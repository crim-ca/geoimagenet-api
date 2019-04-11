"""
Command line script to configure geoserver from a configuration file.
"""
import json
import re
import sys
import urllib.parse
from json import JSONDecodeError
from pathlib import Path
from typing import List, Union, Dict, Tuple
from dataclasses import dataclass, field

import requests

from loguru import logger
import click
import yaml
from geoserver.catalog import Catalog
from geoserver.store import CoverageStore, WmsStore, DataStore
from sqlalchemy.exc import IntegrityError

from geoimagenet_api.config import config
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import Image


@dataclass
class Style:
    name: str
    path: str


class ImageData:
    """Data structure containing a list of images with its metadata.

    The folder name for the images will always be of the format {sensor_name}_{bands}_{bits}.
    Example: PLEIADES_RGBN_16

    The filenames can be anything, as long as any convention is respected within each image type.
    This is because the pairing of different images filenames depending on bands and bits
    is done using the smallest levenshtein distance.
    """

    re_bits = re.compile(r"^[1-9]\d*$")

    def __init__(
        self, sensor_name: str, bands: str, bits: str, images_list: List[Path]
    ):
        if not sensor_name.isupper():
            raise ValueError(
                f"'sensor_name' must be all caps in folder name: {sensor_name}"
            )
        if not bands.isupper():
            raise ValueError(f"'bands' must be all caps in folder name: {bands}")
        if not self.re_bits.match(bits):
            raise ValueError(f"'bits' must be an integer in folder name: {bits}")
        self.sensor_name = sensor_name
        self.bands = bands
        self.bits = int(bits)
        self.images_list = images_list

    def workspace_names(self, bands=None):
        names = []
        bands_list = [self.bands]
        if bands:
            bands_list = [bands]
        elif self.bands == "RGBN":
            bands_list = ["RGB", "NRG"]
        for bands in bands_list:
            names.append(f"{self.sensor_name}_{bands}")
        return names


@dataclass
class Workspace:
    name: str
    uri: str
    style: str
    images_path: str = field(default="")
    layer_group_name: str = field(default="")


