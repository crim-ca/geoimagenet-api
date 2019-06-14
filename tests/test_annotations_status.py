import pytest

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import (
    Annotation,
    AnnotationStatus,
    ValidationEvent,
    ValidationValue,
)

image_id_to_cleanup = 3


def make_annotation(id, user_id, taxonomy_class, status):
    return Annotation(
        id=id,
        annotator_id=user_id,
        geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
        taxonomy_class_id=taxonomy_class,
        image_id=image_id_to_cleanup,
        status=status,
    )


def insert_annotations(*annotations):
    """
    annotations is a list of tuples:
    [(user_id, taxonomy_class_id, status), (...), ...]

    Taxonomy classes tree:
    1
    --2
      --3
    --9

    """
    n_annotations = len(annotations)
    ids = list(range(100, 100 + n_annotations))

    annotations = [make_annotation(i, *a) for i, a in zip(ids, annotations)]

    with connection_manager.get_db_session() as session:
        session.bulk_save_objects(annotations)
        session.commit()

    return ids


@pytest.fixture
def cleanup_annotations(request):
    def delete_annotations():
        with connection_manager.get_db_session() as session:
            session.query(ValidationEvent).delete()
            session.query(Annotation).filter_by(
                image_id=image_id_to_cleanup
            ).delete()
            session.commit()

    request.addfinalizer(delete_annotations)


def assert_statuses(ids, expected_statuses):
    with connection_manager.get_db_session() as session:
        for annotation_id, status in zip(ids, expected_statuses):
            assert (
                session.query(Annotation.status)
                .filter_by(id=annotation_id)
                .first()
                .status
                == status
            )


def make_annotation_ids_payload(ids):
    return {"annotation_ids": [f"annotation.{i}" for i in ids]}


def make_taxonomy_class_payload(taxo_id, recurse=True):
    return {"taxonomy_class_id": taxo_id, "with_taxonomy_children": recurse}


def post_taxonomy_class(client, action, taxonomy_class_id, recurse, expected_code=204):
    data = make_taxonomy_class_payload(taxonomy_class_id, recurse=recurse)
    r = client.post(f"/annotations/{action}", json=data)
    assert r.status_code == expected_code


def post_annotation_ids(client, action, ids, expected_code=204):
    data = make_annotation_ids_payload(ids)
    r = client.post(f"/annotations/{action}", json=data)
    assert r.status_code == expected_code


def test_delete_by_id(cleanup_annotations, client):
    ids = insert_annotations((1, 2, AnnotationStatus.new), (1, 1, AnnotationStatus.new))
    post_annotation_ids(client, "delete", ids)
    expected = [AnnotationStatus.deleted, AnnotationStatus.deleted]
    assert_statuses(ids, expected)


def test_delete_by_taxonomy_class(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 3, AnnotationStatus.new),
        (1, 3, AnnotationStatus.released),
        (1, 2, AnnotationStatus.new),
        (1, 1, AnnotationStatus.new),
    )
    post_taxonomy_class(client, "delete", taxonomy_class_id=2, recurse=True)
    expected = [
        AnnotationStatus.deleted,
        AnnotationStatus.released,
        AnnotationStatus.deleted,
        AnnotationStatus.new,
    ]
    assert_statuses(ids, expected)


def test_delete_not_same_user_not_allowed(cleanup_annotations, client):
    ids = insert_annotations((1, 3, AnnotationStatus.new), (2, 3, AnnotationStatus.new))
    post_taxonomy_class(client, "delete", taxonomy_class_id=3, recurse=False)
    expected = [AnnotationStatus.deleted, AnnotationStatus.new]
    assert_statuses(ids, expected)


def test_delete_by_taxonomy_class_no_recursion(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 3, AnnotationStatus.new),
        (1, 3, AnnotationStatus.released),
        (1, 2, AnnotationStatus.new),
        (1, 1, AnnotationStatus.new),
    )
    post_taxonomy_class(client, "delete", taxonomy_class_id=2, recurse=False)
    expected = [
        AnnotationStatus.new,
        AnnotationStatus.released,
        AnnotationStatus.deleted,
        AnnotationStatus.new,
    ]
    assert_statuses(ids, expected)


