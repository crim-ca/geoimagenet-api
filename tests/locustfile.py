from locust import HttpLocust, TaskSet


def index(l):
    l.client.get("/")


def taxo(l):
    l.client.get("/taxonomy/objets/1")


def classes(l):
    l.client.get("/taxonomy_classes/1", params={"depth": 10}, verify=False)


def classes_search(l):
    l.client.get("/taxonomy_classes", params={"taxonomy_name": "Objets", "id": 1, "depth": 10}, verify=False)


def classes_depth_0(l):
    l.client.get("/taxonomy_classes/1", params={"depth": 0}, verify=False)


def add_annotation_geojson(l):
    data = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-13621076.051761277, 6281028.872735048],
                    [-13621052.165189937, 6280804.33896446],
                    [-13620884.959190564, 6280923.771821156],
                    [-13621076.051761277, 6281028.872735048],
                ]
            ],
        },
        "properties": {
            "taxonomy_class_id": 8,
            "annotator_id": 1,
            "image_name": "My Image",
        },
    }
    l.client.post("/annotations", json=data, verify=False)


def add_annotation_xml(l):
    data = '<Transaction xmlns="http://www.opengis.net/wfs" service="WFS" version="1.1.0" xsi:schemaLocation="http://www.opengis.net/wfs http://schemas.opengis.net/wfs/1.1.0/wfs.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><Insert><annotation xmlns="geoimagenet"><geometry><Polygon xmlns="http://www.opengis.net/gml" srsName="EPSG:3857"><exterior><LinearRing srsName="EPSG:3857"><posList srsDimension="2">-13624202.803949567 6279980.252253259 -13624432.115034422 6279330.537512835 -13623725.072522784 6279483.411569405 -13624202.803949567 6279980.252253259</posList></LinearRing></exterior></Polygon></geometry><taxonomy_class_id>8</taxonomy_class_id><annotator_id>1</annotator_id><image_name>My Image</image_name></annotation></Insert></Transaction>'
    l.client.post(
        "/geoserver/wfs", data=data, headers={"Content-Type": "text/xml"}, verify=False
    )


class UserBehavior(TaskSet):
    tasks = {
        # index: 1,
        # add_annotation_geojson: 1,
        # add_annotation_xml: 1,
        classes: 1,
        # classes_search: 1,
        # classes_depth_0: 1
    }


class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    min_wait = 700
    max_wait = 1300
