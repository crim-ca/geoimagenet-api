import json
from collections import defaultdict
from typing import Tuple, Dict, Union, List, Optional

import dataclasses
from flask import request
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

from geoimagenet_api.openapi_schemas import (
    AnnotationProperties,
    AnnotationCountByStatus,
    AnnotationStatusUpdate,
)
from geoimagenet_api.database.models import (
    Annotation as DBAnnotation,
    AnnotationStatus,
    TaxonomyClass as DBTaxonomyClass,
    ValidationEvent,
    ValidationValue,
)
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.endpoints.taxonomy_classes import (
    flatten_taxonomy_classes_ids,
    get_taxonomy_classes_tree,
    get_all_taxonomy_classes_ids,
)
from geoimagenet_api.utils import get_logged_user

DEFAULT_SRID = 3857


def _geojson_features_from_request(request) -> Tuple[Dict, Union[Dict, None]]:
    """Basic helper function to support a FeatureCollection and a single feature."""
    if request.json["type"] == "FeatureCollection":
        features = request.json["features"]
    else:
        features = [request.json]
    return features


def _serialize_geometry(geometry: Dict, crs: int):
    """Takes a dict geojson geometry, and prepares it to  be written to the db.

    It transforms the geometry into the DEFAULT_CRS if necessary."""
    geom_string = json.dumps(geometry)
    geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_string), crs)
    if crs != DEFAULT_SRID:
        geom = func.ST_Transform(geom, DEFAULT_SRID)
    return geom


def put(srid=DEFAULT_SRID):
    with connection_manager.get_db_session() as session:
        json_annotations = _geojson_features_from_request(request)
        for json_annotation in json_annotations:
            properties = json_annotation["properties"]
            geometry = json_annotation["geometry"]
            properties = AnnotationProperties(
                annotator_id=properties["annotator_id"],
                taxonomy_class_id=properties["taxonomy_class_id"],
                image_name=properties["image_name"],
                status=properties.get("status", AnnotationStatus.new),
            )

            if "id" not in json_annotation:
                return "Property 'id' is required", 400

            result = _get_annotation_ids_integers([json_annotation["id"]])
            if isinstance(result, tuple) and len(result) == 2:
                return result  # error reponse

            id_ = result[0]

            annotation = session.query(DBAnnotation).filter_by(id=id_).first()
            if not annotation:
                return f"Annotation id not found: {id_}", 404

            geom = _serialize_geometry(geometry, srid)

            annotation.taxonomy_class_id = properties.taxonomy_class_id
            annotation.image_name = properties.image_name
            annotation.geometry = geom

            # You can't change the owner of an annotation
            # annotation.annotator_id = properties.annotator_id

            # Use specific endpoints to change the status (ex: /annotations/release)
            # annotation.status = properties.status

        try:
            session.commit()
        except IntegrityError as e:  # pragma: no cover
            return f"Error: {e}", 400

    return "Annotations updated", 204


def post(srid=DEFAULT_SRID):
    written_annotations = []

    with connection_manager.get_db_session() as session:
        features = _geojson_features_from_request(request)
        for feature in features:
            geometry = feature["geometry"]
            properties = feature["properties"]

            geom = _serialize_geometry(geometry, srid)

            annotation = DBAnnotation(
                annotator_id=properties["annotator_id"],
                geometry=geom,
                taxonomy_class_id=properties["taxonomy_class_id"],
                image_name=properties["image_name"],
            )
            session.add(annotation)
            written_annotations.append(annotation)

        try:
            session.commit()
        except IntegrityError as e:  # pragma: no cover
            return f"Error: {e}", 400

        return [a.id for a in written_annotations], 201


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
        return "Annotation ids must be of the format: layer_name.123456", 400
    return annotation_ids


def _update_status(
    update_info: AnnotationStatusUpdate, desired_status: AnnotationStatus
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
            result = _get_annotation_ids_integers(update_info.annotation_ids)
            if isinstance(result, tuple) and len(result) == 2:
                return result  # error response

            annotation_ids = result

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
                return "Status update refused. This transition is not allowed", 403

        else:
            taxonomy_class_id = update_info.taxonomy_class_id
            taxonomy_id = (
                session.query(DBTaxonomyClass.id)
                .filter_by(id=taxonomy_class_id)
                .first()
            )
            if not taxonomy_id:
                return f"Taxonomy class id not found {taxonomy_class_id}", 404
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
    return "No Content", 204


def update_status_release():
    return _update_status(
        AnnotationStatusUpdate(**request.json), AnnotationStatus.released
    )


def update_status_validate():
    return _update_status(
        AnnotationStatusUpdate(**request.json), AnnotationStatus.validated
    )


def update_status_reject():
    return _update_status(
        AnnotationStatusUpdate(**request.json), AnnotationStatus.rejected
    )


def update_status_delete():
    return _update_status(
        AnnotationStatusUpdate(**request.json), AnnotationStatus.deleted
    )


def counts(taxonomy_class_id, group_by_image=False, current_user_only=False):
    """Get annotation count per annotation status for a specific taxonomy class and its children.
    """

    with connection_manager.get_db_session() as session:

        taxo = get_taxonomy_classes_tree(session, taxonomy_class_id=taxonomy_class_id)

        if not taxo:
            return "Taxonomy class id not found", 404

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
                annotation_counts_query = add_filter_current_user(annotation_counts_query)

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
                annotation_counts_query = add_filter_current_user(annotation_counts_query)

            for class_id, status, count in annotation_counts_query:
                setattr(annotation_count_dict[class_id], status, count)

            # add annotation count to parent objects
            def recurse_add_counts(obj):
                for o in obj.children:
                    annotation_count_dict[obj.id] += recurse_add_counts(o)
                return annotation_count_dict[obj.id]

            recurse_add_counts(taxo)

        # Note: No validation is made by `connexion` for this returned
        # value structure due to the dynamic property name
        return {str(k): dataclasses.asdict(v) for k, v in annotation_count_dict.items()}


def _ensure_annotations_exists(annotation_ids: List[int]) -> Optional[Tuple[str, int]]:
    """Makes sure the requested annotation ids, else return a 404 response."""
    with connection_manager.get_db_session() as session:
        ids_exists = session.query(DBAnnotation.id).filter(
            DBAnnotation.id.in_(annotation_ids)
        )

        count_not_found = len(
            set(annotation_ids).difference((o[0] for o in ids_exists))
        )
        if count_not_found:
            return f"{count_not_found} annotation ids could not be found.", 404


def _ensure_annotation_owner(
    annotation_ids: List[int], logged_user: int
) -> Optional[Tuple[str, int]]:
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
            return (
                f"{count_not_owned} annotation ids are not owned by the logged in user.",
                403,
            )


def request_review():
    """Set the 'review_requested' field for a list of annotations"""
    logged_user = get_logged_user(request)

    result = _get_annotation_ids_integers(request.json["annotation_ids"])
    if isinstance(result, tuple) and len(result) == 2:
        return result  # error response

    annotation_ids = result

    response = _ensure_annotations_exists(annotation_ids)
    if response is not None:
        return response
    response = _ensure_annotation_owner(annotation_ids, logged_user)
    if response is not None:
        return response

    with connection_manager.get_db_session() as session:
        (
            session.query(DBAnnotation)
            .filter(DBAnnotation.id.in_(annotation_ids))
            .update(
                {DBAnnotation.review_requested: request.json["boolean"]},
                synchronize_session=False,
            )
        )
        session.commit()

    return "No Content", 204
