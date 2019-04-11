from typing import List

from loguru import logger

from geoimagenet_api.geoserver_setup.geoserver_datastore import GeoServerDatastore
from geoimagenet_api.geoserver_setup.image_data import ImageData


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
