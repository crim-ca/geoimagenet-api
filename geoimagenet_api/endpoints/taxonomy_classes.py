from typing import List, Union

from fastapi import APIRouter, HTTPException
from slugify import slugify
from collections import defaultdict

from geoimagenet_api.openapi_schemas import TaxonomyClass
from geoimagenet_api.database.models import TaxonomyClass as DBTaxonomyClass
from geoimagenet_api.database.models import Taxonomy as DBTaxonomy
from geoimagenet_api.database.connection import connection_manager

router = APIRouter()


@router.get("/", response_model=List[TaxonomyClass], summary="Search")
def search(taxonomy_name: str, name: str, depth: int = -1):
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
            raise HTTPException(
                404, f"Taxonomy name or slug not found: {taxonomy_name}"
            )

        taxonomy_class = (
            session.query(
                DBTaxonomyClass.id,
                DBTaxonomyClass.name_fr,
                DBTaxonomyClass.name_en,
                DBTaxonomyClass.taxonomy_id,
            )
            .filter_by(taxonomy_id=taxonomy.id, name_fr=name)
            .first()
        )
        if not taxonomy_class:
            raise HTTPException(404, f"Taxonomy class name not found: {name}")

        if depth != 0:
            taxonomy_class = get_taxonomy_classes_tree(
                session, taxonomy_class_id=taxonomy_class.id
            )
        else:
            taxonomy_class = TaxonomyClass(
                id=taxonomy_class.id,
                name_fr=taxonomy_class.name_fr,
                name_en=taxonomy_class.name_en,
                taxonomy_id=taxonomy_class.taxonomy_id,
            )

    return [taxonomy_class]


@router.get("/{id}", response_model=TaxonomyClass, summary="Get by id")
def get(id: int, depth: int = -1):
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
            raise HTTPException(404, "Taxonomy class id not found")
        if depth != 0:
            taxonomy_class = get_taxonomy_classes_tree(
                session, taxonomy_class_id=taxonomy_class.id
            )
        else:
            taxonomy_class = TaxonomyClass(
                id=taxonomy_class.id,
                name_fr=taxonomy_class.name_fr,
                name_en=taxonomy_class.name_en,
                taxonomy_id=taxonomy_class.taxonomy_id,
            )
    return taxonomy_class


def get_all_taxonomy_classes_ids(session, taxonomy_class_id: int = None) -> List[int]:
    taxo_tree = get_taxonomy_classes_tree(session, taxonomy_class_id)
    return flatten_taxonomy_classes_ids(taxo_tree)


def flatten_taxonomy_classes_ids(
    taxo: Union[TaxonomyClass, DBTaxonomyClass]
) -> List[int]:
    """make a list of all the taxonomy_class ids from nested objects"""

    def get_queried_ids(obj):
        yield obj.id
        for child in obj.children:
            yield from get_queried_ids(child)

    queried_taxo_ids = list(set(id_ for id_ in get_queried_ids(taxo)))
    return queried_taxo_ids


def get_taxonomy_classes_tree(
    session, taxonomy_class_id: int
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

        taxonomy_query = session.query(
            DBTaxonomyClass.id,
            DBTaxonomyClass.name_fr,
            DBTaxonomyClass.name_en,
            DBTaxonomyClass.parent_id,
        ).filter_by(taxonomy_id=taxonomy_id)

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

        return seen_classes[taxonomy_class_id]
