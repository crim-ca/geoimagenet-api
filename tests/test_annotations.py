import contextlib

import pytest
from geoalchemy2 import functions
from sqlalchemy import func

import geoimagenet_api
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import (
    Annotation,
    AnnotationLog,
    AnnotationLogOperation,
    AnnotationStatus,
    TaxonomyClass,
)
from geoimagenet_api.openapi_schemas import AnnotationProperties

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


@pytest.fixture(autouse=True)
def magpie_current_user_1(monkeypatch):
    monkeypatch.setattr(geoimagenet_api.endpoints.annotations, "get_logged_user_id", lambda *a: 1)


@pytest.fixture(params=[point, linestring, polygon])
def geojson_geometry(request):
    return {
        "type": "Feature",
        "geometry": request.param,
        "properties": {
            "taxonomy_class_id": 1,
            "image_name": "PLEIADES_RGB:test_image",
        },
    }


@pytest.fixture(params=["collection", "single"])
def any_geojson(request, geojson_geometry):
    if request.param == "collection":
        return {"type": "FeatureCollection", "features": [geojson_geometry]}
    else:
        return geojson_geometry


def write_annotation(
    *,
    session=None,
    user_id=1,
    taxonomy_class=2,
    status=AnnotationStatus.new,
    image_id=1,
    review_requested=False,
    geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
):
    def _write(_session):
        annotation = Annotation(
            annotator_id=user_id,
            geometry=geometry,
            taxonomy_class_id=taxonomy_class,
            image_id=image_id,
            review_requested=review_requested,
            status=status,
        )
        _session.add(annotation)
        _session.commit()
        _session.refresh(annotation)
        _session.expunge(annotation)

        return annotation

    if session is not None:
        return _write(session)
    else:
        with connection_manager.get_db_session() as session:
            return _write(session)


def _delete_annotation(annotation_id):
    with connection_manager.get_db_session() as session:
        session.query(Annotation).filter_by(id=annotation_id).delete()
        session.commit()
        session.query(AnnotationLog).filter_by(annotation_id=annotation_id).delete()
        session.commit()


@pytest.fixture
def simple_annotation(request):
    annotation = write_annotation(user_id=1)
    request.addfinalizer(lambda: _delete_annotation(annotation.id))
    return annotation


@pytest.fixture
def simple_annotation_user_2(request):
    annotation = write_annotation(user_id=2)
    request.addfinalizer(lambda: _delete_annotation(annotation.id))
    return annotation


def assert_log_equals(
    log,
    *,
    taxonomy_class_id=None,
    image_id=None,
    status=None,
    review_requested=None,
    geometry=None,
    annotator_id=None,
    annotation_id=None,
    operation=AnnotationLogOperation.update,
):
    assert log.taxonomy_class_id == taxonomy_class_id
    assert log.image_id == image_id
    assert log.status == status
    assert log.review_requested == review_requested
    assert (
        log.geometry is None and geometry is None or log.geometry.desc == geometry.desc
    )
    assert log.annotator_id == annotator_id
    assert log.annotation_id == annotation_id
    assert log.operation == operation


def test_annotation_all_fields(client, simple_annotation):
    annotations = client.get("/annotations").json()
    properties = annotations["features"][0]["properties"]

    assert properties["taxonomy_class_id"] == 2
    assert properties["taxonomy_class_code"] == "test"
    assert properties["annotator_id"] == 1
    assert properties["image_id"] == 1
    assert properties["image_name"] == "test"
    assert properties["status"] == "new"
    assert properties["name"] == 1
    assert properties["review_requested"] == False




