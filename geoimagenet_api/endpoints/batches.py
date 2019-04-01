import json
from urllib.parse import urlencode

from fastapi import APIRouter
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import StreamingResponse
import requests
import sentry_sdk
from sqlalchemy import func, and_

from geoimagenet_api.config import config
from geoimagenet_api.endpoints.taxonomy_classes import get_all_taxonomy_classes_ids
from geoimagenet_api.database.models import (
    Annotation as DBAnnotation,
    AnnotationStatus,
    Taxonomy,
)
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.openapi_schemas import (
    GeoJsonFeatureCollection,
    BatchPost,
    BatchPostForwarded,
    ExecuteIOHref,
    ExecuteIOValue,
)

router = APIRouter()


@router.get(
    "/", response_model=GeoJsonFeatureCollection, summary="Get validated annotations"
)
def get_annotations(taxonomy_id: int):
    if not _is_taxonomy_id_valid(taxonomy_id):
        raise HTTPException(404, "taxonomy_id not found")

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
        async def geojson_stream():
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

        return StreamingResponse(geojson_stream(), media_type="application/json")


def _is_taxonomy_id_valid(taxonomy_id):
    with connection_manager.get_db_session() as session:
        return bool(session.query(Taxonomy).filter_by(id=taxonomy_id).first())


def _get_batch_creation_url(request: Request):
    """Returns the base url for batches creation requests.

    If the `batches_creation_url` configuration is a path,
    the request.host_url is prepended.
    This is for cases when the process is running on the same host.

    for example: https://127.0.0.1/ml/processes/batch-creation/jobs
    """
    batches_url = config.get("batch_creation_url", str).strip("/")
    if not batches_url.startswith("http"):
        path = batches_url.strip("/")
        batches_url = f"{request.url}{path}"

    return batches_url


post_description = (
    "Forwards information to the batch creation process. On success, "
    "the returned body is the same as the one forwarded to the batch "
    "creation service."
)


@router.post(
    "/",
    response_model=BatchPostForwarded,
    status_code=202,
    summary="Create",
    description=post_description,
)
def post(batch_post: BatchPost, request: Request):
    if not _is_taxonomy_id_valid(batch_post.taxonomy_id):
        raise HTTPException(404, "Taxonomy_id not found")

    query = urlencode({"taxonomy_id": batch_post.taxonomy_id})
    url = f"{request.url}?{query}"

    execute = BatchPostForwarded(
        inputs=[
            ExecuteIOValue(id="name", value=batch_post.name),
            ExecuteIOHref(id="geojson_url", href=url),
            ExecuteIOValue(id="overwrite", value=batch_post.overwrite),
        ],
        outputs=[],
    )

    batch_url = _get_batch_creation_url(request)

    try:
        r = requests.post(batch_url, json=execute.json())
        r.raise_for_status()
    except requests.exceptions.RequestException:
        sentry_sdk.capture_exception()
        message = (
            "Could't forward the request to the batch creation service. "
            "This error was reported to the developers."
        )
        raise HTTPException(503, message)

    return execute
