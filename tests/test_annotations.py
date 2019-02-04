import json

import pytest
import pp
from geoalchemy2 import functions
from sqlalchemy import func

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import (
    Annotation,
    Person,
    AnnotationLog,
    AnnotationLogOperation,
    AnnotationStatus,
)
from geoimagenet_api.openapi_schemas import AnnotationProperties
from tests.utils import random_user_name, api_url

wkt_string = {
    "Point": "POINT(100 0)",
    "LineString": "LINESTRING(100 0,101 0,101 1,100 1,100 0)",
    "Polygon": "POLYGON((100 0,101 0,101 1,100 1,100 0))",
}

test_coordinates = [
    [100.0, 0.0],
    [101.0, 0.0],
    [101.0, 1.0],
    [100.0, 1.0],
    [100.0, 0.0],
]

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


@pytest.fixture(params=["collection", "single"])
def any_geojson(request, geojson_geometry):
    if request.param == "collection":
        return {"type": "FeatureCollection", "features": [geojson_geometry]}
    else:
        return geojson_geometry


def random_user():
    with connection_manager.get_db_session() as session:
        username = random_user_name()
        person = Person(username=username, name="Unit Tester")
        session.add(person)
        session.commit()

        return person.id


def test_annotation_log_triggers():
    with connection_manager.get_db_session() as session:
        user_id = random_user()

        annotation = Annotation(
            annotator_id=user_id,
            geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
            taxonomy_class_id=1,
            image_name="my image",
        )
        session.add(annotation)
        session.commit()

        inserted_id = session.query(Annotation.id).filter_by(id=annotation.id).one().id
        assert inserted_id == annotation.id

        log = session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()
        assert len(log) == 1
        assert log[0].taxonomy_class_id == annotation.taxonomy_class_id
        assert log[0].image_name == annotation.image_name
        assert log[0].status == AnnotationStatus.new
        assert log[0].operation == AnnotationLogOperation.insert

        # update image_name
        annotation.image_name = "something else"
        session.add(annotation)
        session.commit()
        log = session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()

        assert log[1].annotator_id is None
        assert log[1].geometry is None
        assert log[1].status is None
        assert log[1].taxonomy_class_id is None
        assert log[1].image_name == "something else"
        assert log[1].operation == AnnotationLogOperation.update

        # update geometry
        polygon_wkt = "SRID=3857;POLYGON((0 0,1 0,2 1,0 1,0 0))"
        annotation.geometry = polygon_wkt
        session.add(annotation)
        session.commit()
        log = session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()

        wkt_geom = (
            "SRID=3857;" + session.query(functions.ST_AsText(log[2].geometry)).scalar()
        )
        assert wkt_geom == polygon_wkt
        assert log[2].annotator_id is None
        assert log[2].status is None
        assert log[2].taxonomy_class_id is None
        assert log[2].image_name is None
        assert log[2].operation == AnnotationLogOperation.update

        # update annotator
        user2_id = random_user()
        annotation.annotator_id = user2_id
        session.add(annotation)
        session.commit()
        log = (
            session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()[-1]
        )
        assert log.annotator_id == user2_id

        # update status
        annotation.status = AnnotationStatus.released
        session.add(annotation)
        session.commit()
        log = (
            session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()[-1]
        )
        assert log.status == AnnotationStatus.released
        annotation.status = AnnotationStatus.new
        session.add(annotation)
        session.commit()

        # update taxonomy_class_id
        annotation.taxonomy_class_id = 2
        session.add(annotation)
        session.commit()
        log = (
            session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()[-1]
        )
        assert log.taxonomy_class_id == 2


def test_log_delete_annotation():
    with connection_manager.get_db_session() as session:
        user_id = random_user()

        annotation = Annotation(
            annotator_id=user_id,
            geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
            taxonomy_class_id=1,
            image_name="my image",
        )
        session.add(annotation)
        session.commit()

        session.delete(annotation)
        session.commit()

        log = (
            session.query(AnnotationLog)
            .filter_by(annotation_id=annotation.id)
            .all()[-1]
        )
        assert log.annotation_id == annotation.id
        assert log.operation == AnnotationLogOperation.delete


def test_annotations_put_not_found(client, geojson_geometry):
    geojson_geometry["id"] = "annotation.1234567"

    r = client.put(
        api_url(f"/annotations"),
        content_type="application/json",
        data=json.dumps(geojson_geometry),
    )
    assert r.status_code == 404


def test_annotations_post_srid(client, any_geojson):
    from_srid = 4326
    query = {"srid": from_srid}
    r = client.post(
        api_url(f"/annotations"),
        content_type="application/json",
        data=json.dumps(any_geojson),
        query_string=query,
    )
    written_ids = r.json
    assert r.status_code == 201
    with connection_manager.get_db_session() as session:
        annotation = session.query(Annotation).filter_by(id=written_ids[0]).one()
        geom = session.query(func.ST_AsText(annotation.geometry)).scalar()

        geometry_type = geom[: geom.find("(")].title().replace("string", "String")
        initial_coordinates = wkt_string[geometry_type]
        transformed = func.ST_AsText(
            func.ST_Transform(
                func.ST_GeomFromText(initial_coordinates, from_srid), 3857
            )
        )
        expected = session.query(transformed).scalar()
        assert expected == geom