class GeoServerDatastore:
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
        # workspaces = [Workspace(**s) for s in self.yaml_config["workspaces"]]
        # logger.debug("Read workspaces: " + ", ".join(w.name for w in workspaces))
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
            session.commit()

    def _request(
        self, method, url, data=None, gwc=False, json_=True, params=None
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
        except requests.exceptions.HTTPError:
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

        existing_gridsets = self._request("get", "/gridsets", gwc=True)
        if "EPSG:3857" not in existing_gridsets:
            logger.info(f"CREATE gridset: EPSG:3857")
            if not self.dry_run:
                name = urllib.parse.quote("EPSG:3857")
                self._request(
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
            cached_layers = self._request("get", "/layers", gwc=True)
            sensor_names = list(set(i.sensor_name for i in image_data))
            layers_to_seed = [
                c for c in cached_layers if any(c.startswith(s) for s in sensor_names)
            ]

            logger.info(f"Generating layer cache for {len(layers_to_seed)} layers")

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
                self._request("post", f"/seed/{layer}.json", data=data, gwc=True)

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
            self._catalog = Catalog(self.geoserver_url)
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
                    f"Folder name not of the format 'sensor_bands_bits': {name}"
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
        self,
        workspaces_to_create: List[Workspace],
        delete_other_workspaces: bool,
        overwrite: bool,
    ):
        """Not used. If required, remove existing workspaces."""
        if delete_other_workspaces or overwrite:
            logger.debug(f"Removing workspaces")
            existing_workspaces = self.workspaces
            workspaces_names_to_create = [w.name for w in workspaces_to_create]

            for workspace in existing_workspaces:
                workspace_exists = workspace.name in workspaces_names_to_create
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

    def create_coverage_stores(self, image_data: List[ImageData]):
        logger.debug(f"Creating stores")

        for data in image_data:
            if data.bands == "RGBN":
                for i in image_data:
                    if i.sensor_name == data.sensor_name and i.bands in ("RGB", "NRG"):
                        # if RGB or NRG images exist, don't load RGBN images
                        continue

            for path in data.images_list:
                logger.debug(f"Found image: {path}")
                for workspace_name in data.workspace_names():
                    style = None
                    if data.bands == "RGBN":
                        style = workspace_name.split("_")[-1]
                    self.create_coverage_store(path, workspace_name, style)

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
                layer = self.catalog.get_resource(
                    name=layer_name, workspace=workspace_name
                )
                if layer is None:
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
                    self._request("put", url, data=data)
                    layer.default_style = self.existing_styles[style]

            if self.get_config("create_cached_layers"):
                cached_layer_name = f"{workspace_name}:{layer.name}"
                logger.info(f"CREATE cached layer: {layer_name}")
                coverage_data = self._request(
                    "get", f"/workspaces/{workspace_name}/coverages/{layer.name}"
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

                self._request(
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


class GeoServerMirror(GeoServerDatastore):
    def __init__(
        self,
        gs_datastore_url,
        gs_datastore_user,
        gs_datastore_password,
        gs_mirror_url,
        gs_mirror_user,
        gs_mirror_password,
        gs_yaml_config,
        dry_run,
    ):
        self.datastore = GeoServerDatastore(
            gs_datastore_url,
            gs_datastore_user,
            gs_datastore_password,
            gs_yaml_config,
            dry_run,
        )
        super().__init__(
            gs_mirror_url, gs_mirror_user, gs_mirror_password, gs_yaml_config, dry_run
        )

    def configure(self):
        image_data = self.parse_images()
        image_data_8bit = [i for i in image_data if i.bits == 8]
        self.create_workspaces(image_data_8bit)

        self.create_wms_stores(image_data_8bit)
        self.create_wms_layers(image_data_8bit)

    def create_wms_stores(self, image_data_8bit: List[ImageData]):
        logger.info("Creating wms stores")
        # delete and recreate
        # r = self._request("delete", f"/workspaces//wmsstores/{self.store_name}.json")
        # r = self._request("get", "/workspaces//wmsstores")

        for image_data in image_data_8bit:
            for workspace_name in image_data.workspace_names():
                r = self._request("get", f"/workspaces/{workspace_name}/wmsstores")
                existing_wms_stores_names = []
                if r["wmsStores"]:
                    existing_wms_stores_names = [
                        w["name"] for w in r["wmsStores"]["wmsStore"]
                    ]

                store_name = workspace_name  # they have the same name

                if store_name not in existing_wms_stores_names:
                    capabilities_url = (
                        self.datastore.geoserver_url.replace("/rest", "")
                        + "/gwc/service/wms?SERVICE=WMS&VERSION=1.1.1&REQUEST=getcapabilities&TILED=true"
                    )
                    data = {
                        "wmsStore": {
                            "name": store_name,
                            "type": "WMS",
                            "capabilitiesURL": capabilities_url,
                            "user": self.datastore.user,
                            "password": self.datastore.password,
                            "maxConnections": 6,
                            "readTimeout": 60,
                            "connectTimeout": 30,
                        }
                    }
                    logger.info(f"CREATE wms store: {store_name}")
                    if not self.dry_run:
                        self._request(
                            "post",
                            f"/workspaces/{workspace_name}/wmsstores.json",
                            data=data,
                        )

    def create_wms_layers(self, image_data_8bit: List[ImageData]):
        logger.info("Creating wms layers")
        # r = self._request(
        #     "get",
        #     f"/workspaces//wmsstores/{self.store_name}/wmslayers.json",
        # )
        # print(r)

        data = {
            "wmsLayer": {
                "name": "string",
                "nativeName": "string",
                # "namespace": {
                #     "name": "string",
                #     "link": "string"
                # },
                "title": "string",
                # "abstract": "",
                "description": "",
                # "keywords": [
                #     {
                #         "string": "string"
                #     }
                # ],
                # "metadatalinks": {
                #     "metadataLink": [
                #         {
                #             "type": "string",
                #             "metadataType": "string",
                #             "content": "string"
                #         }
                #     ]
                # },
                # "dataLinks": {
                #     "metadataLink": [
                #         {
                #             "type": "string",
                #             "content": "string"
                #         }
                #     ]
                # },
                "nativeCRS": "string",
                "srs": "string",
                # "nativeBoundingBox": {
                #     "minx": 0,
                #     "maxx": 0,
                #     "miny": 0,
                #     "maxy": 0,
                #     "crs": "string"
                # },
                # "latLonBoundingBox": {
                #     "minx": 0,
                #     "maxx": 0,
                #     "miny": 0,
                #     "maxy": 0,
                #     "crs": "string"
                # },
                "projectionPolicy": "FORCE_DECLARED",
                "enabled": True,
                # "metadata": [
                #     {
                #         "@key": "regionateStrategy",
                #         "text": "string"
                #     }
                # ],
                # "store": {
                #     "@class": "string",
                #     "name": "string",
                #     "href": "string"
                # }
            }
        }
        for image_data in image_data_8bit:
            for workspace_name in image_data.workspace_names():
                stores = self.datastore.get_stores(workspace_name)
                for store in stores:
                    if self.catalog.get_resource(
                        name=store.name, workspace=workspace_name
                    ):
                        logger.info(f"Layer already exists: {store.name}")
                        continue

                    wmslayer = data["wmsLayer"]
                    wmslayer["name"] = store.name
                    wmslayer["nativeName"] = f"{store.workspace.name}:{store.name}"
                    wmslayer["title"] = store.name
                    wmslayer["nativeCRS"] = "EPSG:3857"
                    wmslayer["srs"] = "EPSG:3857"

                    logger.info(f"CREATE wms layer: {wmslayer['name']}")

                    if not self.dry_run:
                        store_name = workspace_name  # they have the same name
                        self._request(
                            "post",
                            f"/workspaces/{workspace_name}/wmsstores/{store_name}/wmslayers.json",
                            data=data,
                        )
                        self._request(
                            "put",
                            f"/workspaces/{workspace_name}/wmsstores/{store_name}/wmslayers/{wmslayer['name']}",
                            data={"wmsLayer": {}},
                            params={"calculate": "latlonbbox"},
                        )


def main(
    gs_datastore_url: str,
    gs_datastore_user: str,
    gs_datastore_password: str,
    gs_mirror_url: str,
    gs_mirror_user: str,
    gs_mirror_password: str,
    gs_yaml_config: str,
    dry_run=False,
):
    logger.info(f"## Configuring datastore")
    GeoServerDatastore(
        gs_datastore_url,
        gs_datastore_user,
        gs_datastore_password,
        gs_yaml_config,
        dry_run,
    ).configure()

    logger.info(f"## Configuring GeoServer mirror instance")
    GeoServerMirror(
        gs_datastore_url,
        gs_datastore_user,
        gs_datastore_password,
        gs_mirror_url,
        gs_mirror_user,
        gs_mirror_password,
        gs_yaml_config,
        dry_run,
    ).configure()


@click.command()
@click.option(
    "-d",
    "--dry-run",
    is_flag=True,
    help="Only print actions to perform without changing the remote server.",
)
@click.option("--gs-yaml-config", help="Path to the yaml configuration file")
@click.option(
    "--gs-datastore-url",
    help="GeoServer instance where the GeoTIFF images are served from.",
)
@click.option("--gs-datastore-user", help="Username to connect to Geoserver datastore")
@click.option(
    "--gs-datastore-password",
    prompt=True,
    hidden=True,
    help="Password to connect to Geoserver datastore",
)
@click.option(
    "--gs-mirror-url",
    help="GeoServer instance where the GeoTIFF images are served from.",
)
@click.option(
    "--gs-mirror-user", help="Username to connect to Geoserver mirror service"
)
@click.option(
    "--gs-mirror-password",
    prompt=True,
    hidden=True,
    help="Password to connect to Geoserver mirror service",
)
def cli(
    dry_run,
    gs_yaml_config,
    gs_datastore_url,
    gs_datastore_user,
    gs_datastore_password,
    gs_mirror_url,
    gs_mirror_user,
    gs_mirror_password,
):
    """Main entry point for the cli."""

    def _set(variable, variable_name):
        if not variable:
            variable = config.get(variable_name, str)
        if not variable:
            logger.error(f"'{variable_name}' required, exiting.")
            sys.exit(1)
        return variable

    gs_datastore_url = _set(gs_datastore_url, "gs_datastore_url")
    gs_datastore_user = _set(gs_datastore_user, "gs_datastore_user")
    gs_datastore_password = _set(gs_datastore_password, "gs_datastore_password")
    gs_mirror_url = _set(gs_mirror_url, "gs_mirror_url")
    gs_mirror_user = _set(gs_mirror_user, "gs_mirror_user")
    gs_mirror_password = _set(gs_mirror_password, "gs_mirror_password")

    if not gs_yaml_config:
        gs_yaml_config = Path(__file__).with_name("config.yaml")
        if not gs_yaml_config.exists():
            gs_yaml_config = None
    gs_yaml_config = Path(_set(gs_yaml_config, "gs_yaml_config"))

    logger.debug(f"Started with input file: {gs_yaml_config}")

    main(
        gs_datastore_url,
        gs_datastore_user,
        gs_datastore_password,
        gs_mirror_url,
        gs_mirror_user,
        gs_mirror_password,
        gs_yaml_config,
        dry_run,
    )


if __name__ == "__main__":
    cli()
