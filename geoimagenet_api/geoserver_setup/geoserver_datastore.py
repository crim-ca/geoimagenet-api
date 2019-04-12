import json
import re
import sys
import urllib.parse
from dataclasses import dataclass
from json import JSONDecodeError
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import List, Dict, Union

import requests
import yaml
from geoserver.catalog import Catalog
from geoserver.store import DataStore, CoverageStore, WmsStore
from loguru import logger
from sqlalchemy.exc import IntegrityError

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import Image
from geoimagenet_api.geoserver_setup.image_data import ImageData


@dataclass
class Style:
    name: str
    path: str


class GeoServerDatastore:
    thread_pool_size = 3
    extensions = {".tif": "GeoTIFF", ".tiff": "GeoTIFF"}

    def __init__(self, url, user, password, yaml_path, dry_run=False):
        self.geoserver_url = url.rstrip("/")
        if not self.geoserver_url.endswith("/rest"):
            self.geoserver_url += "/rest"

        self.gwc_url = self.geoserver_url.replace("/rest", "/gwc/rest")

        self.yaml_path = yaml_path
        self.yaml_config = yaml.safe_load(open(self.yaml_path))

        self.user = user
        self.password = password

        self.dry_run = dry_run

        self._catalog = None
        self._existing_styles = None

    def configure(self):
        """Launch the configuration of the remote GeoServer instance."""
        styles = [Style(**s) for s in self.yaml_config["styles"]]
        logger.debug("Read styles: " + ", ".join(s.name for s in styles))

        self.ensure_gwc_gridset()

        image_data = self.parse_images()

        image_data_8bit = [i for i in image_data if i.bits == 8]
        image_data_not_8bit = [i for i in image_data if i.bits != 8]

        self.create_workspaces(image_data_8bit)
        self.create_styles(styles)
        self.create_coverage_stores(image_data_8bit)
        self.seed_cache(image_data_8bit)

        self.write_postgis_image_info(image_data_8bit + image_data_not_8bit)

    def write_postgis_image_info(self, image_data: List[ImageData]):
        logger.info(f"Writing images information in database")
        with connection_manager.get_db_session() as session:
            for data in image_data:
                for image_path in data.images_list:
                    db_image = Image(
                        sensor_name=data.sensor_name,
                        bands=data.bands,
                        bits=data.bits,
                        filename=image_path.stem,
                        extension=image_path.suffix,
                    )
                    session.add(db_image)
                    try:
                        session.flush()
                    except IntegrityError:
                        logger.info(f"Image already in database: {db_image}")
                        session.rollback()
                    else:
                        logger.info(f"Added Image information: {db_image}")
            if not self.dry_run:
                session.commit()

    def request(
        self,
        method,
        url,
        data=None,
        gwc=False,
        json_=True,
        params=None,
        ignore_codes=None,
    ) -> Dict:
        if gwc:
            url = self.gwc_url + url
        else:
            url = self.geoserver_url + url
        content_type = "application/json" if json_ else "application/xml"
        headers = {"Accept": content_type, "Content-type": content_type}
        if json_:
            data = json.dumps(data)
        r = requests.request(
            method,
            url,
            data=data,
            auth=(self.user, self.password),
            headers=headers,
            params=params,
        )
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if ignore_codes and e.response.status_code in ignore_codes:
                pass
            else:
                logger.exception(f"Request content: {r.content}")
                raise
        if json_:
            try:
                return r.json()
            except JSONDecodeError:
                return r.content

    def _get_data_file(self, filename) -> Path:
        return Path(__file__).parent / "geoserver_requests" / filename

    def ensure_gwc_gridset(self):
        epsg_3857_gridset = self._get_data_file("epsg_3857_gridset.xml").read_text()

        existing_gridsets = self.request("get", "/gridsets", gwc=True)
        if "EPSG:3857" not in existing_gridsets:
            logger.info(f"CREATE gridset: EPSG:3857")
            if not self.dry_run:
                name = urllib.parse.quote("EPSG:3857")
                self.request(
                    "put",
                    f"/gridsets/{name}",
                    data=epsg_3857_gridset,
                    gwc=True,
                    json_=False,
                )
        else:
            logger.info(f"Gridset exists: EPSG:3857")

    def seed_cache(self, image_data: List[ImageData]):
        if self.get_config("seed_gwc_cache"):
            cached_layers = self.request("get", "/layers", gwc=True)
            sensor_names = list(set(i.sensor_name for i in image_data))
            layers_to_seed = [
                c for c in cached_layers if any(c.startswith(s) for s in sensor_names)
            ]

            logger.info(f"Generating layer cache for {len(layers_to_seed)} layers")

            if not self.dry_run:
                for layer in layers_to_seed:
                    data = {
                        "seedRequest": {
                            "name": layer,
                            "gridSetId": "EPSG:3857",
                            "zoomStart": 0,
                            "zoomStop": 19,
                            "type": "seed",
                            "threadCount": 8,
                        }
                    }
                    self.request("post", f"/seed/{layer}.json", data=data, gwc=True)

    def _get_absolute_path(self, path):
        """Paths can be relative to the config.yaml file or absolute"""
        return Path(self.yaml_path).parent / Path(path)

    def get_config(self, name):
        if name not in self.yaml_config:
            logger.error(f"Missing '{name}' parameter in config")
            sys.exit(1)

        value = self.yaml_config[name]
        return value

    @property
    def catalog(self):
        if self._catalog is None:
            logger.debug(f"Getting catalog from {self.geoserver_url}")
            self._catalog = Catalog(
                self.geoserver_url, username=self.user, password=self.password
            )
        return self._catalog

    @property
    def existing_styles(self):
        if not self._existing_styles:
            self._existing_styles = {s.name: s for s in self.catalog.get_styles()}
        return self._existing_styles

    def parse_images(self) -> List[ImageData]:
        def _parse_folder_name(name: str):
            match = re.match(r"^([^_]+)_([^_]+)_([^_]+)$", name)
            if not match:
                raise ValueError(
                    f"Folder name not of the format '{{sensor}}_{{bands}}_{{bits}}': {name}"
                )
            return match.groups()

        images_folder = Path(self.get_config("images_folder"))
        images_data = []
        for folder in images_folder.iterdir():
            if not folder.is_dir():
                continue
            sensor_name, bands, bits = _parse_folder_name(folder.name)
            images_data.append(
                ImageData(
                    sensor_name=sensor_name,
                    bands=bands,
                    bits=bits,
                    images_list=list(folder.glob("*.*")),
                )
            )
        if not images_data:
            logger.debug("No images found.")

        return images_data

    @property
    def workspaces(self):
        catalog = self.catalog
        logger.debug(f"Getting workspaces")
        return catalog.get_workspaces()

    def remove_workspaces(
        self, workspace_names: List[str], delete_other_workspaces: bool, overwrite: bool
    ):
        """Not used. If required, remove existing workspaces."""
        if delete_other_workspaces or overwrite:
            logger.debug(f"Removing workspaces")
            existing_workspaces = self.workspaces

            for workspace in existing_workspaces:
                workspace_exists = workspace.name in workspace_names
                if (
                    overwrite
                    and workspace_exists
                    or delete_other_workspaces
                    and not workspace_exists
                ):
                    logger.info(f"DELETE workspace: {workspace.href}")
                    if not self.dry_run:
                        self.catalog.delete(workspace, recurse=True)

    def create_workspaces(self, image_data: List[ImageData]):
        logger.debug(f"Creating workspaces")
        existing_workspaces = self.workspaces
        existing_workspaces_names = [w.name for w in existing_workspaces]

        for data in image_data:
            for workspace_name in data.workspace_names():
                if workspace_name not in existing_workspaces_names:
                    logger.info(
                        f"CREATE workspace: name={workspace_name}, uri={workspace_name}"
                    )
                    if not self.dry_run:
                        self.catalog.create_workspace(
                            name=workspace_name, uri=workspace_name
                        )

    def create_styles(self, styles: List[Style]):
        logger.debug(f"Creating styles")
        for style in styles:
            name, path = style.name, self._get_absolute_path(style.path)
            if not path.exists():
                logger.error(f"Path to style {name} doesn't exists: {path}")
                sys.exit(1)

            data = path.read_text()

            logger.info(f"CREATE style: {name}")
            if not self.dry_run:
                self.catalog.create_style(
                    name,
                    data,
                    overwrite=True,
                    workspace=None,
                    style_format="sld10",
                    raw=False,
                )
        self._existing_styles = None

    def map_threadded(self, func, iterable):
        if self.thread_pool_size > 1:
            t = ThreadPool(processes=self.thread_pool_size)
            t.map(func, iterable)
        else:
            list(map(func, iterable))

    def create_coverage_stores(self, image_data: List[ImageData]):
        logger.debug(f"Creating stores")

        for data in image_data:
            if data.bands == "RGBN" and any(
                i.sensor_name == data.sensor_name and i.bands in ("RGB", "NRG")
                for i in image_data
            ):
                # if RGB or NRG images exist, don't load RGBN images
                continue

            def _create_coverage_store(path):
                logger.debug(f"Found image: {path}")
                for workspace_name in data.workspace_names():
                    style = None
                    if data.bands == "RGBN":
                        style = workspace_name.split("_")[-1]
                    self.create_coverage_store(path, workspace_name, style)

            self.map_threadded(_create_coverage_store, data.images_list)

    def create_coverage_store(self, path: Path, workspace_name: str, style: str = None):
        image_name = path.stem
        type_ = self.extensions.get(path.suffix.lower())
        if type_ is None:
            logger.warning(f"Image extension not recognized: {path}")
            return

        logger.info(f"CREATE {type_} store: {workspace_name}:{image_name}")
        if not self.dry_run:
            layer_name = path.stem
            layer = None
            store = self.catalog.get_store(name=image_name, workspace=workspace_name)
            if store:
                logger.info(f"Store already exists: {workspace_name}:{image_name}")
                layer = [r for r in store.get_resources() if r.name == layer_name]
                if layer:
                    layer = layer[0]
                else:
                    logger.info(
                        f"Layer doesn't exist ({layer_name}). Re-creating store."
                    )
                    self.catalog.delete(store)
                    store = None

            if not store and not layer:
                layer = self.catalog.create_coveragestore(
                    image_name,
                    workspace=workspace_name,
                    path=str(path),
                    type=type_,
                    create_layer=True,
                    layer_name=layer_name,
                    source_name=image_name,
                )

                logger.info(f"SET layer properties: {layer_name}")
                layer.projection = "EPSG:3857"
                self.catalog.save(layer)
                if style:
                    logger.debug(f"Applying style {style}")
                    url = f"/workspaces/{workspace_name}/layers/{layer_name}"
                    data = {"layer": {"defaultStyle": {"name": style}}}
                    self.request("put", url, data=data)
                    layer.default_style = self.existing_styles[style]

            if self.get_config("create_cached_layers"):
                cached_layer_name = f"{workspace_name}:{layer_name}"
                logger.info(f"CREATE cached layer: {layer_name}")
                coverage_data = self.request(
                    "get", f"/workspaces/{workspace_name}/coverages/{layer_name}"
                )
                bbox = coverage_data["coverage"]["nativeBoundingBox"]
                assert bbox["crs"]["$"] == "EPSG:3857"

                data = (
                    self._get_data_file("cached_layer_put.xml")
                    .read_text()
                    .format(
                        workspace_name=workspace_name,
                        layer_name=layer_name,
                        minx=bbox["minx"],
                        miny=bbox["miny"],
                        maxx=bbox["maxx"],
                        maxy=bbox["maxy"],
                    )
                )
                name = urllib.parse.quote(cached_layer_name)

                self.request(
                    "put", f"/layers/{name}", data=data, gwc=True, json_=False
                )

    def create_layergroup(self, workspace):
        """Not used."""
        existing_groups = self.catalog.get_layergroups(workspaces=workspace.name)
        if existing_groups:
            logger.debug(
                f"Deleting existing layer group in workspace: {workspace.name}"
            )
            if not self.dry_run:
                for group in existing_groups:
                    self.catalog.delete(group)
        layers = self.catalog.get_layers()
        layer_names = [
            layer.name
            for layer in layers
            if layer.name.startswith(workspace.name + ":")
        ]
        bounds = ("0", "0", "0", "0", "EPSG:3857")
        styles = [workspace.style] * len(layer_names)
        layer_group = self.catalog.create_layergroup(
            workspace.layer_group_name,
            layers=layer_names,
            styles=styles,
            bounds=bounds,
            mode="SINGLE",
            abstract=None,
            title=None,
            workspace=workspace.name,
        )
        logger.info(f"CREATE layer group: {workspace.layer_group_name}")
        if not self.dry_run:
            self.catalog.save(layer_group)

    def get_stores(
        self, workspace_name
    ) -> List[Union[DataStore, CoverageStore, WmsStore]]:
        logger.debug(f"Getting stores for workspace {workspace_name}")
        stores = self.catalog.get_stores(workspaces=workspace_name)
        return stores
