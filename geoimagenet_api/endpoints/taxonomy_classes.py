from typing import List, Union, Optional

from fastapi import APIRouter, HTTPException, Query
from slugify import slugify
from collections import defaultdict

from geoimagenet_api.openapi_schemas import TaxonomyClass
from geoimagenet_api.database.models import TaxonomyClass as DBTaxonomyClass
from geoimagenet_api.database.models import Taxonomy as DBTaxonomy
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import get_latest_version_number

router = APIRouter()


name_query = Query(
    None,
    description=(
        "Name of the taxonomy class. "
        "If not provided, defaults to the taxonomy classes "
        "that don't have any parent (root taxonomy classes)."
    ),
)
taxonomy_name_query = Query(
    None,
    description=(
        "Full name or sluggified name of the taxonomy. "
        "Example of name slug for 'Couverture de sol': "
        "couverture-de-sol"
    ),
)

taxonomy_version_query = Query(
    None,
    description=(
        "Version of the taxonomy. "
        "If not provided, defaults to the latest version "
        "in all the taxonomies in the database."
    ),
)


@router.get("/taxonomy_classes", response_model=List[TaxonomyClass], summary="Search")
def search(
    name: str = name_query,
    taxonomy_name: str = taxonomy_name_query,
    taxonomy_version: str = taxonomy_version_query,
    depth: int = -1,
):
    with connection_manager.get_db_session() as session:

        if not taxonomy_version:
            versions = [t.version for t in session.query(DBTaxonomy.version)]
            taxonomy_version = get_latest_version_number(versions)

        taxonomy_ids = []
        for t in session.query(DBTaxonomy):
            taxonomy_name_ok = True
            taxonomy_version_ok = t.version == taxonomy_version

            if taxonomy_name:
                name_variations = (
                    t.name_fr,
                    slugify(t.name_fr),
                    t.name_en,
                    slugify(t.name_en or ""),
                )
                if taxonomy_name not in name_variations:
                    taxonomy_name_ok = False

            if taxonomy_name_ok and taxonomy_version_ok:
                taxonomy_ids.append(t.id)

        if not taxonomy_ids:
            raise HTTPException(
                404, f"Taxonomy name or slug not found: {taxonomy_name}"
            )

        taxonomy_classes = session.query(
            DBTaxonomyClass.id,
            DBTaxonomyClass.name_fr,
            DBTaxonomyClass.name_en,
            DBTaxonomyClass.taxonomy_id,
            DBTaxonomyClass.code,
        ).filter(DBTaxonomyClass.taxonomy_id.in_(taxonomy_ids))

        if name:
            taxonomy_classes = taxonomy_classes.filter_by(name_fr=name)
        else:
            taxonomy_classes = taxonomy_classes.filter_by(parent=None)

        if not taxonomy_classes.count():
            raise HTTPException(404, f"Taxonomy class name not found: {name}")

        if depth != 0:
            return [
                get_taxonomy_classes_tree(session, taxonomy_class_id=taxo.id)
                for taxo in taxonomy_classes
            ]
        else:
            return [
                TaxonomyClass(
                    id=taxo.id,
                    name_fr=taxo.name_fr,
                    name_en=taxo.name_en,
                    taxonomy_id=taxo.taxonomy_id,
                    code=taxo.code,
                )
                for taxo in taxonomy_classes
            ]


@router.get("/taxonomy_classes/{id}", response_model=TaxonomyClass, summary="Get by id")
def get(id: int, depth: int = -1):
    with connection_manager.get_db_session() as session:
        taxonomy_class = (
            session.query(
                DBTaxonomyClass.id,
                DBTaxonomyClass.name_fr,
                DBTaxonomyClass.name_en,
                DBTaxonomyClass.taxonomy_id,
                DBTaxonomyClass.code,
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
                code=taxonomy_class.code,
            )
    return taxonomy_class


def get_all_taxonomy_classes_ids(session, taxonomy_class_id: int) -> List[int]:
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

    Return the specified taxonomy_class_id and its children.

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
            DBTaxonomyClass.code,
        ).filter_by(taxonomy_id=taxonomy_id)

        for taxo in taxonomy_query:
            taxonomy_class = TaxonomyClass(
                id=taxo.id,
                name_fr=taxo.name_fr,
                name_en=taxo.name_en,
                taxonomy_id=taxonomy_id,
                code=taxo.code,
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
