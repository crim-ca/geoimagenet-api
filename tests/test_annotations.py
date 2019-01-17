import pytest
import pp
from geoalchemy2 import functions
from sqlalchemy.exc import InternalError

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import (
    Annotation,
    Person,
    AnnotationLog,
    AnnotationLogDescription,
)
from tests.utils import random_user_name


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
        assert log[0].description == 1  # INSERT

        # update image_name
        annotation.image_name = "something else"
        session.add(annotation)
        session.commit()
        log = session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()

        assert log[1].annotator_id is None
        assert log[1].geometry is None
        assert log[1].released is None
        assert log[1].taxonomy_class_id is None
        assert log[1].image_name == "something else"
        assert log[1].description == 2  # UPDATE

        # update geometry
        polygon_wkt = "SRID=3857;POLYGON((0 0,1 0,2 1,0 1,0 0))"
        annotation.geometry = polygon_wkt
        session.add(annotation)
        session.commit()
        log = session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()

        wkt_geom = "SRID=3857;" + session.query(functions.ST_AsText(log[2].geometry)).scalar()
        assert wkt_geom == polygon_wkt
        assert log[2].annotator_id is None
        assert log[2].released is None
        assert log[2].taxonomy_class_id is None
        assert log[2].image_name is None
        assert log[2].description == 2  # UPDATE

        # update annotator
        user2_id = random_user()
        annotation.annotator_id = user2_id
        session.add(annotation)
        session.commit()
        log = session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()[-1]
        assert log.annotator_id == user2_id

        # update released
        annotation.released = True
        session.add(annotation)
        session.commit()
        log = session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()[-1]
        assert log.released
        annotation.released = False
        session.add(annotation)
        session.commit()

        # update taxonomy_class_id
        annotation.taxonomy_class_id = 2
        session.add(annotation)
        session.commit()
        log = session.query(AnnotationLog).filter_by(annotation_id=inserted_id).all()[-1]
        assert log.taxonomy_class_id == 2


def test_cant_update_released_annotation():
    with connection_manager.get_db_session() as session:

        user_id = random_user()
        user2_id = random_user()

        annotation = Annotation(
            annotator_id=user_id,
            geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
            taxonomy_class_id=1,
            image_name="my image",
            released=True,
        )
        session.add(annotation)
        session.commit()

        annotation_id = annotation.id

        with pytest.raises(InternalError):
            annotation = session.query(Annotation).filter_by(id=annotation_id).scalar()
            annotation.annotator_id = user2_id
            session.add(annotation)
            session.commit()
        session.rollback()

        with pytest.raises(InternalError):
            annotation = session.query(Annotation).filter_by(id=annotation_id).scalar()
            polygon_wkt = "SRID=3857;POLYGON((0 0,1 0,2 1,0 1,0 0))"
            annotation.geometry = polygon_wkt
            session.add(annotation)
            session.commit()
        session.rollback()

        with pytest.raises(InternalError):
            annotation = session.query(Annotation).filter_by(id=annotation_id).scalar()
            annotation.taxonomy_class_id = 2
            session.add(annotation)
            session.commit()
        session.rollback()

        with pytest.raises(InternalError):
            annotation = session.query(Annotation).filter_by(id=annotation_id).scalar()
            annotation.image_name = "something else"
            session.add(annotation)
            session.commit()
        session.rollback()

        annotation = session.query(Annotation).filter_by(id=annotation_id).scalar()

        annotation.released = False
        session.add(annotation)
        session.commit()

        annotation.released = True
        session.add(annotation)
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

        log = session.query(AnnotationLog).filter_by(annotation_id=annotation.id).all()[-1]
        assert log.annotation_id == annotation.id
        delete_id = (
            session.query(AnnotationLogDescription.id).filter_by(name="delete").first().id
        )
        assert log.description == delete_id
