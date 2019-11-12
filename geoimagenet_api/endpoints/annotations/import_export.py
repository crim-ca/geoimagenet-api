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

from .utils import (
    DEFAULT_SRID,
    geojson_features_from_body,
    record_validation_events,
)
from .annotations import post_annotations


router = APIRouter()


@router.post(
    "/annotations/datasets",
    response_model=Dict[str, int],
    status_code=200,
    summary="Dataset",
    description="Batch import a dataset from an external source (not another "
    "GeoImageNet instance) keeping the provided annotator_id"
    "This route should be reserved for administrators.",
)
def post_datasets(
    request: Request,
    body: Union[GeoJsonFeature, GeoJsonFeatureCollection] = Body(...),
    srid: int = DEFAULT_SRID,
):
    logged_user_id = get_logged_user_id(request)

    total_annotations = len(geojson_features_from_body(body))
    annotation_ids = post_annotations(
        request, body, srid, trust_annotator_id=True, raise_outside_image=False
    )

    with connection_manager.get_db_session() as session:
        query_annotation_ids = session.query(DBAnnotation).filter(
            DBAnnotation.id.in_(annotation_ids)
        )

        query_annotation_ids.update(
            {DBAnnotation.status: AnnotationStatus.pre_released},
            synchronize_session=False,
        )
        session.commit()

        # reject annotations that don't have an image
        query_annotation_ids.filter(DBAnnotation.image_id == None).update(
            {DBAnnotation.status: AnnotationStatus.rejected}, synchronize_session=False
        )
        session.commit()

        # release annotations that are on an image
        query_annotation_ids.filter(DBAnnotation.image_id != None).update(
            {DBAnnotation.status: AnnotationStatus.released}, synchronize_session=False
        )
        session.commit()

        accepted_annotations = (
            session.query(func.count(DBAnnotation.id))
            .filter(DBAnnotation.id.in_(annotation_ids))
            .filter(DBAnnotation.image_id != None)
            .scalar()
        )

        rejected_annotations_query = (
            session.query(DBAnnotation.id)
            .filter(DBAnnotation.id.in_(annotation_ids))
            .filter(DBAnnotation.image_id == None)
            .all()
        )
        rejected_annotations = len(rejected_annotations_query)
        if rejected_annotations:
            record_validation_events(
                session,
                AnnotationStatus.rejected,
                logged_user_id,
                rejected_annotations_query,
            )
            session.commit()

    return {
        "total_annotations": total_annotations,
        "accepted_annotations": accepted_annotations,
        "rejected_annotations": rejected_annotations,
    }


@router.post(
    "/annotations/import",
    response_model=List[int],
    status_code=201,
    summary="Import",
    description="Import annotations from another GeoImageNet instance keeping "
    "the provided status or permissions. "
    "This route should be reserved for administrators.",
)
def post_import(
    request: Request,
    body: Union[GeoJsonFeature, GeoJsonFeatureCollection] = Body(...),
    srid: int = DEFAULT_SRID,
):
    return post_annotations(request, body, srid, trust_status=True)

