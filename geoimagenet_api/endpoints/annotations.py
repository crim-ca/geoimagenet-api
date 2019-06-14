from collections import defaultdict
from typing import Tuple, Dict, Union, List

from fastapi import APIRouter, Query, Body
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import StreamingResponse

from geoimagenet_api.endpoints.image import (
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
)
from geoimagenet_api.endpoints.taxonomy_classes import (
    flatten_taxonomy_classes_ids,
    get_taxonomy_classes_tree,
    get_all_taxonomy_classes_ids,
)
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import geojson_stream

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


def _serialize_geometry(geometry: AnyGeojsonGeometry, crs: int):
    """Takes a dict geojson geometry, and prepares it to  be written to the db.

    It transforms the geometry into the DEFAULT_CRS if necessary."""
    geom_string = geometry.json()
    geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_string), crs)
    if crs != DEFAULT_SRID:
        geom = func.ST_Transform(geom, DEFAULT_SRID)
    return geom


@router.get(
    "/annotations", response_model=GeoJsonFeatureCollection, summary="Get as GeoJson"
)
def get(
    request: Request,
    image_name: str = None,
    status: str = None,
    taxonomy_class_id: int = None,
    review_requested: bool = None,
    current_user_only: bool = False,
    with_geometry: bool = True,
):
    with connection_manager.get_db_session() as session:
        fields = [
            DBAnnotation.id,
            DBAnnotation.taxonomy_class_id,
            DBAnnotation.annotator_id,
            DBAnnotation.image_id,
            DBAnnotation.name,
            DBAnnotation.review_requested,
            DBAnnotation.status,
        ]
        if with_geometry:
            fields.append(func.ST_AsGeoJSON(DBAnnotation.geometry).label("geometry"))
        query = session.query(*fields)
        if image_name:
            image_id = image_id_from_image_name(session, image_name)
            query = query.filter_by(image_id=image_id)
        if status:
            query = query.filter_by(status=status)
        if taxonomy_class_id:
            query = query.filter_by(taxonomy_class_id=taxonomy_class_id)
        if review_requested is not None:
            query = query.filter_by(review_requested=review_requested)
        if current_user_only:
            logged_user_id = get_logged_user_id(request)
            query = query.filter_by(annotator_id=logged_user_id)

        properties = [f.key for f in fields if f.key not in ["geometry", "id"]]
        stream = geojson_stream(
            query, properties=properties, with_geometry=with_geometry
        )

        return StreamingResponse(stream, media_type="application/json")


@router.put("/annotations", status_code=204, summary="Modify")
def put(
    request: Request,
    body: Union[GeoJsonFeature, GeoJsonFeatureCollection] = Body(...), srid: int = DEFAULT_SRID,
):
    logged_user_id = get_logged_user_id(request)

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
            if annotation.annotator_id != logged_user_id:
                raise HTTPException(403, "You are trying to update an annotation another user created.")

            geom = _serialize_geometry(geometry, srid)

            # Notes:
            # You can't change the annotator_id of an annotation
            # Use specific endpoints to change the status (ex: /annotations/release)
            annotation.taxonomy_class_id = properties.taxonomy_class_id

            annotation.image_id = image_id_from_properties(session, properties)
            annotation.geometry = geom
        try:
            session.commit()
        except IntegrityError as e:  # pragma: no cover
            raise HTTPException(400, f"Error: {e}")


