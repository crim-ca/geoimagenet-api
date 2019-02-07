import pytest

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import Annotation, AnnotationStatus
from tests.utils import api_url

image_name_to_cleanup = "testing_annotation_status"


def make_annotation(id, user_id, taxonomy_class, status):
    return Annotation(
        id=id,
        annotator_id=user_id,
        geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
        taxonomy_class_id=taxonomy_class,
        image_name=image_name_to_cleanup,
        status=status,
    )


def insert_annotations(annotations):
    """
    Taxonomy classes tree:
    1
    --2
      --3
    --9

    """
    with connection_manager.get_db_session() as session:
        session.bulk_save_objects(annotations)
        session.commit()


@pytest.fixture
def cleanup_annotations(request):
    def delete_annotations():
        with connection_manager.get_db_session() as session:
            session.query(Annotation).filter_by(
                image_name=image_name_to_cleanup
            ).delete()

    request.addfinalizer(delete_annotations)


def assert_statuses(statuses):
    with connection_manager.get_db_session() as session:
        for annotation_id, status in statuses:
            assert (
                session.query(Annotation.status)
                .filter_by(id=annotation_id)
                .first()
                .status
                == status
            )


def make_annotation_ids_payload(ids):
    return {"annotation_ids": [f"annotation.{i}" for i in ids]}


def test_delete_by_id(cleanup_annotations, client):
    from itertools import cycle

    n_annotations = 3
    ids_list = [100 + i for i in range(n_annotations)]
    ids = cycle(ids_list)

    insert_annotations([
        make_annotation(next(ids), 1, 2, AnnotationStatus.new),
        make_annotation(next(ids), 1, 2, AnnotationStatus.deleted),
        make_annotation(next(ids), 1, 2, AnnotationStatus.released),
    ])
    data = make_annotation_ids_payload(ids_list)

    r = client.put(api_url(f"/annotations/delete"), json=data)
    assert r.status_code == 204

    expected_statuses = [
        (next(ids), AnnotationStatus.deleted),
        (next(ids), AnnotationStatus.deleted),
        (next(ids), AnnotationStatus.released),
    ]
    assert_statuses(expected_statuses)
