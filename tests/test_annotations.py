from functools import partial

import pytest
import pp
from geoalchemy2 import functions
from sqlalchemy.exc import InternalError

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import (
    Annotation,
    Person,
    AnnotationLog,
    AnnotationLogOperation,
    AnnotationStatus,
)
from tests.utils import random_user_name, api_url


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


def insert_annotation(session, taxonomy_class, status):
    annotation = Annotation(
        annotator_id=1,
        geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
        taxonomy_class_id=taxonomy_class,
        image_name="my image",
        status=status,
    )
    session.add(annotation)
    session.commit()
    return annotation.id


def test_annotation_count(client):
    """
    Taxonomy classes tree:
    1
    --2
      --3
    --9

    """

    def get_counts(taxonomy_class_id):
        r = client.get(api_url(f"/annotations/{taxonomy_class_id}/counts"))
        assert r.status_code == 200
        return r.json

    def assert_count(taxonomy_class_id, status, expected):
        r = get_counts(taxonomy_class_id)
        counts = [t for t in r if t["taxonomy_class_id"] == taxonomy_class_id][0][
            "counts"
        ]
        assert counts[status] == expected

    with connection_manager.get_db_session() as session:

        def add(taxonomy_class_id, status):
            insert_annotation(session, taxonomy_class_id, status)

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
