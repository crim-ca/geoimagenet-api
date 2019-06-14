import datetime

from fastapi import APIRouter
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import StreamingResponse
import requests
import sentry_sdk
from sqlalchemy import func, and_

from geoimagenet_api.config import config
from geoimagenet_api.endpoints.image import query_rgbn_16_bit_image
from geoimagenet_api.endpoints.taxonomy import get_latest_taxonomy_ids
from geoimagenet_api.endpoints.taxonomy_classes import get_all_taxonomy_classes_ids
from geoimagenet_api.database.models import (
    Annotation as DBAnnotation,
    AnnotationStatus,
    Taxonomy
)
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.openapi_schemas import (
    GeoJsonFeatureCollection,
    BatchPost,
    BatchPostForwarded,
    ExecuteIOHref,
    ExecuteIOValue,
    BatchPostResult)
from geoimagenet_api.utils import geojson_stream, get_config_url

router = APIRouter()


@router.get(
    "/batches/annotations",
    response_model=GeoJsonFeatureCollection,
    summary="Get validated annotations",
)
def get_annotations():
    """Get annotations for the latest taxonomy version."""

    latest_taxonomy_ids = get_latest_taxonomy_ids()

    with connection_manager.get_db_session() as session:

        taxonomy_ids = []
        for taxonomy_id in latest_taxonomy_ids.values():
            taxonomy_ids += get_all_taxonomy_classes_ids(session, taxonomy_id)

        subquery = query_rgbn_16_bit_image(session)

        query = session.query(
            DBAnnotation.id,
            func.ST_AsGeoJSON(DBAnnotation.geometry).label("geometry"),
            subquery.c.image_name,
            DBAnnotation.taxonomy_class_id,
        ).outerjoin(subquery, subquery.c.image_id == DBAnnotation.image_id).filter(
            and_(
                DBAnnotation.status == AnnotationStatus.validated,
                DBAnnotation.taxonomy_class_id.in_(taxonomy_ids),
            )
        )

        properties = ["image_name", "taxonomy_class_id"]
        stream = geojson_stream(query, properties=properties, with_geometry=True)

        return StreamingResponse(stream, media_type="application/json")


post_description = (
    "Forwards information to the batch creation process. On success, "
    "the returned body is the same as the one forwarded to the batch "
    "creation service."
)


@router.post(
    "/batches",
    response_model=BatchPostResult,
    status_code=202,
    summary="Create",
    description=post_description,
)
def post(batch_post: BatchPost, request: Request):

    url = f"{request.url}/annotations"

    name = datetime.datetime.now().strftime("%Y-%m-%d")

    execute = BatchPostForwarded(
        inputs=[
            ExecuteIOValue(id="name", value=name),
            ExecuteIOHref(id="geojson_url", href=url),
            ExecuteIOValue(id="overwrite", value=batch_post.overwrite),
        ],
        outputs=[],
    )

    batch_url = get_config_url(request, "batch_creation_url")

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

    result = BatchPostResult(sent_to_ml=execute, response_from_ml=r.json())
    return result