def test_annotation_log_triggers():
    with _clean_annotation_session() as session:
        start_geometry = "SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))"
        annotation = write_annotation(
            session=session,
            user_id=1,
            geometry=start_geometry,
            taxonomy_class=1,
            image_id=1,
        )
        session.add(annotation)

        def get_last_log():
            return (
                session.query(AnnotationLog).order_by(AnnotationLog.id.desc()).first()
            )

        assert session.query(AnnotationLog).count() == 1
        wkt_geom = session.query(functions.ST_GeomFromEWKT(start_geometry)).scalar()
        assert_log_equals(
            get_last_log(),
            taxonomy_class_id=annotation.taxonomy_class_id,
            image_id=annotation.image_id,
            status=AnnotationStatus.new,
            review_requested=annotation.review_requested,
            geometry=wkt_geom,
            annotator_id=1,
            annotation_id=annotation.id,
            operation=AnnotationLogOperation.insert,
        )

        # update image_id
        annotation.image_id = 2
        annotation.review_requested = True
        session.commit()

        assert_log_equals(
            get_last_log(),
            image_id=2,
            review_requested=True,
            annotation_id=annotation.id,
        )

        # update geometry
        annotation_log_counts_before = session.query(AnnotationLog).count()
        polygon_wkt = "SRID=3857;POLYGON((0 0,1 0,2 1,0 1,0 0))"
        annotation.geometry = polygon_wkt
        session.commit()
        annotation_log_counts_after = session.query(AnnotationLog).count()

        # no annotation log was written
        assert annotation_log_counts_before == annotation_log_counts_after

        # update annotator
        annotation.annotator_id = 2
        session.commit()

        assert_log_equals(get_last_log(), annotator_id=2, annotation_id=annotation.id)

        # update status
        annotation.status = AnnotationStatus.released
        session.commit()

        assert_log_equals(
            get_last_log(),
            status=AnnotationStatus.released,
            annotation_id=annotation.id,
        )

        # update taxonomy_class_id
        annotation.taxonomy_class_id = 2
        session.commit()

        assert_log_equals(
            get_last_log(), taxonomy_class_id=2, annotation_id=annotation.id
        )


def test_log_delete_annotation():
    with _clean_annotation_session() as session:
        annotation = write_annotation(
            session=session,
            user_id=2,
            geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
            taxonomy_class=1,
            image_id=1,
        )
        session.query(Annotation).filter_by(id=annotation.id).delete()
        session.commit()

        log = session.query(AnnotationLog).order_by(AnnotationLog.id.desc()).first()

        assert_log_equals(
            log, annotation_id=annotation.id, operation=AnnotationLogOperation.delete
        )


def test_annotations_put_not_found(client, geojson_geometry):
    geojson_geometry["id"] = "annotation.1234567"
    r = client.put(f"/annotations", json=geojson_geometry)
    assert r.status_code == 404


def test_annotations_put_not_an_int(client, geojson_geometry):
    geojson_geometry["id"] = "annotation.not_an_int"
    r = client.put(f"/annotations", json=geojson_geometry)
    assert r.status_code == 400


def test_annotations_put_id_required(client, geojson_geometry):
    r = client.put(f"/annotations", json=geojson_geometry)
    assert r.status_code == 400


def test_annotations_post_image_doesnt_exist(client, geojson_geometry):
    geojson_geometry["properties"]["image_name"] = "doesnt exist"
    r = client.post(f"/annotations", json=geojson_geometry)
    assert r.status_code == 400


def test_annotations_put_image_doesnt_exist(
    client, geojson_geometry, simple_annotation
):
    annotation_id = simple_annotation.id
    geojson_geometry["id"] = f"annotation.{annotation_id}"
    geojson_geometry["properties"]["image_name"] = "doesnt exist"
    r = client.put(f"/annotations", json=geojson_geometry)
    assert r.status_code == 400


def test_annotations_put_not_allowed_other_user_admin(client, geojson_geometry):
    with _clean_annotation_session() as session:
        annotation = write_annotation(
            session=session,
            user_id=2,
        )

        annotation_id = annotation.id
        geojson_geometry["id"] = f"annotation.{annotation_id}"

        r = client.put(
            f"/annotations",
            json=geojson_geometry,
        )
        assert r.status_code == 403