@router.post(
    "/annotations", response_model=List[int], status_code=201, summary="Create"
)
def post(
    request: Request,
    body: Union[GeoJsonFeature, GeoJsonFeatureCollection] = Body(...), srid: int = DEFAULT_SRID
):
    logged_user_id = get_logged_user_id(request)
    annotations_to_write = []

    with connection_manager.get_db_session() as session:
        features = _geojson_features_from_body(body)
        for feature in features:
            geom = _serialize_geometry(feature.geometry, srid)
            properties = feature.properties
            image_id = image_id_from_properties(session, properties)

            annotation = DBAnnotation(
                annotator_id=logged_user_id,
                geometry=geom,
                taxonomy_class_id=properties.taxonomy_class_id,
                image_id=image_id,
            )
            annotations_to_write.append(annotation)

        try:
            session.bulk_save_objects(annotations_to_write)
            session.commit()
        except IntegrityError as e:  # pragma: no cover
            raise HTTPException(400, f"Error: {e}")

        return [a.id for a in annotations_to_write]


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
                            and_(DBAnnotation.annotator_id == logged_user_id, status_filter)
                        )
                    else:
                        filters.append(status_filter)

            return query.filter(or_(*filters))

        def _filter_annotation_ids(query) -> Union[Query, Tuple]:

            annotation_ids = _get_annotation_ids_integers(update_info.annotation_ids)

            existing_ids = session.query(DBAnnotation.id).filter(DBAnnotation.id.in_(annotation_ids))
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
                    403, "Status update refused. One or more status transition not allowed."
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

        if update_info.annotation_ids:
            query = _filter_annotation_ids(query)
        else:
            query = _filter_taxonomy_ids(query)

        _record_validation_events(session, desired_status, logged_user_id, query)

        query.update({DBAnnotation.status: desired_status}, synchronize_session=False)

        session.commit()


def _record_validation_events(session, desired_status, user_id, query):
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
                    validator_id=user_id,
                    validation_value=validation_value[desired_status],
                )
                for a in query
            ]
        )



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


@router.get(
    "/annotations/counts/{taxonomy_class_id}",
    response_model=Dict[str, AnnotationCountByStatus],
    status_code=200,
    summary="Get counts",
)
def counts(
    request: Request,
    taxonomy_class_id: int,
    group_by_image: bool = Query(
        False, description="Group by taxonomy class id or by image_name"
    ),
    current_user_only: bool = Query(
        False, description="If true, count only the current user's annotations"
    ),
    with_taxonomy_children: bool = Query(
        True, description="Include the children of the provided taxonomy class id"
    ),
    review_requested: bool = Query(
        None, description="Filter annotations by the review_requested attribute"
    ),
):
    """Return annotation counts for the given taxonomy class along with its children.
    If group_by_image is True, the counts are grouped by image name instead of
    taxonomy class.
    """

    with connection_manager.get_db_session() as session:
        taxo = get_taxonomy_classes_tree(session, taxonomy_class_id=taxonomy_class_id)
        if not taxo:
            raise HTTPException(
                404, f"Taxonomy class id not found: {taxonomy_class_id}"
            )

        if with_taxonomy_children:
            taxonomy_class_ids = flatten_taxonomy_classes_ids(taxo)
        else:
            taxonomy_class_ids = [taxonomy_class_id]

        annotation_count_dict = defaultdict(AnnotationCountByStatus)

        if group_by_image:
            group_by_field = Image.layer_name
        else:
            group_by_field = DBAnnotation.taxonomy_class_id

        query = session.query(
            group_by_field,
            DBAnnotation.status.name,
            func.count(DBAnnotation.id).label("annotation_count"),
        )
        if group_by_image:
            query = query.select_from(DBAnnotation).join(
                Image, Image.id == DBAnnotation.image_id
            )
        query = (
            query.filter(DBAnnotation.taxonomy_class_id.in_(taxonomy_class_ids))
            .group_by(group_by_field)
            .group_by(DBAnnotation.status.name)
        )

        if current_user_only:
            logged_user_id = get_logged_user_id(request)
            query = query.filter(DBAnnotation.annotator_id == logged_user_id)

        if review_requested is not None:
            query = query.filter(DBAnnotation.review_requested == review_requested)

        for group_by_field_name, status, count in query:
            setattr(annotation_count_dict[str(group_by_field_name)], status, count)

        if not group_by_image:
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


@router.post(
    "/annotations/request_review",
    status_code=204,
    response_model=None,
    summary="Request review",
)
def request_review(body: AnnotationRequestReview, request: Request):
    """Set the 'review_requested' field for a list of annotations"""
    logged_user_id = get_logged_user_id(request)

    annotation_ids = _get_annotation_ids_integers(body.annotation_ids)

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
