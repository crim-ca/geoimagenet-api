import json

import pytest
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


def _write_annotation(user_id=1, taxonomy_class=2, status=AnnotationStatus.new, image_name="my image"):
    with connection_manager.get_db_session() as session:
        annotation = Annotation(
            annotator_id=user_id,
            geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
            taxonomy_class_id=taxonomy_class,
            image_name=image_name,
            status=status,
        )
        session.add(annotation)
        session.commit()
        _ = annotation.id

    return annotation


def _delete_annotation(annotation_id):
    with connection_manager.get_db_session() as session:
        session.query(Annotation).filter_by(id=annotation_id).delete()
        session.commit()
        session.query(AnnotationLog).filter_by(annotation_id=annotation_id).delete()
        session.commit()


@pytest.fixture
def simple_annotation(request):
    annotation = _write_annotation(user_id=1)
    request.addfinalizer(lambda: _delete_annotation(annotation.id))
    return annotation


@pytest.fixture
def simple_annotation_user_2(request):
    annotation = _write_annotation(user_id=2)
    request.addfinalizer(lambda: _delete_annotation(annotation.id))
    return annotation


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
        assert log[0].review_requested == annotation.review_requested
        assert log[0].operation == AnnotationLogOperation.insert

        # update image_name
        annotation.image_name = "something else"
        annotation.review_requested = True
        session.add(annotation)
        session.commit()
        log = session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()

        assert log[1].annotator_id is None
        assert log[1].geometry is None
        assert log[1].status is None
        assert log[1].taxonomy_class_id is None
        assert log[1].image_name == "something else"
        assert log[1].review_requested is True
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
        assert log[2].review_requested is None
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

        # cleanup
        session.query(Annotation).filter_by(id=inserted_id).delete()
        session.commit()
        session.query(AnnotationLog).filter_by(annotation_id=inserted_id).delete()
        session.commit()
        session.query(Person).filter(Person.id.in_([user_id, user2_id])).delete(
            synchronize_session=False
        )
        session.commit()


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

        # cleanup
        session.query(AnnotationLog).filter_by(annotation_id=annotation.id).delete()
        session.commit()
        session.query(Person).filter(Person.id == user_id).delete()
        session.commit()


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


def test_annotations_put_srid(client, any_geojson, simple_annotation):
    with connection_manager.get_db_session() as session:
        annotation_id = simple_annotation.id
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


def test_annotations_request_review(client, simple_annotation):
    assert not simple_annotation.review_requested

    def request_review(boolean):
        data = {
            "annotation_ids": [f"annotation.{simple_annotation.id}"],
            "boolean": boolean,
        }
        r = client.post(
            api_url(f"/annotations/request_review"),
            content_type="application/json",
            data=json.dumps(data),
        )
        assert r.status_code == 204

    request_review(True)

    with connection_manager.get_db_session() as session:
        assert (
            session.query(Annotation)
            .filter_by(id=simple_annotation.id)
            .first()
            .review_requested
        )

    request_review(False)

    with connection_manager.get_db_session() as session:
        assert (
            not session.query(Annotation)
            .filter_by(id=simple_annotation.id)
            .first()
            .review_requested
        )


def test_annotations_request_review_not_authorized(client, simple_annotation_user_2):
    data = {
        "annotation_ids": [f"annotation.{simple_annotation_user_2.id}"],
        "boolean": True,
    }
    r = client.post(
        api_url(f"/annotations/request_review"),
        content_type="application/json",
        data=json.dumps(data),
    )
    assert r.status_code == 403


def test_annotations_request_review_not_found(client, simple_annotation):
    data = {"annotation_ids": [f"annotation.1234"], "boolean": True}
    r = client.post(
        api_url(f"/annotations/request_review"),
        content_type="application/json",
        data=json.dumps(data),
    )
    assert r.status_code == 404