def test_annotations_post_srid(client, any_geojson):
    from_srid = 4326
    query = {"srid": from_srid}
    r = client.post("/annotations", json=any_geojson, params=query)
    written_ids = r.json()
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


def test_annotations_post_image_id(client, any_geojson):
    """POST an annotation using the image_id instead of the image_name"""
    if any_geojson["type"] == "FeatureCollection":
        properties = any_geojson["features"][0]["properties"]
    else:
        properties = any_geojson["properties"]
    properties["image_id"] = 2
    del properties["image_name"]
    r = client.post("/annotations", json=any_geojson)
    written_ids = r.json()
    assert r.status_code == 201
    with connection_manager.get_db_session() as session:
        annotation = session.query(Annotation).filter_by(id=written_ids[0]).first()
        assert annotation.image_id == 2


def test_annotations_put_image_id(client, simple_annotation, any_geojson):
    """POST an annotation using the image_id instead of the image_name"""
    if any_geojson["type"] == "FeatureCollection":
        feature = any_geojson["features"][0]
    else:
        feature = any_geojson
    feature["properties"]["image_id"] = 2
    del feature["properties"]["image_name"]

    feature["id"] = f"annotation.{simple_annotation.id}"

    r = client.put("/annotations", json=any_geojson)
    assert r.status_code == 204
    with connection_manager.get_db_session() as session:
        annotation = session.query(Annotation).filter_by(id=simple_annotation.id).first()
        assert annotation.image_id == 2


def test_annotations_put_srid(client, any_geojson, simple_annotation):
    with connection_manager.get_db_session() as session:
        annotation_id = simple_annotation.id
        if any_geojson["type"] == "FeatureCollection":
            any_geojson["features"][0]["id"] = f"annotation.{annotation_id}"
        else:
            any_geojson["id"] = f"annotation.{annotation_id}"

        from_srid = 4326
        query = {"srid": from_srid}
        r = client.put(f"/annotations", json=any_geojson, params=query)
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
        r = client.post(f"/annotations/request_review", json=data)
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
    r = client.post(f"/annotations/request_review", json=data)
    assert r.status_code == 403


def test_annotations_request_review_not_an_int(client):
    data = {"annotation_ids": [f"annotation.not_an_int"], "boolean": True}
    r = client.post(f"/annotations/request_review", json=data)
    assert r.status_code == 400


def test_annotations_request_review_not_found(client, simple_annotation):
    data = {"annotation_ids": [f"annotation.1234"], "boolean": True}
    r = client.post(f"/annotations/request_review", json=data)
    assert r.status_code == 404


def test_annotations_put(client, any_geojson, simple_annotation):
    with connection_manager.get_db_session() as session:
        annotation_id = simple_annotation.id
        annotator_id = simple_annotation.annotator_id

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

        r = client.put(f"/annotations", json=any_geojson)
        assert r.status_code == 204

        annotation2 = session.query(Annotation).filter_by(id=annotation_id).one()
        assert annotation2.taxonomy_class_id == properties.taxonomy_class_id
        assert annotation2.image_id == 1  # there should be an image of id 1 named test_image.tif

        # you can't change the status of an annotation this way
        assert annotation2.status == AnnotationStatus.new

        wkt = "SRID=3857;" + wkt_string[first_feature["geometry"]["type"]]

        wkt_geom = (
            "SRID=3857;" + session.query(func.ST_AsText(annotation2.geometry)).scalar()
        )
        assert wkt_geom == wkt


