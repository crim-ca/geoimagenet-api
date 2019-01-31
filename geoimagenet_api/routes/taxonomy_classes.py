from typing import List, Union, Dict

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import func

from geoimagenet_api.openapi_schemas import TaxonomyClass
from geoimagenet_api.database.models import (
    TaxonomyClass as DBTaxonomyClass,
    Annotation as DBAnnotation,
)
from geoimagenet_api.database.models import Taxonomy as DBTaxonomy
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import dataclass_from_object, DictSkipNone


def search(taxonomy_name, id=None, name=None, depth=-1):
    with connection_manager.get_db_session() as session:
        try:
            taxonomy = session.query(DBTaxonomy).filter_by(name=taxonomy_name).one()
        except NoResultFound:
            return f"Taxonomy not found: {taxonomy_name}", 404

        filter_by = DictSkipNone(id=id, name=name)
        if not len(filter_by):
            return "Please provide one of: id, name", 400
        filter_by["taxonomy_id"] = taxonomy.id

        taxo = query_taxonomy_classes_with_depth(session, filter_by, depth)

    if not taxo:
        return "No taxonomy class found", 404
    return taxo


def get(id, depth=-1):
    with connection_manager.get_db_session() as session:
        taxo = query_taxonomy_classes_with_depth(
            session, filter_by={"id": id}, depth=depth
        )
    if not taxo:
        return "Taxonomy class id not found", 404
    return taxo


def insert_annotation_count(session, taxo: List[TaxonomyClass]) -> None:
    """For a given list of nested TaxonomyClass instances, query the database to
    get the total count of annotation for each taxonomy class."""
    queried_taxo_ids = flatten_taxonomy_ids(taxo)
    annotation_counts = (
        session.query(
            DBAnnotation.taxonomy_class_id,
            func.count(DBAnnotation.id).label("annotation_count"),
        )
        .filter(DBAnnotation.taxonomy_class_id.in_(queried_taxo_ids))
        .group_by(DBAnnotation.taxonomy_class_id)
    )
    # build dictionary of annotation count per taxonomy_class_id
    annotation_count_dict = {
        o.taxonomy_class_id: o.annotation_count for o in annotation_counts
    }

    # insert annotation_count in the returned object
    def recurse(obj: TaxonomyClass):
        obj.annotation_count = annotation_count_dict.get(obj.id, 0)
        for child in obj.children:
            recurse(child)

    for t in taxo:
        recurse(t)


def flatten_taxonomy_ids(
    taxo: Union[List[TaxonomyClass], List[DBTaxonomyClass]]
) -> List[int]:
    """make a list of all the taxonomy_class ids from nested objects"""

    def get_queried_ids(obj):
        yield obj.id
        for child in obj.children:
            yield from get_queried_ids(child)

    queried_taxo_ids = list(set(id_ for t in taxo for id_ in get_queried_ids(t)))
    return queried_taxo_ids


def query_taxonomy_classes_with_depth(
    session, filter_by: Dict, depth: int
) -> List[TaxonomyClass]:
    if depth == 0:
        # If the depth is 0, we explicitely don't query the children.
        # The way the sqlalchemy relationship is set, the query is always recursive and
        # much more expensive than needed in this case.
        fields = [DBTaxonomyClass.id, DBTaxonomyClass.name, DBTaxonomyClass.taxonomy_id]
    else:
        fields = [DBTaxonomyClass]
    taxo = session.query(*fields).filter_by(**filter_by).all()
    taxo = [dataclass_from_object(TaxonomyClass, t, depth=depth) for t in taxo]
    insert_annotation_count(session, taxo)
    return taxo
