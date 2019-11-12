from collections import defaultdict
from datetime import datetime
from typing import Tuple, Dict, Union, List

import psycopg2
import psycopg2.extras
import sqlalchemy.exc
from fastapi import APIRouter, Query, Body
from sqlalchemy import and_, or_
from sqlalchemy.sql import func
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from geoimagenet_api.endpoints.images import (
    image_id_from_image_name,
    image_id_from_properties,
)
from geoimagenet_api.endpoints.users import get_logged_user_id
from geoimagenet_api.openapi_schemas import (
    AnnotationCountByStatus,
    GeoJsonFeature,
    GeoJsonFeatureCollection,
    AnnotationRequestReview,
    AnnotationStatusUpdateIds,
    AnnotationStatusUpdateTaxonomyClass,
    AnyGeojsonGeometry,
)
from geoimagenet_api.database.models import (
    Annotation as DBAnnotation,
    AnnotationStatus,
    TaxonomyClass as DBTaxonomyClass,
    ValidationEvent,
    ValidationValue,
    Image,
    Person,
)
from geoimagenet_api.endpoints.taxonomy_classes import (
    flatten_taxonomy_classes_ids,
    get_taxonomy_classes_tree,
    get_all_taxonomy_classes_ids,
)
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import geojson_stream

from .utils import record_validation_events, get_annotation_ids_integers


router = APIRouter()


def _ensure_annotations_exists(annotation_ids: List[int]):
    """Makes sure the requested annotation ids, else return a 404 response."""
    with connection_manager.get_db_session() as session:
        ids_exists = session.query(DBAnnotation.id).filter(
            DBAnnotation.id.in_(annotation_ids)
        )

        count_not_found = len(
            set(annotation_ids).difference((o[0] for o in ids_exists))
        )
        if count_not_found:
            raise HTTPException(
                404, f"{count_not_found} annotation ids could not be found."
            )


def _ensure_annotation_owner(annotation_ids: List[int], logged_user: int):
    """Makes sure the requested annotation ids belong to the logged in user, else return a 403 response."""
    with connection_manager.get_db_session() as session:
        count_not_owned = (
            session.query(DBAnnotation.id)
            .filter(
                and_(
                    DBAnnotation.id.in_(annotation_ids),
                    DBAnnotation.annotator_id != logged_user,
                )
            )
            .count()
        )

        if count_not_owned:
            raise HTTPException(
                403,
                f"{count_not_owned} annotation ids are not owned by the logged in user.",
            )


allowed_status_transitions = {
    # (from_status, to_status, only_logged_user)
    (AnnotationStatus.new, AnnotationStatus.deleted, True),
    (AnnotationStatus.new, AnnotationStatus.released, True),
    (AnnotationStatus.released, AnnotationStatus.rejected, False),
    (AnnotationStatus.released, AnnotationStatus.validated, False),
}


status_update_type = Union[
    AnnotationStatusUpdateIds, AnnotationStatusUpdateTaxonomyClass
]


def _update_status(
    update_info: status_update_type, desired_status: AnnotationStatus, request: Request
):
    """Update annotations statuses based on filters provided in update_info and allowed transitions."""
    logged_user_id = get_logged_user_id(request)

    with connection_manager.get_db_session() as session:

        def _filter_for_allowed_transitions(query, desired_status):
            filters = []
            for from_status, to_status, only_logged_user in allowed_status_transitions:
                if to_status == desired_status:
                    status_filter = DBAnnotation.status == from_status
                    if only_logged_user:
                        filters.append(
                            and_(
                                DBAnnotation.annotator_id == logged_user_id,
                                status_filter,
                            )
                        )
                    else:
                        filters.append(status_filter)

            return query.filter(or_(*filters))

        def _filter_annotation_ids(query) -> Union[Query, Tuple]:
            annotation_ids = get_annotation_ids_integers(update_info.annotation_ids)

            existing_ids = session.query(DBAnnotation.id).filter(
                DBAnnotation.id.in_(annotation_ids)
            )
            existing_ids = [a.id for a in existing_ids]
            missing_ids = set(annotation_ids).difference(existing_ids)
            if missing_ids:
                raise HTTPException(
                    404, f"Annotation ids not found: {', '.join(map(str, missing_ids))}"
                )

            query = query.filter(DBAnnotation.id.in_(annotation_ids))

            count_to_update = query.count()
            count_requested = len(annotation_ids)
            if count_to_update < count_requested:
                # some annotation ids were not in a good state and
                # a wrong transition was requested
                raise HTTPException(
                    403,
                    "Status update refused. One or more status transition not allowed.",
                )

            return query

        def _filter_taxonomy_ids(query) -> Union[Query, Tuple]:
            taxonomy_class_id = update_info.taxonomy_class_id
            taxonomy_id = (
                session.query(DBTaxonomyClass.id)
                .filter_by(id=taxonomy_class_id)
                .first()
            )
            if not taxonomy_id:
                raise HTTPException(
                    404, f"Taxonomy class id not found: {taxonomy_class_id}"
                )
            if update_info.with_taxonomy_children:
                taxonomy_ids = get_all_taxonomy_classes_ids(session, taxonomy_class_id)
            else:
                taxonomy_ids = [taxonomy_class_id]
            return query.filter(DBAnnotation.taxonomy_class_id.in_(taxonomy_ids))

        query = session.query(DBAnnotation)
        query = _filter_for_allowed_transitions(query, desired_status)

        if isinstance(update_info, AnnotationStatusUpdateIds):
            query = _filter_annotation_ids(query)
        else:
            query = _filter_taxonomy_ids(query)

        record_validation_events(session, desired_status, logged_user_id, query)

        query.update({DBAnnotation.status: desired_status}, synchronize_session=False)

        session.commit()

    return Response(status_code=204)


@router.post("/annotations/release", status_code=204, summary="Release")
def update_status_release(request: Request, update: status_update_type = Body(...)):
    return _update_status(update, AnnotationStatus.released, request)


@router.post("/annotations/validate", status_code=204, summary="Validate")
def update_status_validate(request: Request, update: status_update_type = Body(...)):
    return _update_status(update, AnnotationStatus.validated, request)


@router.post("/annotations/reject", status_code=204, summary="Reject")
def update_status_reject(request: Request, update: status_update_type = Body(...)):
    return _update_status(update, AnnotationStatus.rejected, request)


@router.post("/annotations/delete", status_code=204, summary="Delete")
def update_status_delete(request: Request, update: status_update_type = Body(...)):
    return _update_status(update, AnnotationStatus.deleted, request)


@router.post("/annotations/request_review", status_code=204, summary="Request review")
def request_review(body: AnnotationRequestReview, request: Request):
    """Set the 'review_requested' field for a list of annotations"""
    logged_user_id = get_logged_user_id(request)

    annotation_ids = get_annotation_ids_integers(body.annotation_ids)

    _ensure_annotations_exists(annotation_ids)
    _ensure_annotation_owner(annotation_ids, logged_user_id)

    with connection_manager.get_db_session() as session:
        (
            session.query(DBAnnotation)
            .filter(DBAnnotation.id.in_(annotation_ids))
            .update(
                {DBAnnotation.review_requested: body.boolean}, synchronize_session=False
            )
        )
        session.commit()

    return Response(status_code=204)