def test_annotation_post(client, any_geojson):
    r = client.post(f"/annotations", json=any_geojson)
    written_ids = r.json()
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

    def get_counts(taxonomy_class_id, with_taxonomy_children=True):
        params = {"with_taxonomy_children": with_taxonomy_children}
        r = client.get(f"/annotations/counts/{taxonomy_class_id}", params=params)
        assert r.status_code == 200
        return r.json()

    with _clean_annotation_session() as session:

        def add(taxonomy_class_id, status):
            write_annotation(
                session=session, taxonomy_class=taxonomy_class_id, status=status
            )

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

        counts = get_counts(taxonomy_class_id=1, with_taxonomy_children=True)

        assert counts["3"]["released"] == 2
        assert counts["1"]["released"] == 2
        assert counts["1"]["new"] == 0
        assert counts["1"]["pre_released"] == 0
        assert counts["1"]["review"] == 5
        assert counts["2"]["review"] == 3
        assert counts["1"]["validated"] == 1
        assert counts["9"]["validated"] == 1
        assert counts["2"]["validated"] == 0
        assert counts["1"]["rejected"] == 1
        assert counts["9"]["rejected"] == 1
        assert counts["2"]["rejected"] == 0
        assert counts["1"]["deleted"] == 1

        counts_without_children = get_counts(
            taxonomy_class_id=1, with_taxonomy_children=False
        )
        assert counts_without_children["1"]["review"] == 1

        assert all(key.isdigit() for key in counts)
        assert all(key.isdigit() for key in counts_without_children)


def _get_annotations(client, params):
    r = client.get(f"/annotations", params=params)
    assert r.status_code == 200
    return r.json()["features"]


@contextlib.contextmanager
def _clean_annotation_session():
    """Clean all annotation before and after the session scope"""
    with connection_manager.get_db_session() as session:
        # make sure there are no other annotations
        session.query(Annotation).delete()
        session.query(AnnotationLog).delete()
        session.commit()
        try:
            yield session
        finally:
            # cleanup
            session.query(Annotation).delete()
            session.query(AnnotationLog).delete()
            session.commit()


def test_annotation_get_none(client):
    with _clean_annotation_session():
        annotations = _get_annotations(client, {})
        assert not annotations


def test_annotation_get_image_id(client):
    with _clean_annotation_session() as session:
        write_annotation(session=session, image_id=1)
        write_annotation(session=session, image_id=2)

        params = {"image_name": "PLEIADES_RGB:test_image"}
        annotations = _get_annotations(client, params)
        assert len(annotations) == 1
        assert annotations[0]["properties"]["image_id"] == 1


def test_annotation_get_username(client, simple_annotation_user_2):
    params = {"username": "observateur"}
    annotations = _get_annotations(client, params)
    assert len(annotations) == 1
    assert annotations[0]["properties"]["annotator_id"] == 2


def test_annotation_get_username_not_found(client, simple_annotation_user_2):
    params = {"username": "notfound"}
    r = client.get(f"/annotations", params=params)
    assert r.status_code == 404


def test_annotation_get_status(client):
    with _clean_annotation_session() as session:
        write_annotation(session=session, status=AnnotationStatus.validated)
        write_annotation(session=session, status=AnnotationStatus.rejected)
        params = {"status": "validated"}
        annotations = _get_annotations(client, params)
        assert len(annotations) == 1
        assert annotations[0]["properties"]["status"] == "validated"


def test_annotation_get_taxonomy_class_id(client):
    with _clean_annotation_session() as session:
        write_annotation(session=session, taxonomy_class=1)
        write_annotation(session=session, taxonomy_class=2)
        params = {"taxonomy_class_id": 1}
        annotations = _get_annotations(client, params)
        assert len(annotations) == 1
        assert annotations[0]["properties"]["taxonomy_class_id"] == 1


def test_annotation_get_review_requested(client):
    with _clean_annotation_session() as session:
        write_annotation(session=session, review_requested=True)
        write_annotation(session=session, review_requested=False)
        params = {"review_requested": True}
        annotations = _get_annotations(client, params)
        assert len(annotations) == 1
        assert annotations[0]["properties"]["review_requested"]

        params = {"review_requested": False}
        annotations = _get_annotations(client, params)
        assert len(annotations) == 1

        annotations = _get_annotations(client, {})
        assert len(annotations) == 2