def test_annotations_put_srid(client, any_geojson):
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
        if any_geojson["type"] == "FeatureCollection":
            any_geojson["features"][0]["id"] = f"annotation.{annotation_id}"
        else:
            any_geojson["id"] = f"annotation.{annotation_id}"

        from_srid = 4326
        query = {"srid": from_srid}
        r = client.put(
            api_url(f"/annotations"),
            content_type="application/json",
            data=json.dumps(any_geojson),
            query_string=query,
        )
        assert r.status_code == 204

        annotation = session.query(Annotation).filter_by(id=annotation_id).one()
        geom = session.query(func.ST_AsText(annotation.geometry)).scalar()

        geometry_type = geom[: geom.find("(")].title().replace("string", "String")
        initial_coordinates = wkt_string[geometry_type]
        transformed = func.ST_AsText(
            func.ST_Transform(
                func.ST_GeomFromText(initial_coordinates, from_srid), 3857
            )
        )
        expected = session.query(transformed).scalar()
        assert expected == geom


def test_annotations_put(client, any_geojson):
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
        if any_geojson["type"] == "FeatureCollection":
            first_feature = any_geojson["features"][0]
            first_feature["id"] = f"annotation.{annotation_id}"
            properties = AnnotationProperties(**first_feature["properties"])
        else:
            first_feature = any_geojson
            any_geojson["id"] = f"annotation.{annotation_id}"
            properties = AnnotationProperties(**any_geojson["properties"])

        r = client.put(
            api_url(f"/annotations"),
            content_type="application/json",
            data=json.dumps(any_geojson),
        )
        assert r.status_code == 204

        annotation = session.query(Annotation).filter_by(id=annotation_id).one()
        assert annotation.taxonomy_class_id == properties.taxonomy_class_id
        assert annotation.image_name == properties.image_name
        assert annotation.annotator_id == properties.annotator_id
        assert annotation.status.name == properties.status

        wkt = "SRID=3857;" + wkt_string[first_feature["geometry"]["type"]]

        wkt_geom = (
            "SRID=3857;" + session.query(func.ST_AsText(annotation.geometry)).scalar()
        )
        assert wkt_geom == wkt


def test_annotations_release(client):
    """
    Taxonomy classes tree:
    1
    --2
      --3
    --9

    """
    with connection_manager.get_db_session() as session:
        for class_ in [1, 2, 3, 9]:
            annotation = Annotation(
                annotator_id=1,
                geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
                taxonomy_class_id=class_,
                image_name="my image",
            )
            session.add(annotation)
            session.commit()

        def assert_status(class_id, status):
            assert (
                session.query(Annotation.status)
                .filter_by(taxonomy_class_id=class_id)
                .first()
                .status
                == status
            )

        assert_status(1, AnnotationStatus.new)
        assert_status(2, AnnotationStatus.new)
        assert_status(3, AnnotationStatus.new)
        assert_status(9, AnnotationStatus.new)

        query = {"taxonomy_class_id": 2}

        r = client.post(api_url(f"/annotations/release"), query_string=query)
        assert r.status_code == 204

        assert_status(1, AnnotationStatus.new)
        assert_status(2, AnnotationStatus.released)
        assert_status(3, AnnotationStatus.released)
        assert_status(9, AnnotationStatus.new)

        query = {"taxonomy_class_id": 1}

        r = client.post(api_url(f"/annotations/release"), query_string=query)
        assert r.status_code == 204

        assert_status(1, AnnotationStatus.released)
        assert_status(2, AnnotationStatus.released)
        assert_status(3, AnnotationStatus.released)
        assert_status(9, AnnotationStatus.released)


def test_annotation_post(client, any_geojson):
    r = client.post(
        api_url(f"/annotations"),
        content_type="application/json",
        data=json.dumps(any_geojson),
    )
    written_ids = r.json
    assert r.status_code == 201
    with connection_manager.get_db_session() as session:
        assert session.query(Annotation.id).filter_by(id=written_ids[0]).one()


def test_annotation_delete(client):
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

    client.delete(
        api_url(f"/annotations"),
        content_type="application/json",
        data=json.dumps([f"annotation.{annotation_id}"]),
    )
    with connection_manager.get_db_session() as session:
        assert not session.query(Annotation.id).filter_by(id=annotation_id).first()


def test_annotation_delete_not_found(client):
    r = client.delete(
        api_url(f"/annotations"),
        content_type="application/json",
        data=json.dumps([f"annotation.1234567"]),
    )
    assert r.status_code == 404


def test_annotation_delete_malformed(client):
    r = client.delete(
        api_url(f"/annotations"),
        content_type="application/json",
        data=json.dumps([f"1234567"]),
    )
    assert r.status_code == 400


def test_annotation_count_total(client):
    with connection_manager.get_db_session() as session:
        for user_id in [1, 1, 1, 2, 2, 3]:
            annotation = Annotation(
                annotator_id=user_id,
                geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
                taxonomy_class_id=22,
                image_name="my image",
            )
            session.add(annotation)
        for taxonomy_class_id in [10, 10, 10, 11, 11]:
            annotation = Annotation(
                annotator_id=1,
                geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
                taxonomy_class_id=taxonomy_class_id,
                image_name="my image",
            )
            session.add(annotation)

        session.commit()

    query = {"taxonomy_name": "Objets", "name": "Objets"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)

    expected = {22: 6, 10: 3, 11: 2}

    def recurse(obj):
        if obj["id"] in expected:
            assert obj["annotation_count"] == expected[obj["id"]]
        for child in obj["children"]:
            recurse(child)

    recurse(r.json[0])
