import json
from collections import defaultdict
from typing import Tuple, Dict, Union

from flask import request
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

from geoimagenet_api.openapi_schemas import (
    AnnotationProperties,
    AnnotationCounts,
    AnnotationCount,
)
from geoimagenet_api.database.models import (
    Annotation as DBAnnotation,
    AnnotationStatus,
    TaxonomyClass as DBTaxonomyClass,
)
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.routes.taxonomy_classes import (
    flatten_taxonomy_ids,
    get_taxonomy_tree,
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

            layer, id_ = json_annotation.get("id").split(".", 1)

            try:
                id_ = int(id_)
            except ValueError:
                return f"Annotation id not an int: {id_}", 400

            annotation = session.query(DBAnnotation).filter_by(id=id_).first()
            if not annotation:
                return f"Annotation id not found: {id_}", 404

            geom = _serialize_geometry(geometry, srid)

            annotation.taxonomy_class_id = properties.taxonomy_class_id
            annotation.image_name = properties.image_name
            annotation.annotator_id = properties.annotator_id
            annotation.status = properties.status
            annotation.geometry = geom

        try:
            session.commit()
        except IntegrityError as e:
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
        except IntegrityError as e:
            return f"Error: {e}", 400

        return [a.id for a in written_annotations], 201


def delete():
    try:
        ids = [int(i.split(".", 1)[1]) for i in request.json]
    except (ValueError, IndexError):
        return f"Annotation id must be of the form: layer_name.1234567", 400

    with connection_manager.get_db_session() as session:
        query = session.query(DBAnnotation.id).filter(DBAnnotation.id.in_(ids))
        if not query.count():
            return f"Annotation ids not found", 404
        query.delete(False)
        session.commit()
    return "Success", 204


def release(taxonomy_class_id):
    logged_user = get_logged_user(request)

    with connection_manager.get_db_session() as session:
        taxo = session.query(DBTaxonomyClass).filter_by(id=taxonomy_class_id).all()
        if not taxo:
            return f"Taxonomy class id not found: {taxonomy_class_id}", 404
        taxo_ids = flatten_taxonomy_ids(taxo)
        (
            session.query(DBAnnotation)
            .filter(
                and_(
                    DBAnnotation.taxonomy_class_id.in_(taxo_ids),
                    DBAnnotation.annotator_id == logged_user,
                )
            )
            .update(
                {DBAnnotation.status: AnnotationStatus.released},
                synchronize_session=False,
            )
        )
        session.commit()

    return "No Content", 204


def counts(taxonomy_class_id):
    """Get annotation count per annotation status for a specific taxonomy class and its children.
    """
    with connection_manager.get_db_session() as session:

        # Get the taxonomy tree corresponding to this taxonomy_class_id

        taxonomy_class = (
            session.query(
                DBTaxonomyClass.id, DBTaxonomyClass.name, DBTaxonomyClass.taxonomy_id
            )
            .filter_by(id=taxonomy_class_id)
            .first()
        )
        if not taxonomy_class:
            return "Taxonomy class id not found", 404

        taxo = get_taxonomy_tree(
            session,
            taxonomy_id=taxonomy_class.taxonomy_id,
            taxonomy_class_id=taxonomy_class_id,
        )

        # Get annotation count only for these taxonomy class ids
        queried_taxo_ids = flatten_taxonomy_ids(taxo)

        annotation_counts_query = (
            session.query(
                DBAnnotation.taxonomy_class_id,
                DBAnnotation.status,
                func.count(DBAnnotation.id).label("annotation_count"),
            )
            .filter(DBAnnotation.taxonomy_class_id.in_(queried_taxo_ids))
            .group_by(DBAnnotation.taxonomy_class_id)
            .group_by(DBAnnotation.status)
        )
        # build dictionary of annotation count per taxonomy_class_id
        annotation_count_dict = defaultdict(AnnotationCount)

        for taxonomy_class_id, status, count in annotation_counts_query:
            setattr(annotation_count_dict[taxonomy_class_id], status.name, count)

        # add annotation count to parent objects
        def recurse_add_counts(obj):
            for o in obj.children:
                annotation_count_dict[obj.id] += recurse_add_counts(o)
            return annotation_count_dict[obj.id]

        recurse_add_counts(taxo)

        # Build return object
        annotation_counts = [
            AnnotationCounts(taxo_id, counts)
            for taxo_id, counts in annotation_count_dict.items()
        ]

        return annotation_counts
