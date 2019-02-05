import json

from flask import request
from geoimagenet_api.routes.taxonomy_classes import get_all_taxonomy_classes_ids
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy import func

from geoimagenet_api.openapi_schemas import Batch
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
            result.append(
                {
                    "taxonomy_class_id": row.taxonomy_class_id,
                    "taxonomy_class_name": row.taxonomy_class_name,
                    "geometries": json.loads(row.geometries),
                }
            )
        return result


def post(taxonomy_id):
    testing_ratio = 10  # one in 10

    with connection_manager.get_db_session() as session:
        batch_items = []
        other_batches_count = None

        user = get_logged_user(request=request)
        batch = DBBatch(created_by=user, taxonomy_id=taxonomy_id)
        session.add(batch)
        session.flush()
        batch_id = batch.id

        other_batches_ids = session.query(DBBatch.id).filter_by(taxonomy_id=taxonomy_id)
        other_batches_annotation_ids = None
        if other_batches_ids.first():
            query = (
                session.query(DBBatchItem.annotation_id, DBBatchItem.role)
                .filter_by(DBBatchItem.batch_id.in_(other_batches_ids))
                .distinct()
            )
            batch_items += [
                DBBatchItem(batch_id=batch_id, annotation_id=id_, role=role)
                for id_, role in query
            ]

            other_batches_annotation_ids = (
                session.query(DBBatchItem.annotation_id)
                .filter_by(DBBatchItem.batch_id.in_(other_batches_ids))
                .distinct()
            )

            query = (
                session.query(
                    DBAnnotation.taxonomy_class_id, func.count(DBAnnotation.id)
                )
                .filter_by(DBAnnotation.id.in_(other_batches_annotation_ids))
                .group_by(DBAnnotation.taxonomy_class_id)
            )

            for taxonomy_class_id, count in query:
                other_batches_count[taxonomy_class_id] = count

        ids = get_all_taxonomy_classes_ids(session, taxonomy_id)

        query = (
            session.query(
                DBAnnotation.taxonomy_class_id,
                func.array_agg(aggregate_order_by(DBAnnotation.id, func.random())),
            )
            .group_by(DBAnnotation.taxonomy_class_id)
            .filter(DBAnnotation.taxonomy_class_id.in_(ids))
        )

        if other_batches_annotation_ids is not None:
            query = query.filter(~DBAnnotation.id.in_(other_batches_annotation_ids))

        for taxonomy_class_id, annotation_ids in query:
            start = 0
            if other_batches_count is not None:
                start = other_batches_count[taxonomy_class_id]

            for n, annotation_id in enumerate(annotation_ids, start=start):
                testing = n % testing_ratio == (testing_ratio - 1)
                role = "testing" if testing else "training"
                item = DBBatchItem(
                    batch_id=batch_id, annotation_id=annotation_id, role=role
                )
                batch_items.append(item)
        session.bulk_save_objects(batch_items)
        session.commit()

        return batch_id, 201
