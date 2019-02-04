import connexion
from flask import request

from geoimagenet_api.openapi_schemas import Validation, ValidationPost, Batch
from geoimagenet_api.database.models import Batch as DBBatch, BatchItem as DBBatchItem
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


def get_batch_items_by_role(id, role):
    with connection_manager.get_db_session() as session:
        batch_items = session.query(DBBatchItem).filter_by(batch_id=id, role=role)
        if not batch_items.count():
            return "No batch items found", 404
        # todo: return geojson


def post(taxonomy_id):
    with connection_manager.get_db_session() as session:
        user = get_logged_user(request=request)
        batch = DBBatch(created_by=user)
        session.add(batch)
        session.flush()

        # todo: calculate 10% test and 90% training

        return batch.id, 201