def test_annotation_get_current_user_only(client):
    with _clean_annotation_session() as session:
        write_annotation(session=session, user_id=1)
        write_annotation(session=session, user_id=2)
        params = {"current_user_only": True}
        annotations = _get_annotations(client, params)
        assert len(annotations) == 1
        assert annotations[0]["properties"]["annotator_id"] == 1


def test_annotation_get_with_geometry(client):
    with _clean_annotation_session() as session:
        write_annotation(session=session)
        annotations = _get_annotations(client, {"with_geometry": False})
        assert len(annotations) == 1
        assert "geometry" not in annotations[0]

        annotations = _get_annotations(client, {"with_geometry": True})
        assert len(annotations) == 1
        assert isinstance(annotations[0]["geometry"], dict)

        assert "geometry" not in annotations[0]["properties"]
        assert "id" not in annotations[0]["properties"]


def test_annotation_counts_not_found(client):
    r = client.get(f"/annotations/counts/123456")
    assert r.status_code == 404


def test_annotation_counts_by_image(client):
    """
    Taxonomy classes tree:
    1
    --2
      --3
    --9

    """

    def get_counts(taxonomy_class_id, with_taxonomy_children=True):
        params = {
            "group_by_image": True,
            "with_taxonomy_children": with_taxonomy_children,
        }
        r = client.get(f"/annotations/counts/{taxonomy_class_id}", params=params)
        assert r.status_code == 200
        return r.json()

    with _clean_annotation_session() as session:

        def add(taxonomy_class_id, status, image_id):
            write_annotation(
                session=session,
                taxonomy_class=taxonomy_class_id,
                status=status,
                image_id=image_id,
            )

        add(3, "released", 1)
        add(3, "new", 1)
        add(3, "validated", 1)

        add(2, "validated", 1)
        add(2, "validated", 1)

        add(9, "validated", 1)
        add(9, "validated", 1)

        add(3, "released", 2)
        add(3, "new", 2)
        add(3, "validated", 2)

        add(2, "validated", 2)
        add(2, "validated", 2)

        add(9, "validated", 2)
        add(9, "validated", 2)

        # todo: get image names from api

        counts = get_counts(taxonomy_class_id=1, with_taxonomy_children=True)
        assert counts["PLEIADES_RGB:test_image"]["released"] == 1
        assert counts["PLEIADES_RGB:test_image"]["validated"] == 5
        assert counts["PLEIADES_RGB:test_image2"]["released"] == 1
        assert counts["PLEIADES_RGB:test_image2"]["validated"] == 5
        assert set(counts) == {"PLEIADES_RGB:test_image", "PLEIADES_RGB:test_image2"}

        counts = get_counts(taxonomy_class_id=2, with_taxonomy_children=True)
        assert counts["PLEIADES_RGB:test_image"]["validated"] == 3
        assert counts["PLEIADES_RGB:test_image2"]["validated"] == 3
        assert set(counts) == {"PLEIADES_RGB:test_image", "PLEIADES_RGB:test_image2"}

        counts = get_counts(taxonomy_class_id=2, with_taxonomy_children=False)
        assert counts["PLEIADES_RGB:test_image2"]["validated"] == 2
        assert set(counts) == {"PLEIADES_RGB:test_image", "PLEIADES_RGB:test_image2"}


