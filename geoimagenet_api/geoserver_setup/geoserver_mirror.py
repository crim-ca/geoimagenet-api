from typing import List

from loguru import logger

from geoimagenet_api.geoserver_setup.geoserver_datastore import GeoServerDatastore
from geoimagenet_api.geoserver_setup.image_data import ImageData
from geoimagenet_api.geoserver_setup.utils import find_date
from geoimagenet_api import config


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
        image_data = self.parse_images()
        image_data_8bit = [i for i in image_data if i.bits == 8]
        self.create_workspaces(image_data_8bit)

        self.create_wms_stores(image_data_8bit)
        self.create_wms_layers(image_data_8bit)
        self.delete_cached_layers(image_data_8bit)

        self.create_annotation_workspace()
        self.create_annotation_store()
        self.create_annotation_layer()

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
                  "minx": -2.0037508342789244E7,
                  "maxx": 2.0037508342789244E7,
                  "miny": -2.00489661040146E7,
                  "maxy": 2.0048966104014594E7,
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

    def delete_cached_layers(self, image_data_8bit: List[ImageData]):
        existing_layers = self.request("get", f"/layers.json", gwc=True)

        for image_data in image_data_8bit:

            def _delete_cached_layers(path):
                layer_name = path.stem
                for workspace_name in image_data.workspace_names():
                    cached_layer_name = f"{workspace_name}:{layer_name}"
                    if cached_layer_name in existing_layers:
                        logger.info(f"DELETE cached layer: {cached_layer_name}")
                        if not self.dry_run:
                            self.request(
                                "delete",
                                f"/layers/{cached_layer_name}",
                                gwc=True,
                                ignore_codes=[404],
                            )

            self.map_threaded(_delete_cached_layers, image_data.images_list)

    def create_wms_stores(self, image_data_8bit: List[ImageData]):
        logger.info("Creating wms stores")

        for image_data in image_data_8bit:
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

    def create_wms_layers(self, image_data_8bit: List[ImageData]):
        logger.info("Creating wms layers")

        attributions = {
            meta["name"]: meta["attribution"] for meta in self.get_config("metadata")
        }

        for image_data in image_data_8bit:
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
