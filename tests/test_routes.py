"""
Important: Some tests don't seem to assert anything.
But the server is setup to validate every input and output using the openapi schema.

So if any json is not valid, it would raise an error.
"""
import pytest
import json

from sqlalchemy import func

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import Annotation
from geoimagenet_api.openapi_schemas import AnnotationProperties
from tests.utils import api_url, random_user_name


test_coordinates = [
    [100.0, 0.0],
    [101.0, 0.0],
    [101.0, 1.0],
    [100.0, 1.0],
    [100.0, 0.0],
]

wkt_string = {
    "Point": "POINT(100 0)",
    "LineString": "LINESTRING(100 0,101 0,101 1,100 1,100 0)",
    "Polygon": "POLYGON((100 0,101 0,101 1,100 1,100 0))",
}

point = {"type": "Point", "coordinates": test_coordinates[0]}
linestring = {"type": "LineString", "coordinates": test_coordinates}
polygon = {"type": "Polygon", "coordinates": [test_coordinates]}


@pytest.fixture(params=[point, linestring, polygon])
def geojson_geometry(request):
    return {
        "type": "Feature",
        "geometry": request.param,
        "properties": {
            "annotator_id": 1,
            "taxonomy_class_id": 1,
            "image_name": "my image name",
        },
    }


def test_root(client):
    r = client.get(api_url("/"))
    assert r.status_code == 200
    assert "name" in r.json
    assert "version" in r.json
    assert "authors" in r.json


def test_not_found(client):
    r = client.get(api_url("/yadayada"))
    assert r.status_code == 404


def test_add_user(client):
    """Adds a new user and get it using different routes"""
    username = random_user_name()
    full_name = "Test User"

    query = {"username": username, "name": full_name}

    r = client.post(api_url("/users"), query_string=query)
    assert r.json["name"] == full_name
    assert r.json["username"]

    r = client.get(api_url("/users"))
    assert any(
        user["username"] == username and user["name"] == full_name for user in r.json
    )

    r = client.get(api_url(f"/users/{username}"))
    assert r.json["username"] == username and r.json["name"] == full_name


def test_taxonomy_class_depth_0(client):
    query = {"taxonomy_name": "Objets", "name": "Objets", "depth": "0"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)
    assert len(r.json) == 1
    assert len(r.json[0]["children"]) == 0


def test_taxonomy_class_depth_1(client):
    query = {"taxonomy_name": "Objets", "name": "Objets", "depth": "1"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)
    assert len(r.json) == 1
    assert len(r.json[0]["children"]) >= 1


def test_taxonomy_class_by_id_query_param(client):
    query = {"taxonomy_name": "Objets", "id": "2"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)
    assert len(r.json) == 1
    assert r.json[0]["name"]


def test_taxonomy_class_by_id_route(client):
    id_ = 1
    r = client.get(api_url(f"/taxonomy_classes/{id_}"))
    assert r.json["name"] == "Objets"


def test_taxonomy_class_by_id_route_depth_1(client):
    id_ = 1
    query = {"depth": "1"}
    r = client.get(api_url(f"/taxonomy_classes/{id_}"), query_string=query)
    assert len(r.json["children"]) >= 1
    assert len(r.json["children"][0]["children"]) == 0
    assert r.json["name"] == "Objets"


def test_taxonomy_class_by_id_route_infinite_depth(client):
    id_ = 1
    query = {"depth": "-1"}
    r = client.get(api_url(f"/taxonomy_classes/{id_}"), query_string=query)

    def max_depth(obj, depth=0):
        return max([max_depth(c["children"], depth + 1) for c in obj] + [depth])

    assert len(r.json["children"]) >= 1
    depth = max_depth([r.json])
    assert depth >= 3


def test_taxonomy_search_all(client):
    r = client.get(api_url(f"/taxonomy"))
    assert len(r.json) >= 2


def test_taxonomy_versions(client):
    r = client.get(api_url(f"/taxonomy"))
    assert isinstance(r.json[0]["versions"], list)
    assert len(r.json[0]["versions"]) >= 1


def test_taxonomy_versions_400_version_only(client):
    query = {"version": "1"}
    r = client.get(api_url(f"/taxonomy"), query_string=query)
    assert r.status_code == 400


def test_taxonomy_versions_version_not_found(client):
    query = {"name": "Objets", "version": "10"}
    r = client.get(api_url(f"/taxonomy"), query_string=query)
    assert r.status_code == 404
    assert r.json == "Version not found"


def test_taxonomy_search_by_slug(client):
    query = {"name": "couverture-de-sol", "version": "1"}
    r = client.get(api_url(f"/taxonomy"), query_string=query)
    assert len(r.json) == 1
    assert r.json[0]["name"] == "Couverture de sol"


def test_taxonomy_search_by_name(client):
    query = {"name": "Couverture de sol", "version": "1"}
    r = client.get(api_url(f"/taxonomy"), query_string=query)
    assert len(r.json) == 1
    assert r.json[0]["name"] == "Couverture de sol"


def test_taxonomy_get_by_slug(client):
    name_slug = "couverture-de-sol"
    version = "1"
    r = client.get(api_url(f"/taxonomy/{name_slug}/{version}"))
    assert r.json["name"] == "Couverture de sol"


def test_taxonomy_get_by_slug_not_found(client):
    name_slug = "not-found"
    version = "10"
    r = client.get(api_url(f"/taxonomy/{name_slug}/{version}"))
    assert r.status_code == 404


def test_annotations_put_not_found(client, geojson_geometry):
    geojson_geometry["properties"]["annotation_id"] = 1_234_567

    r = client.put(
        api_url(f"/annotations"),
        content_type="application/json",
        data=json.dumps(geojson_geometry),
    )
    assert r.status_code == 404


def test_annotations_put(client, geojson_geometry):
    with connection_manager.get_db_session() as session:
        annotation = Annotation(
            annotator_id=1,
            geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
            taxonomy_class_id=2,
            image_name="my image",
        )
        session.add(annotation)
        session.commit()

        annotation_id = annotation.id
        geojson_geometry["properties"]["annotation_id"] = annotation_id

        properties = AnnotationProperties(**geojson_geometry["properties"])

        r = client.put(
            api_url(f"/annotations"),
            content_type="application/json",
            data=json.dumps(geojson_geometry),
        )
        assert r.status_code == 204

        annotation = session.query(Annotation).filter_by(id=annotation_id).one()
        assert annotation.taxonomy_class_id == properties.taxonomy_class_id
        assert annotation.image_name == properties.image_name
        assert annotation.annotator_id == properties.annotator_id
        assert annotation.released == properties.released

        wkt = "SRID=3857;" + wkt_string[geojson_geometry['geometry']['type']]

        wkt_geom = (
            "SRID=3857;" + session.query(func.ST_AsText(annotation.geometry)).scalar()
        )
        assert wkt_geom == wkt


def test_annotation_post(client, geojson_geometry):
    r = client.post(
        api_url(f"/annotations"),
        content_type="application/json",
        data=json.dumps(geojson_geometry),
    )
    written_id = r.json[0]
    with connection_manager.get_db_session() as session:
        assert session.query(Annotation.id).filter_by(id=written_id).one()
