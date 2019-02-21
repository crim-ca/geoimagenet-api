import json

from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import and_

from flask import Response

from geoimagenet_api.routes.taxonomy_classes import get_all_taxonomy_classes_ids
from geoimagenet_api.database.models import Annotation as DBAnnotation, AnnotationStatus
from geoimagenet_api.database.connection import connection_manager


def get_annotations(taxonomy_id):
    with connection_manager.get_db_session() as session:
        taxonomy_ids = get_all_taxonomy_classes_ids(session, taxonomy_id)

        query = session.query(
            func.json_build_object(
                "type",
                "Feature",
                "geometry",
                cast(func.ST_AsGeoJSON(DBAnnotation.geometry), JSON),
                "properties",
                func.json_build_object(
                    "image_name",
                    DBAnnotation.image_name,
                    "taxonomy_class_id",
                    DBAnnotation.taxonomy_class_id,
                ),
            )
        ).filter(
            and_(
                DBAnnotation.status == AnnotationStatus.validated,
                DBAnnotation.taxonomy_class_id.in_(taxonomy_ids),
            )
        )

        # try to stream the geojson features from the database
        # so that the whole FeatureCollection is not built entirely in memory

        def geojson_stream():
            yield '{"type": "FeatureCollection", "features": ['
            n_features = query.count()
            for n, r in enumerate(query):
                feature = json.dumps(r[0])
                if n != n_features - 1:
                    feature += ','
                yield feature
            yield ']}'
        return Response(geojson_stream(), mimetype='application/json')
