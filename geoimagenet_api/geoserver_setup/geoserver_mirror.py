from pathlib import Path
from typing import List
import sys
import csv

from loguru import logger

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import Image
from geoimagenet_api.geoserver_setup import images_names_utils
from geoimagenet_api.geoserver_setup.geoserver_datastore import GeoServerDatastore
from geoimagenet_api.geoserver_setup.image_data import ImageInfo
from geoimagenet_api.geoserver_setup.utils import find_date, wkt_multipolygon_to_polygon
from geoimagenet_api import config


csv.field_size_limit(sys.maxsize)


class GeoServerMirror(GeoServerDatastore):
    annotation_workspace = "GeoImageNet"
    annotation_store = "annotations"
    annotation_table = "annotation"

    def __init__(
        self,
        gs_datastore_url,
        gs_datastore_user,
        gs_datastore_password,
        gs_mirror_url,
        gs_mirror_user,
        gs_mirror_password,
        gs_yaml_config,
        *,
        dry_run,
        skip_ssl,
    ):
        self.datastore = GeoServerDatastore(
            gs_datastore_url,
            gs_datastore_user,
            gs_datastore_password,
            gs_yaml_config,
            dry_run=dry_run,
        )
        super().__init__(
            gs_mirror_url,
            gs_mirror_user,
            gs_mirror_password,
            gs_yaml_config,
            dry_run=dry_run,
            skip_ssl=skip_ssl,
        )

    def configure(self):
        workspaces_request = self.datastore.request("get", "/workspaces.json")
        images_info = []
        for w in workspaces_request["workspaces"]["workspace"]:
            try:
                images_info.append(ImageInfo.from_workspace_name(w["name"]))
            except ValueError:
                pass
        print(images_info)

        self.create_workspaces(images_info)

        self.create_wms_stores(images_info)
        self.create_wms_layers(images_info)
        self.delete_cached_layers(images_info)

        self.create_annotation_workspace()
        self.create_annotation_store()
        self.create_annotation_layer()

        self.write_postgis_image_info(images_info)

    def write_postgis_image_info(self, image_data: List[ImageInfo]):
        """Write image information into the postgis database.

        Try to take as much information from the remote geoserver datastore from
        wms layers and wfs queries.

        When local images are available in images_folder, they will also be inserted.

        This configuration makes setting up a development environment much simpler.
        When you don't have access to the images, there is nothing you need to do. But
        when the images are available (in production) the information will be added
        without having to specify anything if images_folder is setup correctly.
        """
        logger.info(f"Writing images information in database")

        with connection_manager.get_db_session() as session:

            def write_image_info(image_name, sensor_name, bands, bits):
                existing = (
                    session.query(Image)
                    .filter_by(
                        sensor_name=sensor_name,
                        bands=bands,
                        bits=bits,
                        filename=image_name,
                    )
                    .first()
                )

                if existing:
                    logger.info(f"Image already in database: {image_name}")
                    if existing.trace is None:
                        wkt = self._get_ewkt(sensor_name, image_name)
                        existing.trace = wkt
                        logger.info(f"Updated trace geometry: {image_name}")
                else:
                    wkt = self._get_ewkt(sensor_name, image_name)
                    db_image = Image(
                        sensor_name=sensor_name,
                        bands=bands,
                        bits=bits,
                        filename=image_name,
                        extension=".tif",  # we assume the tiff extension
                        trace=wkt,
                    )
                    session.add(db_image)
                    logger.info(f"Added image information: {image_name}")

            for data in image_data:
                for workspace_name in data.workspace_names():
                    for store in self.datastore.get_stores(workspace_name):
                        write_image_info(store.name, data.sensor_name, data.bands, data.bits)

            image_data_on_drive = self.parse_images()

            for data in image_data_on_drive:
                for image_path in data.images_list:
                    image_name = image_path.stem
                    write_image_info(image_name, data.sensor_name, data.bands, data.bits)

            if not self.dry_run:
                session.commit()

    def _get_ewkt(self, sensor_name, layer_name):
        traces_layer_names = [
            layer["name"]
            for layer in self.datastore.request(
                "get", f"/workspaces/{sensor_name}_CONTOURS/layers"
            )["layers"]["layer"]
        ]
        trace_layer = images_names_utils.find_matching_name(
            layer_name, traces_layer_names
        )
        if not trace_layer:
            logger.error(f"Could not find trace layer for: {layer_name}")
        params = {
            "typeNames": f"{sensor_name}_CONTOURS:{trace_layer}",
            "outputFormat": "csv",
            "srsName": "EPSG:3857",
        }
        content = self.datastore.wfs(params=params).content.decode()
        separator = "\r\n" if "\r\n" in content else "\n"
        header, *geometries = csv.reader(content.split(separator))
        geom_index = header.index("the_geom")
        wkt = geometries[0][geom_index]
        # convert multipolygon to polygon wkt
        polygon_wkt = wkt_multipolygon_to_polygon(wkt)
        ewkt = "SRID=3857;" + polygon_wkt

        return ewkt

    def create_annotation_workspace(self):
        logger.debug(f"Creating annotation workspace")
        existing_workspaces_names = [w.name for w in self.workspaces]

        if self.annotation_workspace not in existing_workspaces_names:
            logger.info(
                f"CREATE workspace: name={self.annotation_workspace}, uri={self.annotation_workspace}"
            )
            if not self.dry_run:
                self.catalog.create_workspace(
                    name=self.annotation_workspace, uri=self.annotation_workspace
                )

    def create_annotation_store(self):
        existing_stores = self.request(
            "get", f"/workspaces/{self.annotation_workspace}/datastores.json"
        )
        existing_stores_names = []
        if existing_stores["dataStores"]:
            existing_stores_names = [
                d["name"] for d in existing_stores["dataStores"]["dataStore"]
            ]

        if self.annotation_store in existing_stores_names:
            logger.info(f"annotation store already exists")
            return

        host = config.get("postgis_host", str)
        user = config.get("postgis_user", str)
        password = config.get("postgis_password", str)
        db = config.get("postgis_db", str)

        data = {
            "dataStore": {
                "name": self.annotation_store,
                "connectionParameters": {
                    "entry": [
                        {"@key": "host", "$": host},
                        {"@key": "port", "$": "5432"},
                        {"@key": "database", "$": db},
                        {"@key": "user", "$": user},
                        {"@key": "passwd", "$": password},
                        {"@key": "dbtype", "$": "postgis"},
                        {"@key": "Expose primary keys", "$": "true"},
                    ]
                },
            }
        }

        logger.info(f"CREATE annotations store")
        if not self.dry_run:
            self.request(
                "post",
                f"/workspaces/{self.annotation_workspace}/datastores.json",
                data=data,
            )

    def create_annotation_layer(self):
        existing_layers = self.request(
            "get",
            f"/workspaces/{self.annotation_workspace}/datastores/{self.annotation_store}/featuretypes.json",
        )
        existing_layers_names = []
        if existing_layers["featureTypes"]:
            existing_layers_names = [
                d["name"] for d in existing_layers["featureTypes"]["featureType"]
            ]

        if self.annotation_table in existing_layers_names:
            logger.info(f"annotation layer already exists")
            return

        data = {
            "featureType": {
                "name": self.annotation_table,
                "nativeCRS": "EPSG:3857",
                "srs": "EPSG:3857",
                "nativeBoundingBox": {
                    "minx": -2.0037508342789244e7,
                    "maxx": 2.0037508342789244e7,
                    "miny": -2.00489661040146e7,
                    "maxy": 2.0048966104014594e7,
                    "crs": "EPSG:3857",
                },
                "projectionPolicy": "FORCE_DECLARED",
                "enabled": True,
            }
        }

        logger.info(f"CREATE annotation layer")
        if not self.dry_run:
            self.request(
                "post",
                f"/workspaces/{self.annotation_workspace}/datastores/{self.annotation_store}/featuretypes.json",
                data=data,
            )

    def delete_cached_layers(self, images_info: List[ImageInfo]):
        existing_layers = self.request("get", f"/layers.json", gwc=True)
        cached_layers_to_delete = []
        for image_data in images_info:
            for workspace_name in image_data.workspace_names():
                for store in self.datastore.get_stores(workspace_name):
                    cached_layer_name = f"{workspace_name}:{store.name}"
                    if cached_layer_name in existing_layers:
                        cached_layers_to_delete.append(cached_layer_name)

        def _delete_cached_layer(layer_name):
            logger.info(f"DELETE cached layer: {layer_name}")
            if not self.dry_run:
                self.request(
                    "delete", f"/layers/{layer_name}", gwc=True, ignore_codes=[404]
                )

        self.map_threaded(_delete_cached_layer, cached_layers_to_delete)

    def create_wms_stores(self, images_info: List[ImageInfo]):
        logger.info("Creating wms stores")

        for image_data in images_info:
            for workspace_name in image_data.workspace_names():
                r = self.request("get", f"/workspaces/{workspace_name}/wmsstores")
                existing_wms_stores_names = []
                if r["wmsStores"]:
                    existing_wms_stores_names = [
                        w["name"] for w in r["wmsStores"]["wmsStore"]
                    ]

                wms_store_name = workspace_name  # they have the same name

                if wms_store_name not in existing_wms_stores_names:
                    capabilities_url = (
                        self.datastore.geoserver_url.replace("/rest", "")
                        + "/gwc/service/wms?SERVICE=WMS&VERSION=1.1.1&REQUEST=getcapabilities"
                    )
                    data = {
                        "wmsStore": {
                            "name": wms_store_name,
                            "type": "WMS",
                            "capabilitiesURL": capabilities_url,
                            "user": self.datastore.user,
                            "password": self.datastore.password,
                            "maxConnections": 6,
                            "readTimeout": 60,
                            "connectTimeout": 30,
                        }
                    }
                    logger.info(f"CREATE wms store: {wms_store_name}")
                    if not self.dry_run:
                        self.request(
                            "post",
                            f"/workspaces/{workspace_name}/wmsstores.json",
                            data=data,
                        )

    def create_wms_layers(self, images_info: List[ImageInfo]):
        logger.info("Creating wms layers")

        attributions = {
            meta["name"]: meta["attribution"] for meta in self.get_config("metadata")
        }

        for image_data in images_info:
            for workspace_name in image_data.workspace_names():

                def _create_wms_layers(store):
                    coverage_info = self.datastore.request(
                        "get",
                        f"/workspaces/{store.workspace.name}/coveragestores/{store.name}/coverages/{store.name}.json",
                    )
                    bbox = coverage_info["coverage"]["nativeBoundingBox"]

                    data = {
                        "wmsLayer": {
                            "name": store.name,
                            "nativeName": f"{store.workspace.name}:{store.name}",
                            "title": store.name,
                            "abstract": "",
                            "description": "",
                            "keywords": [
                                {
                                    "application": "GEOIMAGENET",
                                    "sensor_name": image_data.sensor_name,
                                    "color": workspace_name.split("_")[-1],
                                    "date": find_date(store.name),
                                }
                            ],
                            "nativeBoundingBox": {
                                "minx": bbox["minx"],
                                "maxx": bbox["maxx"],
                                "miny": bbox["miny"],
                                "maxy": bbox["maxy"],
                                "crs": "EPSG:3857",
                            },
                            "nativeCRS": "EPSG:3857",
                            "srs": "EPSG:3857",
                            "projectionPolicy": "FORCE_DECLARED",
                            "enabled": True,
                        }
                    }

                    logger.info(f"CREATE wms layer: {store.name}")

                    if not self.dry_run:
                        wms_store_name = workspace_name  # they have the same name

                        if self.catalog.get_resource(
                            name=store.name, workspace=workspace_name
                        ):
                            logger.info(f"Layer already exists, updating: {store.name}")
                            self.request(
                                "put",
                                f"/workspaces/{workspace_name}/wmsstores/{wms_store_name}/wmslayers/{store.name}.json",
                                data=data,
                                params={"calculate": "latlonbbox"},
                            )
                        else:
                            self.request(
                                "post",
                                f"/workspaces/{workspace_name}/wmsstores/{wms_store_name}/wmslayers.json",
                                data=data,
                            )
                            self.request(
                                "put",
                                f"/workspaces/{workspace_name}/wmsstores/{wms_store_name}/wmslayers/{store.name}.json",
                                data={"wmsLayer": {}},
                                params={"calculate": "latlonbbox"},
                            )

                        attribution = attributions.get(image_data.sensor_name)
                        if attribution:
                            data = {"layer": {"attribution": {"title": attribution}}}
                            self.request(
                                "put",
                                f"/workspaces/{workspace_name}/layers/{store.name}.json",
                                data=data,
                            )

                stores = self.datastore.get_stores(workspace_name)
                self.map_threaded(_create_wms_layers, stores)
