import json
import random
from unittest import mock
import pytest

import requests

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import Annotation, AnnotationStatus
from .test_annotations import write_annotation, _clean_annotation_session
from .test_images import pleiades_images


def test_get_annotations(client):
    with _clean_annotation_session() as session:
        # ----- given
        some_annotations_ids = []
        for _ in range(3):
            a = write_annotation(
                session=session,
                user_id=1,
                status=AnnotationStatus.validated,
                image_id=2,
            )
            some_annotations_ids.append(a.id)

        # ----- when
        query = {"taxonomy_id": 1}
        r = client.get("/batches", params=query)

        # ----- then
        assert r.status_code == 200
        assert len(r.json()["features"]) == 3
        assert "crs" in r.json()
        ids = set(f["id"] for f in r.json()["features"])
        expected_ids = set(f"annotation.{i}" for i in some_annotations_ids)
        assert ids == expected_ids
        first_feature = r.json()["features"][0]
        assert "image_name" in first_feature["properties"]
        assert "taxonomy_class_id" in first_feature["properties"]
        image_names = [f["properties"]["image_name"] for f in r.json()["features"]]
        assert image_names == [None, None, None]


def test_get_annotation_images_16_bits(client, pleiades_images):
    with _clean_annotation_session() as session:
        # ----- given
        random_image = random.choice([i for i in pleiades_images if i.bits == 8])
        write_annotation(
            session=session,
            user_id=1,
            status=AnnotationStatus.validated,
            image_id=random_image.id,
        )

        # ----- when
        query = {"taxonomy_id": 1}
        r = client.get("/batches", params=query)

        image_names = [f["properties"]["image_name"] for f in r.json()["features"]]
        assert len(r.json()["features"]) == 1
        assert (
            image_names[0]
            == f"PLEIADES_RGBN_16/{random_image.filename.replace('8bits', '16bits')}"
        )


@pytest.mark.skip(msg="only for load testing purposes")
def test_get_annotations_load_testing(client):
    # ----- given
    n_features = 10  # increase this number
    from time import perf_counter

    with connection_manager.get_db_session() as session:
        some_annotations = []
        for _ in range(n_features):
            some_annotations.append(
                Annotation(
                    annotator_id=1,
                    geometry="SRID=3857;POLYGON((0.001 0.001,1.001 0.001,1.001 1.001,0.001 1.001,0.001 0.001))",
                    taxonomy_class_id=2,
                    image_id=1,
                    status="validated",
                )
            )
        session.bulk_save_objects(some_annotations)
        session.commit()

    # print(f"{perf_counter() - t:.2f}")
    t = perf_counter()

    # ----- when
    query = {"taxonomy_id": 1}
    r = client.get("/batches", params=query)
    _ = r.json()  # consume the streamed json

    # ----- then
    # print(f"{perf_counter() - t:.2f}")
    assert r.status_code == 200
    assert len(r.json()["features"]) == n_features

    # ----- cleanup
    with connection_manager.get_db_session() as session:
        session.query(Annotation).delete()
        session.commit()


def test_mock_post(client):
    # ----- given
    data = {"name": "test_batch", "taxonomy_id": 1, "overwrite": "False"}

    with mock.patch("geoimagenet_api.endpoints.batches.requests") as mock_requests:
        mock_requests.exceptions.RequestException = requests.exceptions.RequestException
        response = mock.Mock()
        response.raise_for_status.return_value = None
        mock_requests.post.return_value = response
        batches_url = "http://testserver/batches/ml/processes/batch-creation/jobs"
        execute = {
            "inputs": [
                {"id": "name", "value": data["name"]},
                {
                    "id": "geojson_url",
                    "href": "http://testserver/batches?taxonomy_id=1",
                },
                {"id": "overwrite", "value": data["overwrite"]},
            ],
            "outputs": [],
        }

        # ----- when
        r = client.post("/batches", json=data)

        # ----- then
        assert r.status_code == 202
        mock_requests.post.assert_called_with(batches_url, json=json.dumps(execute))


def test_mock_post_failure(client):
    # ----- given
    data = {"name": "test_batch", "taxonomy_id": 1, "overwrite": False}

    # ----- when
    # it's faster to mock the exception than to let it raise an error
    with mock.patch("geoimagenet_api.endpoints.batches.requests") as mock_requests:
        mock_requests.exceptions.RequestException = requests.exceptions.RequestException
        mock_requests.post.side_effect = requests.exceptions.HTTPError
        r = client.post("/batches", json=data)

    # ----- then
    assert r.status_code == 503


def test_post_404(client):
    # ----- given
    data = {"name": "test_batch", "taxonomy_id": 9999, "overwrite": False}

    # ----- when
    r = client.post("/batches", json=data)

    # ----- then
    assert r.status_code == 404


def test_get_404(client):
    # ----- when
    query = {"taxonomy_id": 9999}
    r = client.get("/batches", params=query)

    # ----- then
    assert r.status_code == 404