def test_release_by_id(cleanup_annotations, client):
    ids = insert_annotations((1, 2, AnnotationStatus.new), (1, 1, AnnotationStatus.new))
    post_annotation_ids(client, "release", ids)
    expected = [AnnotationStatus.released, AnnotationStatus.released]
    assert_statuses(ids, expected)


def test_release_by_id_not_found(cleanup_annotations, client):
    post_annotation_ids(client, "release", [12345678], expected_code=404)


def test_release_by_id_not_an_int(cleanup_annotations, client):
    ids = ["not_an_int"]
    post_annotation_ids(client, "release", ids, expected_code=400)


def test_release_id_not_found(cleanup_annotations, client):
    post_taxonomy_class(
        client, "release", taxonomy_class_id=9999, recurse=False, expected_code=404
    )


def test_release_by_taxonomy_class(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 3, AnnotationStatus.new),
        (1, 3, AnnotationStatus.deleted),
        (1, 2, AnnotationStatus.new),
        (1, 1, AnnotationStatus.new),
    )
    post_taxonomy_class(client, "release", taxonomy_class_id=2, recurse=True)
    expected = [
        AnnotationStatus.released,
        AnnotationStatus.deleted,
        AnnotationStatus.released,
        AnnotationStatus.new,
    ]
    assert_statuses(ids, expected)


def test_release_not_same_user_not_allowed(cleanup_annotations, client):
    ids = insert_annotations((1, 3, AnnotationStatus.new), (2, 3, AnnotationStatus.new))
    post_taxonomy_class(client, "release", taxonomy_class_id=3, recurse=False)
    expected = [AnnotationStatus.released, AnnotationStatus.new]
    assert_statuses(ids, expected)


def test_release_by_taxonomy_class_no_recursion(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 3, AnnotationStatus.new),
        (1, 3, AnnotationStatus.validated),
        (1, 2, AnnotationStatus.new),
        (1, 1, AnnotationStatus.new),
    )
    post_taxonomy_class(client, "release", taxonomy_class_id=2, recurse=False)
    expected = [
        AnnotationStatus.new,
        AnnotationStatus.validated,
        AnnotationStatus.released,
        AnnotationStatus.new,
    ]
    assert_statuses(ids, expected)


def test_reject_by_id(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 2, AnnotationStatus.released), (2, 1, AnnotationStatus.released)
    )
    post_annotation_ids(client, "reject", ids)
    expected = [AnnotationStatus.rejected, AnnotationStatus.rejected]
    assert_statuses(ids, expected)


def test_reject_by_taxonomy_class(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 3, AnnotationStatus.released),
        (1, 3, AnnotationStatus.new),
        (1, 2, AnnotationStatus.released),
        (1, 1, AnnotationStatus.released),
    )
    post_taxonomy_class(client, "reject", taxonomy_class_id=2, recurse=True)
    expected = [
        AnnotationStatus.rejected,
        AnnotationStatus.new,
        AnnotationStatus.rejected,
        AnnotationStatus.released,
    ]
    assert_statuses(ids, expected)


def test_reject_not_same_user_allowed(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 3, AnnotationStatus.released), (2, 3, AnnotationStatus.released)
    )
    post_taxonomy_class(client, "reject", taxonomy_class_id=3, recurse=False)
    expected = [AnnotationStatus.rejected, AnnotationStatus.rejected]
    assert_statuses(ids, expected)


def test_reject_by_taxonomy_class_no_recursion(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 3, AnnotationStatus.released),
        (1, 3, AnnotationStatus.new),
        (1, 2, AnnotationStatus.released),
        (1, 1, AnnotationStatus.released),
    )
    post_taxonomy_class(client, "reject", taxonomy_class_id=2, recurse=False)
    expected = [
        AnnotationStatus.released,
        AnnotationStatus.new,
        AnnotationStatus.rejected,
        AnnotationStatus.released,
    ]
    assert_statuses(ids, expected)


