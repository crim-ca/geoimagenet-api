from typing import List, Union, Tuple

from fastapi import APIRouter, HTTPException

from geoimagenet_api.database.models import (
    ValidationEvent,
    ValidationValue,
)
from geoimagenet_api.openapi_schemas import (
    GeoJsonFeature,
    GeoJsonFeatureCollection,
    AnnotationStatus,
)

DEFAULT_SRID = 3857


def geojson_features_from_body(
    body: Union[GeoJsonFeature, GeoJsonFeatureCollection]
) -> List[GeoJsonFeature]:
    """Basic helper function to support a FeatureCollection and a single feature."""
    if isinstance(body, GeoJsonFeatureCollection):
        features = body.features
    else:
        features = [body]
    return features


def get_annotation_ids_integers(annotation_ids: List[str]) -> Union[List[int], Tuple]:
    """For annotation ids of the format 'annotation.1234', return a list of annotation ids integers"""
    try:
        annotation_ids = [int(i.split(".")[-1]) for i in annotation_ids]
    except ValueError:
        raise HTTPException(
            400, "Annotation ids must be of the format: layer_name.123456"
        )
    return annotation_ids


def record_validation_events(session, desired_status, user_id, query):
    # record validation events
    if desired_status in (AnnotationStatus.validated, AnnotationStatus.rejected):
        validation_value = {
            AnnotationStatus.validated: ValidationValue.validated,
            AnnotationStatus.rejected: ValidationValue.rejected,
        }
        session.bulk_save_objects(
            [
                ValidationEvent(
                    annotation_id=annotation.id,
                    validator_id=user_id,
                    validation_value=validation_value[desired_status],
                )
                for annotation in query
            ]
        )

