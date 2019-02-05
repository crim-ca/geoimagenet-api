import pytest
from sqlalchemy import func

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import (
    Annotation,
    Batch,
    BatchItem,
    ValidationRules,
)
from tests.utils import api_url


def make_annotation(taxonomy_class, status):
    annotation = Annotation(
        annotator_id=1,
        geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
        taxonomy_class_id=taxonomy_class,
        image_name="my image",
        status=status,
    )
    return annotation


def insert_validated_annotations():
    """
    Taxonomy classes tree:
    1
    --2
      --3
    --9
    """
    insertions = {
        3: 20,
        9: 15,
    }
    with connection_manager.get_db_session() as session:
        for class_, count in insertions.items():
            session.bulk_save_objects([make_annotation(class_, "validated") for _ in range(count)])
        session.commit()


def delete_all_annotations():
    with connection_manager.get_db_session() as session:
        session.query(Annotation).delete()
        session.commit()


@pytest.fixture
def basic_batch(request):
    insert_validated_annotations()

    with connection_manager.get_db_session() as session:
        val_id = (
            session.query(ValidationRules.id)
            .filter_by(nb_validators=1, consensus=True)
            .scalar()
        )
        batch = Batch(created_by=1, taxonomy_id=1, validation_rules_id=val_id)
        session.add(batch)
        session.flush()
        ids_3 = session.query(Annotation.id).filter_by(taxonomy_class_id=3)
        ids_9 = session.query(Annotation.id).filter_by(taxonomy_class_id=9)
        batch_items = []
        for ids in [ids_3, ids_9]:
            for n, id_ in enumerate(ids):
                role = "testing" if n % 10 == 9 else "training"
                item = BatchItem(batch_id=batch.id, annotation_id=id_, role=role)
                batch_items.append(item)

        session.bulk_save_objects(batch_items)
        session.commit()

        def delete_batch():
            session.query(Batch).delete()
            session.commit()
            delete_all_annotations()

        request.addfinalizer(delete_batch)


def test_batches_get_batches(client, basic_batch):
    r = client.get(api_url(f"/batches"))
    assert len(r.json) == 1

    id = r.json[0]["id"]
    r = client.get(api_url(f"/batches/{id}"))
    assert r.json["id"] == 1
    assert r.json["created_by"] == 1


def test_batches_get_by_role(client, basic_batch):
    r = client.get(api_url(f"/batches"))
    assert len(r.json) == 1

    expected = {3: {"training": 18, "testing": 2}, 9: {"training": 14, "testing": 1}}

    id = r.json[0]["id"]
    r = client.get(api_url(f"/batches/{id}/items/training"))

    assert r.status_code == 200
    for batch_items in r.json:
        class_id = batch_items["taxonomy_class_id"]
        geometry_count = len(batch_items["geometries"]["coordinates"])
        assert geometry_count == expected[class_id]["training"]

    r = client.get(api_url(f"/batches/{id}/items/testing"))

    assert r.status_code == 200
    for batch_items in r.json:
        class_id = batch_items["taxonomy_class_id"]
        geometry_count = len(batch_items["geometries"]["coordinates"])
        assert geometry_count == expected[class_id]["testing"]


def test_post_batch_single(client):
    insert_validated_annotations()

    query = {"taxonomy_id": 1}

    r = client.post(api_url(f"/batches"), query_string=query)
    assert r.status_code == 201

    batch_id = r.json

    with connection_manager.get_db_session() as session:
        created_batch = session.query(Batch.id).filter_by(id=batch_id)
        created_items = (
            session.query(
                BatchItem.role,
                Annotation.taxonomy_class_id,
                func.count(BatchItem.annotation_id),
            )
            .filter(BatchItem.batch_id == batch_id)
            .join(Annotation)
            .group_by(BatchItem.role, Annotation.taxonomy_class_id)
        )
        expected = [
            ("testing", 3, 2),
            ("training", 3, 18),
            ("testing", 9, 1),
            ("training", 9, 14),
        ]
        for role, taxo_id, count in created_items:
            assert (role, taxo_id, count) in expected

        created_batch.delete()
        session.commit()

    delete_all_annotations()


def test_post_batch_incremental(client):
    insert_validated_annotations()

    query = {"taxonomy_id": 1}

    r = client.post(api_url(f"/batches"), query_string=query)
    assert r.status_code == 201
    first_batch_id = r.json

    # add more annotations
    with connection_manager.get_db_session() as session:
        # add more validated annotations
        session.bulk_save_objects([make_annotation(3, "validated") for _ in range(40)])
        session.bulk_save_objects([make_annotation(9, "validated") for _ in range(40)])
        session.bulk_save_objects([make_annotation(2, "validated") for _ in range(10)])
        session.commit()

    # create a second batch
    r = client.post(api_url(f"/batches"), query_string=query)
    assert r.status_code == 201
    batch_id = r.json
    assert batch_id == first_batch_id + 1

    with connection_manager.get_db_session() as session:
        created_batch = session.query(Batch.id).filter_by(id=batch_id)
        created_items = (
            session.query(
                BatchItem.role,
                Annotation.taxonomy_class_id,
                func.count(BatchItem.annotation_id),
            )
            .filter(BatchItem.batch_id == batch_id)
            .join(Annotation)
            .group_by(BatchItem.role, Annotation.taxonomy_class_id)
        )
        expected = [
            ("testing", 2, 1),
            ("training", 2, 9),
            ("testing", 3, 6),
            ("training", 3, 54),
            ("testing", 9, 5),
            ("training", 9, 50),
        ]
        for role, taxo_id, count in created_items:
            assert (role, taxo_id, count) in expected

        created_batch.delete()
        session.query(Batch.id).filter_by(id=first_batch_id).delete()
        session.commit()

    delete_all_annotations()
