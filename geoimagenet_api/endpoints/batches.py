import json
from urllib.parse import urlencode

import requests
import sentry_sdk
from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import TEXT
from sqlalchemy import and_

from flask import Response, request

from geoimagenet_api.config import config
from geoimagenet_api.endpoints.taxonomy_classes import get_all_taxonomy_classes_ids
from geoimagenet_api.database.models import (
    Annotation as DBAnnotation,
    AnnotationStatus,
    Taxonomy,
)
from geoimagenet_api.database.connection import connection_manager


def get_annotations(taxonomy_id):
    if not _is_taxonomy_id_valid(taxonomy_id):
        return "taxonomy_id not found", 404

    with connection_manager.get_db_session() as session:

        taxonomy_ids = get_all_taxonomy_classes_ids(session, taxonomy_id)

        query = session.query(
            DBAnnotation.id,
            func.ST_AsGeoJSON(DBAnnotation.geometry).label("geometry"),
            DBAnnotation.image_name,
            DBAnnotation.taxonomy_class_id,
        )

        query = query.filter(
            and_(
                DBAnnotation.status == AnnotationStatus.validated,
                DBAnnotation.taxonomy_class_id.in_(taxonomy_ids),
            )
        )

        # Stream the geojson features from the database
        # so that the whole FeatureCollection is not built entirely in memory.
        # The bulk of the json serialization (the geometries) takes place in the database
        # doing all the serialization in the database is a very small
        # performance improvement and I prefer to build the json in python than in sql.
        def geojson_stream():
            feature_collection = json.dumps(
                {
                    "type": "FeatureCollection",
                    "crs": {"type": "EPSG", "properties": {"code": 3857}},
                    "features": [],
                }
            )
            before_ending_brackets = feature_collection[:-2]
            ending_brackets = feature_collection[-2:]

            yield before_ending_brackets
            first_result = True
            for r in query:
                if not first_result:
                    yield ","
                else:
                    first_result = False

                data = json.dumps(
                    {
                        "type": "Feature",
                        "geometry": "__geometry",
                        "id": f"annotation.{r.id}",
                        "properties": {
                            "image_name": r.image_name,
                            "taxonomy_class_id": r.taxonomy_class_id,
                        },
                    }
                )
                # geometry is already serialized
                yield data.replace('"__geometry"', r.geometry)

            yield ending_brackets

        return Response(geojson_stream(), mimetype="application/json")


def _is_taxonomy_id_valid(taxonomy_id):
    with connection_manager.get_db_session() as session:
        return bool(session.query(Taxonomy).filter_by(id=taxonomy_id).first())


def _get_batch_creation_url(request):
    """Returns the base url for batches creation requests.

    If the `batches_creation_url` configuration is a path,
    the request.host_url is prepended.
    This is for cases when the process is running on the same host.

    for example: https://127.0.0.1/ml/processes/batch-creation/jobs
    """
    batches_url = config.get("batch_creation_url", str).strip("/")
    if not batches_url.startswith("http"):
        base = request.host_url
        path = batches_url.strip("/")
        batches_url = f"{base}{path}"

    return batches_url


def post():
    name = request.json["name"]
    taxonomy_id = request.json["taxonomy_id"]
    overwrite = request.json.get("overwrite", False)

    if not _is_taxonomy_id_valid(taxonomy_id):
        return "taxonomy_id not found", 404

    query = urlencode({"taxonomy_id": taxonomy_id})
    url = f"{request.base_url}?{query}"

    execute = {
        "inputs": [
            {"id": "name", "value": name},
            {"id": "geojson_url", "href": url},
            {"id": "overwrite", "value": overwrite},
        ],
        "outputs": [],
    }

    batch_url = _get_batch_creation_url(request)

    try:
        r = requests.post(batch_url, json=execute)
        r.raise_for_status()
    except requests.exceptions.RequestException:
        sentry_sdk.capture_exception()
        message = (
            "Could't forward the request to the batch creation service. "
            "This error was reported to the developers."
        )
        return message, 503

    return execute, 202
