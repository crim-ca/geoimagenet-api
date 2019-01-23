import json
from typing import Dict

from flask import request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

from geoimagenet_api.openapi_schemas import GeoJsonAnnotation, AnnotationProperties
from geoimagenet_api.database.models import Annotation as DBAnnotation, Annotation
from geoimagenet_api.database.connection import connection_manager


def put():
    geojson_annotation = GeoJsonAnnotation(**request.json)
    # noinspection PyArgumentList
    properties = AnnotationProperties(**geojson_annotation.properties)
    if not properties.annotation_id:
        return "Property 'annotation_id' is required", 400

    with connection_manager.get_db_session() as session:
        annotation = session.query(DBAnnotation).filter_by(id=properties.annotation_id).first()
        if not annotation:
            return f"Annotation id not found: {properties.annotation_id}", 404

        geom_string = json.dumps(geojson_annotation.geometry)
        geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_string), 3857)

        annotation.taxonomy_class_id = properties.taxonomy_class_id
        annotation.image_name = properties.image_name
        annotation.annotator_id = properties.annotator_id
        annotation.released = properties.released
        annotation.geometry = geom

        try:
            session.commit()
        except IntegrityError as e:
            return f"Error: {e}", 400

    return "Annotations updated", 204


def post():
    ids = []
    with connection_manager.get_db_session() as session:
        geometry = request.json['geometry']
        properties = request.json['properties']

        geom_string = json.dumps(geometry)
        geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_string), 3857)

        annotation = Annotation(
            annotator_id=properties['annotator_id'],
            geometry=geom,
            taxonomy_class_id=properties['taxonomy_class_id'],
            image_name=properties['image_name'],
        )
        session.add(annotation)
        try:
            session.commit()
        except IntegrityError as e:
            return f"Error: {e}", 400

        ids.append(annotation.id)

    return ids
