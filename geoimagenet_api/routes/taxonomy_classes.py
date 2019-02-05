from typing import List, Union

from slugify import slugify
from collections import defaultdict

from geoimagenet_api.openapi_schemas import TaxonomyClass
from geoimagenet_api.database.models import TaxonomyClass as DBTaxonomyClass
from geoimagenet_api.database.models import Taxonomy as DBTaxonomy
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import dataclass_from_object


def search(taxonomy_name, id=None, name=None, depth=-1):
    with connection_manager.get_db_session() as session:
        for t in session.query(DBTaxonomy):
            if taxonomy_name in (t.name, slugify(t.name)):
                taxonomy = t
                break
        else:
            return f"Taxonomy name or slug not found: {taxonomy_name}", 404

        if not id and not name:
            return "Please provide one of: id, name", 400
        if name and not id:
            id = (
                session.query(DBTaxonomyClass.id)
                .filter_by(taxonomy_id=taxonomy.id, name=name)
                .scalar()
            )
            if not id:
                return f"Taxonomy class name not found: {name}", 404

        taxonomy_class = (
            session.query(
                DBTaxonomyClass.id, DBTaxonomyClass.name, DBTaxonomyClass.taxonomy_id
            )
            .filter_by(id=id)
            .first()
        )
        if not taxonomy_class:
            return "Taxonomy class id not found", 404

        if depth == 0:
            taxo = dataclass_from_object(TaxonomyClass, taxonomy_class)
        else:
            taxo = get_taxonomy_tree(
                session, taxonomy_id=taxonomy.id, taxonomy_class_id=id
            )

    if not taxo:
        return "No taxonomy class found", 404
    return [taxo]


def get(id, depth=-1):
    with connection_manager.get_db_session() as session:
        taxonomy_class = (
            session.query(
                DBTaxonomyClass.id, DBTaxonomyClass.name, DBTaxonomyClass.taxonomy_id
            )
            .filter_by(id=id)
            .first()
        )
        if not taxonomy_class:
            return "Taxonomy class id not found", 404
        if depth == 0:
            return dataclass_from_object(TaxonomyClass, taxonomy_class)
        taxo = get_taxonomy_tree(
            session, taxonomy_id=taxonomy_class.taxonomy_id, taxonomy_class_id=id
        )
    return taxo


def flatten_taxonomy_ids(taxo: Union[List[TaxonomyClass], List[DBTaxonomyClass]]) -> List[int]:
    """make a list of all the taxonomy_class ids from nested objects"""

    def get_queried_ids(obj):
        yield obj.id
        for child in obj.children:
            yield from get_queried_ids(child)

    queried_taxo_ids = list(set(id_ for t in taxo for id_ in get_queried_ids(t)))
    return queried_taxo_ids


def get_taxonomy_tree(
    session, taxonomy_id: int, taxonomy_class_id: int = None
) -> TaxonomyClass:
    """Builds the taxonomy_class tree.

    If taxonomy_class_id is specified, returns this id and its children.
    If not, return the root element.

    This is the most effective solution I found to query this kind of nested elements.

    The methods tried are:

    - join parameters directly in the sqlalchemy model 'children' relationship
    - join parameters in the sqlalchemy query
    - recursive query using postgresql 'with recursive' instruction

    The taxonomy class list is very small, and this algorithm loops the list only once.

    This query happens at multiple places, so it makes sense to keep it fast.

    This should be the fastest based on my tests.
    """
    seen_classes = {}
    missing_parents = defaultdict(list)

    query_fields = [DBTaxonomyClass.id, DBTaxonomyClass.name, DBTaxonomyClass.parent_id]
    for taxo in session.query(*query_fields).filter_by(taxonomy_id=taxonomy_id):
        taxonomy_class = TaxonomyClass(
            id=taxo.id, name=taxo.name, taxonomy_id=taxonomy_id
        )
        seen_classes[taxo.id] = taxonomy_class

        if taxo.id in missing_parents:
            for child in missing_parents[taxo.id]:
                taxo.children.append(child)

        if taxo.parent_id in seen_classes:
            seen_classes[taxo.parent_id].children.append(taxonomy_class)
        else:
            missing_parents[taxo.parent_id].append(taxonomy_class)

    root = missing_parents[None][0]
    if taxonomy_class_id is not None:
        return seen_classes[taxonomy_class_id]
    return root
