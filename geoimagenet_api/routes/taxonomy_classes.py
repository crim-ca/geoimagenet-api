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
            if taxonomy_name in (
                t.name_fr,
                slugify(t.name_fr),
                t.name_en,
                slugify(t.name_en),
            ):
                taxonomy = t
                break
        else:
            return f"Taxonomy name or slug not found: {taxonomy_name}", 404

        if not id and not name:
            return "Please provide one of: id, name", 400
        if name and not id:
            id = (
                session.query(DBTaxonomyClass.id)
                .filter_by(taxonomy_id=taxonomy.id, name_fr=name)
                .scalar()
            )
            if not id:
                return f"Taxonomy class name not found: {name}", 404

        taxonomy_class = (
            session.query(
                DBTaxonomyClass.id,
                DBTaxonomyClass.name_fr,
                DBTaxonomyClass.name_en,
                DBTaxonomyClass.taxonomy_id,
            )
            .filter_by(id=id)
            .first()
        )
        if not taxonomy_class:
            return "Taxonomy class id not found", 404

        if depth == 0:
            taxo = dataclass_from_object(TaxonomyClass, taxonomy_class)
        else:
            taxo = get_taxonomy_classes_tree(session, taxonomy_class_id=id)

    if not taxo:
        return "No taxonomy class found", 404
    return [taxo]


def get(id, depth=-1):
    with connection_manager.get_db_session() as session:
        taxonomy_class = (
            session.query(
                DBTaxonomyClass.id,
                DBTaxonomyClass.name_fr,
                DBTaxonomyClass.name_en,
                DBTaxonomyClass.taxonomy_id,
            )
            .filter_by(id=id)
            .first()
        )
        if not taxonomy_class:
            return "Taxonomy class id not found", 404
        if depth == 0:
            return dataclass_from_object(TaxonomyClass, taxonomy_class)
        taxo = get_taxonomy_classes_tree(session, taxonomy_class_id=id)
    return taxo


def get_all_taxonomy_classes_ids(session, taxonomy_class_id: int = None) -> List[int]:
    taxo_tree = get_taxonomy_classes_tree(session, taxonomy_class_id)
    return flatten_taxonomy_classes_ids([taxo_tree])


def flatten_taxonomy_classes_ids(
    taxo: Union[List[TaxonomyClass], List[DBTaxonomyClass]]
) -> List[int]:
    """make a list of all the taxonomy_class ids from nested objects"""

    def get_queried_ids(obj):
        yield obj.id
        for child in obj.children:
            yield from get_queried_ids(child)

    queried_taxo_ids = list(set(id_ for t in taxo for id_ in get_queried_ids(t)))
    return queried_taxo_ids


def get_taxonomy_classes_tree(
    session, taxonomy_class_id: int = None
) -> Union[TaxonomyClass, None]:
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

    taxonomy_class = (
        session.query(DBTaxonomyClass.taxonomy_id)
        .filter_by(id=taxonomy_class_id)
        .first()
    )

    if taxonomy_class:
        taxonomy_id = taxonomy_class.taxonomy_id

        seen_classes = {}
        missing_parents = defaultdict(list)

        query_fields = [
            DBTaxonomyClass.id,
            DBTaxonomyClass.name_fr,
            DBTaxonomyClass.name_en,
            DBTaxonomyClass.parent_id,
        ]
        taxonomy_query = session.query(*query_fields).filter_by(taxonomy_id=taxonomy_id)

        if not taxonomy_query.first():
            raise ValueError(
                f"Couldn't find any taxonomy class having taxonomy id of {taxonomy_id}"
            )

        for taxo in taxonomy_query:
            taxonomy_class = TaxonomyClass(
                id=taxo.id,
                name_fr=taxo.name_fr,
                name_en=taxo.name_en,
                taxonomy_id=taxonomy_id,
            )
            seen_classes[taxo.id] = taxonomy_class

            if taxo.id in missing_parents:
                for child in missing_parents[taxo.id]:
                    taxonomy_class.children.append(child)

            if taxo.parent_id in seen_classes:
                seen_classes[taxo.parent_id].children.append(taxonomy_class)
            else:
                missing_parents[taxo.parent_id].append(taxonomy_class)

        root = missing_parents[None][0]
        if taxonomy_class_id is not None:
            return seen_classes[taxonomy_class_id]
        return root