def test_validate_by_id(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 2, AnnotationStatus.released), (2, 1, AnnotationStatus.released)
    )
    post_annotation_ids(client, "validate", ids)
    expected = [AnnotationStatus.validated, AnnotationStatus.validated]
    assert_statuses(ids, expected)


def test_validate_by_taxonomy_class(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 3, AnnotationStatus.released),
        (1, 3, AnnotationStatus.new),
        (1, 2, AnnotationStatus.released),
        (1, 1, AnnotationStatus.released),
    )
    post_taxonomy_class(client, "validate", taxonomy_class_id=2, recurse=True)
    expected = [
        AnnotationStatus.validated,
        AnnotationStatus.new,
        AnnotationStatus.validated,
        AnnotationStatus.released,
    ]
    assert_statuses(ids, expected)


def test_validate_not_same_user_allowed(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 3, AnnotationStatus.released), (2, 3, AnnotationStatus.released)
    )
    post_taxonomy_class(client, "validate", taxonomy_class_id=3, recurse=False)
    expected = [AnnotationStatus.validated, AnnotationStatus.validated]
    assert_statuses(ids, expected)


def test_validate_by_taxonomy_class_no_recursion(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 3, AnnotationStatus.released),
        (1, 3, AnnotationStatus.new),
        (1, 2, AnnotationStatus.released),
        (1, 1, AnnotationStatus.released),
    )
    post_taxonomy_class(client, "validate", taxonomy_class_id=2, recurse=False)
    expected = [
        AnnotationStatus.released,
        AnnotationStatus.new,
        AnnotationStatus.validated,
        AnnotationStatus.released,
    ]
    assert_statuses(ids, expected)


def test_action_by_id_not_allowed(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 2, AnnotationStatus.rejected), (1, 2, AnnotationStatus.validated)
    )

    post_annotation_ids(client, "delete", ids, expected_code=403)
    expected = [AnnotationStatus.rejected, AnnotationStatus.validated]
    assert_statuses(ids, expected)

    post_annotation_ids(client, "release", ids, expected_code=403)
    assert_statuses(ids, expected)

    post_annotation_ids(client, "reject", ids, expected_code=403)
    assert_statuses(ids, expected)

    post_annotation_ids(client, "validate", ids, expected_code=403)
    assert_statuses(ids, expected)


def test_action_by_id_not_allowed_same_state(cleanup_annotations, client):
    ids = insert_annotations(
        (1, 2, AnnotationStatus.released), (1, 2, AnnotationStatus.released)
    )
    post_annotation_ids(client, "release", ids, expected_code=403)
    expected = [AnnotationStatus.released, AnnotationStatus.released]
    assert_statuses(ids, expected)


def test_validate_write_validation_in_database(cleanup_annotations, client):
    ids = insert_annotations(
        (2, 2, AnnotationStatus.released), (2, 1, AnnotationStatus.released)
    )
    post_annotation_ids(client, "validate", ids)

    with connection_manager.get_db_session() as session:
        for id in ids:
            validation = (
                session.query(ValidationEvent).filter_by(annotation_id=id).scalar()
            )
            assert validation.validator_id == 1
            assert validation.validation_value == ValidationValue.validated


def test_validate_write_rejection_in_database(cleanup_annotations, client):
    ids = insert_annotations(
        (2, 2, AnnotationStatus.released), (2, 1, AnnotationStatus.released)
    )
    post_annotation_ids(client, "reject", ids)

    with connection_manager.get_db_session() as session:
        for id in ids:
            validation = (
                session.query(ValidationEvent).filter_by(annotation_id=id).scalar()
            )
            assert validation.validator_id == 1
            assert validation.validation_value == ValidationValue.rejected
