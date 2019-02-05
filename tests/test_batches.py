import pytest

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import Annotation, Batch, BatchItem, ValidationRules
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


@pytest.fixture
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
        session.add_all([make_annotation(3, "validated") for _ in range(100)])
        session.add_all([make_annotation(9, "validated") for _ in range(50)])
        session.commit()

        request.addfinalizer(delete_annotations)


@pytest.fixture
def basic_batch(request, insert_validated_annotations):
    with connection_manager.get_db_session() as session:
        val = ValidationRules(nb_validators=1, consensus=True)
        session.add(val)
        session.flush()
        batch = Batch(created_by=1, validation_rules_id=val.id)
        session.add(batch)
        session.flush()
        ids = session.query(Annotation.id)
        session.add_all([BatchItem(batch_id=batch.id, annotation_id=a, role="training") for a in ids])
        session.commit()

        def delete_batch():
            session.query(Batch).delete()
            session.commit()

        request.addfinalizer(delete_batch)


def test_batches_search_all(client, basic_batch):
    r = client.get(api_url(f"/batches"))
    assert len(r.json) == 1


def test_batches_get_by_id(client, basic_batch):
    id = 1
    r = client.get(api_url(f"/batches/{id}"))
    assert r.json['id'] == 1
    assert r.json['created_by'] == 1
