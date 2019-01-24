import json
from typing import Dict

from flask import request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

from geoimagenet_api.openapi_schemas import AnnotationProperties
from geoimagenet_api.database.models import Annotation as DBAnnotation, Annotation
from geoimagenet_api.database.connection import connection_manager


def put():
    properties = request.json['properties']
    geometry = request.json['geometry']
    properties = AnnotationProperties(
        annotator_id=properties['annotator_id'],
        taxonomy_class_id=properties['taxonomy_class_id'],
        image_name=properties['image_name'],
        released=properties.get('released', False),
    )

    if "id" not in request.json:
        return "Property 'id' is required", 400

    layer, id_ = request.json.get('id').split(".", 1)

    try:
        id_ = int(id_)
    except ValueError:
        return f"Annotation id not an int: {id_}", 400

    with connection_manager.get_db_session() as session:
        annotation = session.query(DBAnnotation).filter_by(id=id_).first()
        if not annotation:
            return f"Annotation id not found: {id_}", 404

        geom_string = json.dumps(geometry)
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

        return annotation.id


    return ids
