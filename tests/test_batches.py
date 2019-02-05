import pytest

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


@pytest.fixture(scope='module')
def insert_validated_annotations(request):
    """
    Taxonomy classes tree:
    1
    --2
      --3
    --9
    """
    with connection_manager.get_db_session() as session:

        def delete_annotations():
            session.query(Annotation).delete()
            session.commit()

        delete_annotations()
        session.bulk_save_objects([make_annotation(3, "validated") for _ in range(20)])
        session.bulk_save_objects([make_annotation(9, "validated") for _ in range(15)])
        session.commit()

        request.addfinalizer(delete_annotations)


@pytest.fixture(scope='module')
def basic_batch(request, insert_validated_annotations):
    with connection_manager.get_db_session() as session:
        val_id = session.query(ValidationRules.id).filter_by(nb_validators=1, consensus=True).scalar()
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

        request.addfinalizer(delete_batch)


def test_batches_get_batches(client, basic_batch):
    r = client.get(api_url(f"/batches"))
    assert len(r.json) == 1

    id = 1
    r = client.get(api_url(f"/batches/{id}"))
    assert r.json["id"] == 1
    assert r.json["created_by"] == 1


def test_batches_get_training(client, basic_batch):
    expected = {3: {"training": 18, "testing": 2}, 9: {"training": 14, "testing": 1}}

    id = 1
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
