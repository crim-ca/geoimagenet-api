from collections import defaultdict
from typing import Tuple, Dict, Union, List

from fastapi import APIRouter
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
from starlette.exceptions import HTTPException
from starlette.requests import Request

from geoimagenet_api.openapi_schemas import (
    AnnotationProperties,
    AnnotationCountByStatus,
    AnnotationStatusUpdate,
    GeoJsonFeature,
    GeoJsonFeatureCollection,
    GeoJsonGeometry,
    AnnotationRequestReview,
)
from geoimagenet_api.database.models import (
    Annotation as DBAnnotation,
    AnnotationStatus,
    TaxonomyClass as DBTaxonomyClass,
    ValidationEvent,
    ValidationValue,
)
from geoimagenet_api.endpoints.taxonomy_classes import (
    flatten_taxonomy_classes_ids,
    get_taxonomy_classes_tree,
    get_all_taxonomy_classes_ids,
)
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import get_logged_user

DEFAULT_SRID = 3857

router = APIRouter()


def _geojson_features_from_body(
    body: Union[GeoJsonFeature, GeoJsonFeatureCollection]
) -> List[GeoJsonFeature]:
    """Basic helper function to support a FeatureCollection and a single feature."""
    if isinstance(body, GeoJsonFeatureCollection):
        features = body.features
    else:
        features = [body]
    return features


def _serialize_geometry(geometry: GeoJsonGeometry, crs: int):
    """Takes a dict geojson geometry, and prepares it to  be written to the db.

    It transforms the geometry into the DEFAULT_CRS if necessary."""
    geom_string = geometry.json()
    geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_string), crs)
    if crs != DEFAULT_SRID:
        geom = func.ST_Transform(geom, DEFAULT_SRID)
    return geom


@router.put("/", status_code=204, summary="Modify")
def put(
    body: Union[GeoJsonFeature, GeoJsonFeatureCollection], srid: int = DEFAULT_SRID
):
    with connection_manager.get_db_session() as session:
        json_annotations = _geojson_features_from_body(body)
        for json_annotation in json_annotations:
            properties = json_annotation.properties
            geometry = json_annotation.geometry

            if json_annotation.id is None:
                raise HTTPException(400, "Property 'id' is required")

            id_ = _get_annotation_ids_integers([json_annotation.id])[0]

            annotation = session.query(DBAnnotation).filter_by(id=id_).first()
            if not annotation:
                raise HTTPException(404, f"Annotation id not found: {id_}")

            geom = _serialize_geometry(geometry, srid)

            # Notes:
            # You can't change the annotator_id of an annotation
            # Use specific endpoints to change the status (ex: /annotations/release)
            annotation.taxonomy_class_id = properties.taxonomy_class_id
            annotation.image_name = properties.image_name
            annotation.geometry = geom
        try:
            session.commit()
        except IntegrityError as e:  # pragma: no cover
            raise HTTPException(400, f"Error: {e}")


@router.post("/", response_model=List[int], status_code=201, summary="Create")
def post(
    body: Union[GeoJsonFeature, GeoJsonFeatureCollection], srid: int = DEFAULT_SRID
):
    written_annotations = []

    with connection_manager.get_db_session() as session:
        features = _geojson_features_from_body(body)
        for feature in features:
            geom = _serialize_geometry(feature.geometry, srid)
            properties = feature.properties
            annotation = DBAnnotation(
                annotator_id=properties.annotator_id,
                geometry=geom,
                taxonomy_class_id=properties.taxonomy_class_id,
                image_name=properties.image_name,
            )
            session.add(annotation)
            written_annotations.append(annotation)

        try:
            session.commit()
        except IntegrityError as e:  # pragma: no cover
            raise HTTPException(400, f"Error: {e}")

        return [a.id for a in written_annotations]


allowed_status_transitions = {
    # (from_status, to_status, only_logged_user)
    (AnnotationStatus.new, AnnotationStatus.deleted, True),
    (AnnotationStatus.new, AnnotationStatus.released, True),
    (AnnotationStatus.released, AnnotationStatus.rejected, False),
    (AnnotationStatus.released, AnnotationStatus.validated, False),
}


def _get_annotation_ids_integers(annotation_ids: List[str]) -> Union[List[int], Tuple]:
    """For annotation ids of the format 'annotation.1234', return a list of annotation ids integers"""
    try:
        annotation_ids = [int(i.split(".")[-1]) for i in annotation_ids]
    except ValueError:
        raise HTTPException(
            400, "Annotation ids must be of the format: layer_name.123456"
        )
    return annotation_ids


