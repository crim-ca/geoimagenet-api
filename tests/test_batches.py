import json
from unittest import mock

import pp
import requests

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
                    image_name="my imagéé",
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
    assert "crs" in r.json
    assert r.json["features"][0]["id"] == str(some_annotations_ids[0])
    first_feature = r.json["features"][0]
    assert "image_name" in first_feature["properties"]
    assert "taxonomy_class_id" in first_feature["properties"]

    # ----- cleanup
    with connection_manager.get_db_session() as session:
        session.query(Annotation).filter(
            Annotation.id.in_(some_annotations_ids)
        ).delete(synchronize_session=False)
        session.commit()


def test_get_annotations_load_testing(client_no_response_validation):
    # ----- given
    n_features = 10  # increase this number
    from time import perf_counter

    t = perf_counter()
    with connection_manager.get_db_session() as session:
        some_annotations = []
        for _ in range(n_features):
            some_annotations.append(
                Annotation(
                    annotator_id=1,
                    geometry="SRID=3857;POLYGON((0.001 0.001,1.001 0.001,1.001 1.001,0.001 1.001,0.001 0.001))",
                    taxonomy_class_id=2,
                    image_name="my image",
                    status="validated",
                )
            )
        session.bulk_save_objects(some_annotations)
        session.commit()
        some_annotations_ids = [a.id for a in some_annotations]

    # print(f"{perf_counter() - t:.2f}")
    t = perf_counter()

    # ----- when
    query = {"taxonomy_id": 1}
    r = client_no_response_validation.get(api_url("/batches"), query_string=query)
    _ = r.json  # consume the streamed json

    # ----- then
    # print(f"{perf_counter() - t:.2f}")
    assert r.status_code == 200
    assert len(r.json["features"]) == n_features

    # ----- cleanup
    with connection_manager.get_db_session() as session:
        session.query(Annotation).filter(
            Annotation.id.in_(some_annotations_ids)
        ).delete(synchronize_session=False)
        session.commit()


def test_mock_post(client):
    # ----- given
    data = {"name": "test_batch", "taxonomy_id": 1, "overwrite": False}

    with mock.patch("geoimagenet_api.routes.batches.requests") as mock_requests:
        mock_requests.exceptions.RequestException = requests.exceptions.RequestException
        response = mock.Mock()
        response.raise_for_status.return_value = None
        mock_requests.post.return_value = response
        batches_url = "http://localhost/ml/processes/batch-creation/jobs"
        execute = {
            "inputs": [
                {"id": "name", "value": data["name"]},
                {
                    "id": "geojson_url",
                    "href": "http://localhost/api/v1/batches?taxonomy_id=1",
                },
                {"id": "overwrite", "value": data["overwrite"]},
            ],
            "outputs": [],
        }

        # ----- when
        r = client.post(
            api_url("/batches"), content_type="application/json", data=json.dumps(data)
        )

        # ----- then
        assert r.status_code == 202
        mock_requests.post.assert_called_with(batches_url, json=execute)


def test_mock_post_failure(client):
    # ----- given
    data = {"name": "test_batch", "taxonomy_id": 1, "overwrite": False}

    # ----- when
    # it's faster to mock the exception than to let it raise an error
    with mock.patch("geoimagenet_api.routes.batches.requests") as mock_requests:
        mock_requests.exceptions.RequestException = requests.exceptions.RequestException
        mock_requests.post.side_effect = requests.exceptions.HTTPError
        r = client.post(
            api_url("/batches"), content_type="application/json", data=json.dumps(data)
        )

    # ----- then
    assert r.status_code == 503


def test_post_404(client):
    # ----- given
    data = {"name": "test_batch", "taxonomy_id": 9999, "overwrite": False}

    # ----- when
    r = client.post(
        api_url("/batches"), content_type="application/json", data=json.dumps(data)
    )

    # ----- then
    assert r.status_code == 404


def test_get_404(client):
    # ----- when
    query = {"taxonomy_id": 9999}
    r = client.get(api_url("/batches"), query_string=query)

    # ----- then
    assert r.status_code == 404
