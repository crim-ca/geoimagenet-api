import json
from urllib.parse import urlencode

import requests
import sentry_sdk
from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import JSON, TEXT
from sqlalchemy import and_

from flask import Response, request

from geoimagenet_api.config import config
from geoimagenet_api.routes.taxonomy_classes import get_all_taxonomy_classes_ids
from geoimagenet_api.database.models import Annotation as DBAnnotation, AnnotationStatus
from geoimagenet_api.database.connection import connection_manager


def get_annotations(taxonomy_id):
    with connection_manager.get_db_session() as session:
        taxonomy_ids = get_all_taxonomy_classes_ids(session, taxonomy_id)

        query = session.query(
            cast(func.json_build_object(
                "type",
                "Feature",
                "geometry",
                cast(func.ST_AsGeoJSON(DBAnnotation.geometry), JSON),
                "properties",
                func.json_build_object(
                    "image_name",
                    DBAnnotation.image_name,
                    "taxonomy_class_id",
                    DBAnnotation.taxonomy_class_id,
                ),
            ), TEXT)
        ).filter(
            and_(
                DBAnnotation.status == AnnotationStatus.validated,
                DBAnnotation.taxonomy_class_id.in_(taxonomy_ids),
            )
        )

        # try to stream the geojson features from the database
        # so that the whole FeatureCollection is not built entirely in memory

        def geojson_stream():
            yield '{"type": "FeatureCollection", "features": ['
            n_features = query.count()
            for n, r in enumerate(query):
                yield r[0]
                if n != n_features - 1:
                    yield ","
            yield "]}"

        return Response(geojson_stream(), mimetype="application/json")


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
    query = urlencode({"taxonomy_id": taxonomy_id})
    url = f"{request.base_url}?{query}"

    forwarded_json = {"name": name, "geojson_url": url, "overwrite": overwrite}

    batch_url = _get_batch_creation_url(request)

    try:
        r = requests.post(batch_url, json=forwarded_json)
        r.raise_for_status()
    except requests.exceptions.RequestException:
        sentry_sdk.capture_exception()
        message = (
            "Could't forward the request to the batch creation service. "
            "This error was reported to the developers."
        )
        return message, 503

    return forwarded_json, 202