def _update_status(
    update_info: AnnotationStatusUpdate,
    desired_status: AnnotationStatus,
    request: Request,
):
    """Update annotations statuses based on filters provided in update_info and allowed transitions."""
    logged_user = get_logged_user(request)

    with connection_manager.get_db_session() as session:
        query = session.query(DBAnnotation)

        filters = []

        for from_status, to_status, only_logged_user in allowed_status_transitions:
            if to_status == desired_status:
                status_filter = DBAnnotation.status == from_status
                if only_logged_user:
                    filters.append(
                        and_(DBAnnotation.annotator_id == logged_user, status_filter)
                    )
                else:
                    filters.append(status_filter)

        query = query.filter(or_(*filters))

        if update_info.annotation_ids:
            annotation_ids = _get_annotation_ids_integers(update_info.annotation_ids)

            query = query.filter(DBAnnotation.id.in_(annotation_ids))

            count_in_good_state = (
                session.query(DBAnnotation.id)
                .filter(
                    and_(
                        DBAnnotation.id.in_(annotation_ids),
                        DBAnnotation.status == desired_status,
                    )
                )
                .count()
            )
            count_to_update = query.count()
            count_requested = len(annotation_ids)
            if count_to_update < count_requested - count_in_good_state:
                # some annotation ids were not in a good state and
                # a wrong transition was requested
                raise HTTPException(
                    403, "Status update refused. This transition is not allowed"
                )

        else:
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
            query = query.filter(DBAnnotation.taxonomy_class_id.in_(taxonomy_ids))

        # record validation events
        if desired_status in (AnnotationStatus.validated, AnnotationStatus.rejected):
            validation_value = {
                AnnotationStatus.validated: ValidationValue.validated,
                AnnotationStatus.rejected: ValidationValue.rejected,
            }
            session.bulk_save_objects(
                [
                    ValidationEvent(
                        annotation_id=a.id,
                        validator_id=logged_user,
                        validation_value=validation_value[desired_status],
                    )
                    for a in query
                ]
            )

        query.update({DBAnnotation.status: desired_status}, synchronize_session=False)

        session.commit()


@router.post("/release", status_code=204, summary="Release")
def update_status_release(update: AnnotationStatusUpdate, request: Request):
    return _update_status(update, AnnotationStatus.released, request)


@router.post("/validate", status_code=204, summary="Validate")
def update_status_validate(update: AnnotationStatusUpdate, request: Request):
    return _update_status(update, AnnotationStatus.validated, request)


@router.post("/reject", status_code=204, summary="Reject")
def update_status_reject(update: AnnotationStatusUpdate, request: Request):
    return _update_status(update, AnnotationStatus.rejected, request)


@router.post("/delete", status_code=204, summary="Delete")
def update_status_delete(update: AnnotationStatusUpdate, request: Request):
    return _update_status(update, AnnotationStatus.deleted, request)


@router.get(
    "/counts/{taxonomy_class_id}",
    response_model=Dict[str, AnnotationCountByStatus],
    status_code=200,
    summary="Get counts",
)
def counts(
    request: Request,
    taxonomy_class_id: int,
    group_by_image: bool = False,
    current_user_only: bool = False,
):
    """Get annotation count per annotation status for a specific taxonomy class and its children.
    """

    with connection_manager.get_db_session() as session:

        taxo = get_taxonomy_classes_tree(session, taxonomy_class_id=taxonomy_class_id)

        if not taxo:
            raise HTTPException(
                404, f"Taxonomy class id not found: {taxonomy_class_id}"
            )

        # Get annotation count only for these taxonomy class ids
        queried_taxo_ids = flatten_taxonomy_classes_ids(taxo)

        annotation_count_dict = defaultdict(AnnotationCountByStatus)

        def add_filter_current_user(query):
            logged_user = get_logged_user(request)
            query = query.filter_by(annotator_id=logged_user)
            return query

        if group_by_image:
            annotation_counts_query = (
                session.query(
                    DBAnnotation.image_name,
                    DBAnnotation.status.name,
                    func.count(DBAnnotation.id).label("annotation_count"),
                )
                .filter(DBAnnotation.taxonomy_class_id.in_(queried_taxo_ids))
                .group_by(DBAnnotation.image_name)
                .group_by(DBAnnotation.status.name)
            )

            if current_user_only:
                annotation_counts_query = add_filter_current_user(
                    annotation_counts_query
                )

            for image_name, status, count in annotation_counts_query:
                setattr(annotation_count_dict[image_name], status, count)
        else:
            annotation_counts_query = (
                session.query(
                    DBAnnotation.taxonomy_class_id,
                    DBAnnotation.status.name,
                    func.count(DBAnnotation.id).label("annotation_count"),
                )
                .filter(DBAnnotation.taxonomy_class_id.in_(queried_taxo_ids))
                .group_by(DBAnnotation.taxonomy_class_id)
                .group_by(DBAnnotation.status.name)
            )

            if current_user_only:
                annotation_counts_query = add_filter_current_user(
                    annotation_counts_query
                )

            for class_id, status, count in annotation_counts_query:
                setattr(annotation_count_dict[str(class_id)], status, count)

            # add annotation count to parent objects
            def recurse_add_counts(obj):
                for o in obj.children:
                    annotation_count_dict[str(obj.id)] += recurse_add_counts(o)
                return annotation_count_dict[str(obj.id)]

            recurse_add_counts(taxo)

        return annotation_count_dict


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


@router.post("/request_review/", status_code=204, summary="Request review")
def request_review(body: AnnotationRequestReview, request: Request):
    """Set the 'review_requested' field for a list of annotations"""
    logged_user = get_logged_user(request)

    annotation_ids = _get_annotation_ids_integers(body.annotation_ids)

    _ensure_annotations_exists(annotation_ids)
    _ensure_annotation_owner(annotation_ids, logged_user)

    with connection_manager.get_db_session() as session:
        (
            session.query(DBAnnotation)
            .filter(DBAnnotation.id.in_(annotation_ids))
            .update(
                {DBAnnotation.review_requested: body.boolean}, synchronize_session=False
            )
        )
        session.commit()