def test_annotations_put(client, any_geojson, simple_annotation_user_2):
    with connection_manager.get_db_session() as session:
        annotation_id = simple_annotation_user_2.id
        annotator_id = simple_annotation_user_2.annotator_id

        if any_geojson["type"] == "FeatureCollection":
            first_feature = any_geojson["features"][0]
            first_feature["id"] = f"annotation.{annotation_id}"
            first_feature["status"] = f"released"
            properties = AnnotationProperties(**first_feature["properties"])
        else:
            first_feature = any_geojson
            any_geojson["id"] = f"annotation.{annotation_id}"
            any_geojson["status"] = f"released"
            properties = AnnotationProperties(**any_geojson["properties"])

        r = client.put(
            api_url(f"/annotations"),
            content_type="application/json",
            data=json.dumps(any_geojson),
        )
        assert r.status_code == 204

        annotation2 = session.query(Annotation).filter_by(id=annotation_id).one()
        assert annotation2.taxonomy_class_id == properties.taxonomy_class_id
        assert annotation2.image_name == properties.image_name

        # you can't change owner of an annotation
        assert annotation2.annotator_id == annotator_id
        # you can't change the status of an annotation this way
        assert annotation2.status == AnnotationStatus.new

        wkt = "SRID=3857;" + wkt_string[first_feature["geometry"]["type"]]

        wkt_geom = (
            "SRID=3857;" + session.query(func.ST_AsText(annotation2.geometry)).scalar()
        )
        assert wkt_geom == wkt


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


def test_annotation_count(client):
    """
    Taxonomy classes tree:
    1
    --2
      --3
    --9

    """

    def get_counts(taxonomy_class_id):
        r = client.get(api_url(f"/annotations/counts/{taxonomy_class_id}"))
        assert r.status_code == 200
        return r.json

    def assert_count(taxonomy_class_id, status, expected):
        r = get_counts(taxonomy_class_id)
        counts = r[str(taxonomy_class_id)]
        assert counts[status] == expected

    with connection_manager.get_db_session() as session:
        # make sure there are no other annotations
        session.query(Annotation).delete()
        session.commit()

        def add(taxonomy_class_id, status):
            _write_annotation(taxonomy_class=taxonomy_class_id, status=status)

        try:
            add(3, "released")
            add(3, "released")
            add(9, "validated")
            add(9, "rejected")
            add(1, "deleted")

            add(3, "review")
            add(3, "review")
            add(9, "review")
            add(1, "review")
            add(2, "review")

            assert_count(3, "released", 2)
            assert_count(1, "released", 2)
            assert_count(1, "new", 0)
            assert_count(1, "pre_released", 0)
            assert_count(1, "review", 5)
            assert_count(2, "review", 3)
            assert_count(1, "validated", 1)
            assert_count(9, "validated", 1)
            assert_count(2, "validated", 0)
            assert_count(1, "rejected", 1)
            assert_count(9, "rejected", 1)
            assert_count(2, "rejected", 0)
            assert_count(1, "deleted", 1)
        finally:
            # cleanup
            session.query(Annotation).delete()
            session.commit()


def test_annotation_counts_not_found(client):
    r = client.get(api_url(f"/annotations/counts/123456"))
    assert r.status_code == 404


def test_annotation_counts_by_image_not_found(client):
    r = client.get(api_url(f"/annotations/counts_by_image/123456"))
    assert r.status_code == 404


def test_annotation_counts_by_image(client):
    """
    Taxonomy classes tree:
    1
    --2
      --3
    --9

    """

    def get_counts(taxonomy_class_id, status, image_name):
        r = client.get(api_url(f"/annotations/counts_by_image/{taxonomy_class_id}"))
        assert r.status_code == 200
        for i in r.json:
            if i["status"] == status and i["image_name"] == image_name:
                return i
        raise AssertionError("Got the wrong annotation count")

    def assert_count(taxonomy_class_id, status, image_name, expected):
        r = get_counts(taxonomy_class_id, status, image_name)
        counts = r["annotation_count"]
        assert counts == expected

    with connection_manager.get_db_session() as session:
        # make sure there are no other annotations
        session.query(Annotation).delete()
        session.commit()

        def add(taxonomy_class_id, status, image_name):
            _write_annotation(taxonomy_class=taxonomy_class_id, status=status, image_name=image_name)

        try:
            add(3, "released", "image_1")
            add(3, "new", "image_1")
            add(3, "validated", "image_1")

            add(2, "validated", "image_1")
            add(2, "validated", "image_1")

            add(9, "validated", "image_1")
            add(9, "validated", "image_1")

            add(3, "released", "image_2")
            add(3, "new", "image_2")
            add(3, "validated", "image_2")

            add(2, "validated", "image_2")
            add(2, "validated", "image_2")

            add(9, "validated", "image_2")
            add(9, "validated", "image_2")

            assert_count(1, "released", "image_1", 1)
            assert_count(1, "validated", "image_1", 5)
            assert_count(2, "validated", "image_1", 3)

            assert_count(1, "released", "image_2", 1)
            assert_count(1, "validated", "image_2", 5)
            assert_count(2, "validated", "image_2", 3)
        finally:
            # cleanup
            session.query(Annotation).delete()
            session.commit()