def test_annotation_counts_current_user(client):
    """
    Taxonomy classes tree:
    1
    --2
      --3
    --9

    """

    def get_counts(taxonomy_class_id, current_user_only, group_by_image=False):
        params = {
            "group_by_image": group_by_image,
            "current_user_only": current_user_only,
        }
        r = client.get(f"/annotations/counts/{taxonomy_class_id}", params=params)
        assert r.status_code == 200
        return r.json()

    def assert_count(taxonomy_class_id, current_user_only, group_by_image, expected):
        r = get_counts(taxonomy_class_id, current_user_only, group_by_image)
        if group_by_image:
            counts = r["PLEIADES_RGB:test_image"]
        else:
            counts = r[str(taxonomy_class_id)]
        assert counts["new"] == expected

    with _clean_annotation_session() as session:

        def add(taxonomy_class_id, user_id):
            write_annotation(
                session=session,
                user_id=user_id,
                taxonomy_class=taxonomy_class_id,
                image_id=1,
            )

        add(taxonomy_class_id=2, user_id=1)
        add(taxonomy_class_id=2, user_id=1)
        add(taxonomy_class_id=3, user_id=1)
        add(taxonomy_class_id=3, user_id=1)
        add(taxonomy_class_id=3, user_id=1)

        add(taxonomy_class_id=3, user_id=2)
        add(taxonomy_class_id=3, user_id=2)
        add(taxonomy_class_id=3, user_id=2)

        # group_by_image=False
        assert_count(2, True, False, 5)
        assert_count(2, False, False, 8)
        assert_count(3, True, False, 3)
        assert_count(3, False, False, 6)

        # group_by_image=True
        assert_count(2, True, True, 5)
        assert_count(2, False, True, 8)
        assert_count(3, True, True, 3)
        assert_count(3, False, True, 6)


def test_annotation_counts_review_requested(client):
    """
    Taxonomy classes tree:
    1
    --2
      --3
    --9

    """

    def get_counts(taxonomy_class_id, review_requested=None):
        params = {}
        if review_requested is not None:
            params["review_requested"] = review_requested
        r = client.get(f"/annotations/counts/{taxonomy_class_id}", params=params)
        assert r.status_code == 200
        return r.json()

    def assert_count(taxonomy_class_id, review_requested, expected):
        r = get_counts(taxonomy_class_id, review_requested)
        counts = r[str(taxonomy_class_id)]
        assert counts["new"] == expected

    with _clean_annotation_session() as session:
        write_annotation(session=session, taxonomy_class=2, review_requested=True)
        write_annotation(session=session, taxonomy_class=3, review_requested=True)
        write_annotation(session=session, taxonomy_class=3, review_requested=False)

        assert_count(2, review_requested=True, expected=2)
        assert_count(2, review_requested=False, expected=1)
        assert_count(2, review_requested=None, expected=3)


def test_friendly_name():
    with connection_manager.get_db_session() as session:
        geometry = "SRID=4326;POLYGON((-71 39,-71 41,-69 41,-69 39,-71 39))"
        transformed_geometry = session.query(
            func.ST_AsEWKT(func.ST_Transform(func.ST_GeomFromEWKT(geometry), 3857))
        ).scalar()
        annotation = write_annotation(
            session=session, geometry=transformed_geometry, taxonomy_class=12
        )

        assert annotation.name == "CARD_+040.000000_-070.000000"
        taxo = (
            session.query(TaxonomyClass)
            .filter_by(id=annotation.taxonomy_class_id)
            .first()
        )
        taxo.code = "TEST"
        session.commit()

        session.add(annotation)

        annotation.taxonomy_class_id = 10
        session.commit()
        annotation.taxonomy_class_id = taxo.id
        session.commit()

        assert annotation.name == "TEST_+040.000000_-070.000000"

        geometry2 = "SRID=4326;POLYGON((-71 37,-71 41,-69 41,-69 37,-71 37))"
        transformed_geometry2 = session.query(
            func.ST_AsEWKT(func.ST_Transform(func.ST_GeomFromEWKT(geometry2), 3857))
        ).scalar()

        annotation.geometry = transformed_geometry2
        session.commit()

        assert annotation.name == "TEST_+039.000000_-070.000000"

        session.query(Annotation).filter_by(id=annotation.id).delete()
        session.commit()
