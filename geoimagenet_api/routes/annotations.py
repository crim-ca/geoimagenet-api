from flask import request
import connexion

from geoimagenet_api.openapi_schemas import AnnotationPut
from geoimagenet_api.database.models import Annotation as DBAnnotation
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import dataclass_from_object


def put():
    annotations = [
        AnnotationPut(id=a["id"], released=a["released"]) for a in request.json
    ]
    with connection_manager.get_db_session() as session:
        ids = list(sorted([a.id for a in annotations]))
        query = session.query(DBAnnotation).filter(DBAnnotation.id.in_(ids)).order_by(DBAnnotation.id)
        if query.count() != len(annotations):
            not_found = set([a.id for a in annotations]).difference([q.id for q in query])
            return f"Ids not found: {', '.join(map(str, not_found))}", 404

        for anno, db_anno in zip(annotations, query):
            db_anno.released = anno.released

        session.commit()
    return "Annotations updated", 204
