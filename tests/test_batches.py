import json

import pp

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import Annotation
from tests.utils import api_url


def test_get_annotations(client):
    # ----- given
    with connection_manager.get_db_session() as session:
        some_annotations = []
        for _ in range(3):
            some_annotations.append(
                Annotation(
                    annotator_id=1,
                    geometry="SRID=3857;POLYGON((0 0,1 0,1 1,0 1,0 0))",
                    taxonomy_class_id=2,
                    image_name="my image",
                    status="validated",
                )
            )
            session.add(some_annotations[-1])
        session.commit()
        some_annotations_ids = [a.id for a in some_annotations]

    # ----- when
    query = {"taxonomy_id": 1}
    r = client.get(api_url("/batches"), query_string=query)

    # ----- then
    assert r.status_code == 200
    assert len(r.json["features"]) == 3
    first_feature = r.json["features"][0]
    assert "image_name" in first_feature["properties"]
    assert "taxonomy_class_id" in first_feature["properties"]

    # ----- cleanup
    with connection_manager.get_db_session() as session:
        session.query(Annotation).filter(
            Annotation.id.in_(some_annotations_ids)
        ).delete(synchronize_session=False)
        session.commit()


def test_post(client):
    # ----- when
    data = {"name": "test_batch", "taxonomy_id": 1, "overwrite": False}
    r = client.post(
        api_url("/batches"), content_type="application/json", data=json.dumps(data)
    )
    assert r.status_code == 201
    pp(r.json())
