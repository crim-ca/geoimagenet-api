import json

from flask import request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

from geoimagenet_api.openapi_schemas import AnnotationProperties
from geoimagenet_api.database.models import Annotation as DBAnnotation, Annotation
from geoimagenet_api.database.connection import connection_manager


def _geojson_features_from_request(request):
    if request.json['type'] == 'FeatureCollection':
        features = request.json['features']
    else:
        features = [request.json]
    return features


def put():
    with connection_manager.get_db_session() as session:
        json_annotations = _geojson_features_from_request(request)
        for json_annotation in json_annotations:
            properties = json_annotation['properties']
            geometry = json_annotation['geometry']
            properties = AnnotationProperties(
                annotator_id=properties['annotator_id'],
                taxonomy_class_id=properties['taxonomy_class_id'],
                image_name=properties['image_name'],
                released=properties.get('released', False),
            )

            if "id" not in json_annotation:
                return "Property 'id' is required", 400

            layer, id_ = json_annotation.get('id').split(".", 1)

            try:
                id_ = int(id_)
            except ValueError:
                return f"Annotation id not an int: {id_}", 400

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
    written_annotations = []

    with connection_manager.get_db_session() as session:
        features = _geojson_features_from_request(request)
        for feature in features:
            geometry = feature['geometry']
            properties = feature['properties']

            geom_string = json.dumps(geometry)
            geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_string), 3857)

            annotation = Annotation(
                annotator_id=properties['annotator_id'],
                geometry=geom,
                taxonomy_class_id=properties['taxonomy_class_id'],
                image_name=properties['image_name'],
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
