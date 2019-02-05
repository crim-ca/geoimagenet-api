import json

import connexion
from flask import request
from sqlalchemy import func

from geoimagenet_api.openapi_schemas import Batch, BatchItems
from geoimagenet_api.database.models import (
    Batch as DBBatch,
    BatchItem as DBBatchItem,
    Annotation as DBAnnotation,
    TaxonomyClass as DBTaxonomyClass,
)
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import dataclass_from_object, get_logged_user


def search():
    with connection_manager.get_db_session() as session:
        batches = session.query(DBBatch)
        batches = [dataclass_from_object(Batch, b) for b in batches]
        return batches


def get(id):
    with connection_manager.get_db_session() as session:
        batch = session.query(DBBatch).filter_by(id=id).first()
        if not batch:
            return "Batch id not found", 404
        return dataclass_from_object(Batch, batch)


def get_batch_items_training(id):
    return get_batch_items(id, "training")


def get_batch_items_testing(id):
    return get_batch_items(id, "testing")


def get_batch_items(id, role):
    with connection_manager.get_db_session() as session:
        batch_items = session.query(DBBatchItem.annotation_id).filter_by(
            batch_id=id, role=role
        )
        if not batch_items.first():
            return "No batch items found", 404
        max_decimal_digits = 15
        option_add_short_crs = 2
        geometry = func.ST_AsGeoJSON(
            func.ST_Collect(DBAnnotation.geometry),
            max_decimal_digits,
            option_add_short_crs,
        ).label("geometries")
        query = (
            session.query(
                DBAnnotation.taxonomy_class_id,
                geometry,
                DBTaxonomyClass.name.label("taxonomy_class_name"),
            )
            .filter(DBAnnotation.id.in_(batch_items))
            .group_by(DBAnnotation.taxonomy_class_id, DBTaxonomyClass.name)
            .join(DBTaxonomyClass)
        )
        result = []
        for row in query:
            result.append({
                "taxonomy_class_id": row.taxonomy_class_id,
                "taxonomy_class_name": row.taxonomy_class_name,
                "geometries": json.loads(row.geometries),
            })
        return result


def post(taxonomy_id):
    with connection_manager.get_db_session() as session:
        user = get_logged_user(request=request)
        batch = DBBatch(created_by=user)
        session.add(batch)
        session.flush()

        # todo: calculate 10% test and 90% training

        return batch.id, 201
