from typing import List, Dict

from fastapi import APIRouter, Query, Path
from slugify import slugify
from sqlalchemy import func


import sentry_sdk
from starlette.exceptions import HTTPException

from geoimagenet_api.openapi_schemas import Taxonomy, TaxonomyVersion, TaxonomyGroup
from geoimagenet_api.database.models import (
    Taxonomy as DBTaxonomy,
    TaxonomyClass as DBTaxonomyClass,
)
from geoimagenet_api.database.connection import connection_manager

router = APIRouter()


def get_latest_taxonomy_ids() -> Dict[str, int]:
    """Get ids for the latest taxonomies.
    
    Returns the taxonomy ids from the Taxonomy database, which are the
    root classes for the TaxonomyClass database.
    """
    with connection_manager.get_db_session() as session:
        query = session.query(
            DBTaxonomy.name_fr,
            func.array_agg(DBTaxonomy.id).label("ids"),
            func.array_agg(DBTaxonomy.version).label("versions"),
        ).group_by(DBTaxonomy.name_fr)
        return {q.name_fr: q.ids[q.versions.index(max(q.versions))] for q in query}

def get_adjusted_taxonomy_ids() -> Dict[str, int]:
    """Get the TaxonomyClass ids for the latest taxonomies.
    
    Returns the TaxonomyClass ids for the root classes found in the 
    Taxonomy database.
    """
    latest_taxonomy_ids = get_latest_taxonomy_ids()

    with connection_manager.get_db_session() as session:

        adjust_query = session.query(
            DBTaxonomyClass.name_fr,
            func.array_agg(DBTaxonomyClass.id).label("ids"),
            func.array_agg(DBTaxonomyClass.taxonomy_id).label("taxids"),
        ).filter(DBTaxonomyClass.name_fr.in_(latest_taxonomy_ids.keys())
        ).group_by(DBTaxonomyClass.name_fr)
        
        return {q.name_fr: q.ids[q.taxids.index(latest_taxonomy_ids[q.name_fr])] for q in adjust_query}

def aggregated_taxonomies():
    with connection_manager.get_db_session() as session:
        query = (
            session.query(
                func.array_agg(DBTaxonomy.id),
                DBTaxonomy.name_fr,
                DBTaxonomy.name_en,
                func.array_agg(DBTaxonomyClass.id.label("root_taxonomy_class_id")),
                func.array_agg(DBTaxonomy.version),
            )
            .join(DBTaxonomyClass)
            .filter(DBTaxonomyClass.parent_id.is_(None))
            .group_by(DBTaxonomy.name_fr, DBTaxonomy.name_en)
            .order_by(DBTaxonomy.name_fr)
        )
        return query.all()


name_query = Query(
    None,
    description=(
        "Full name or sluggified name of the taxonomy. "
        "Example of name slug for 'Couverture de sol': "
        "couverture-de-sol"
    ),
)


@router.get("/taxonomy", response_model=List[TaxonomyGroup], summary="Search")
def search(name: str = name_query, version: str = None):
    if version and not name:
        raise HTTPException(400, "Please provide a `name` if you provide a `version`.")

    taxonomy_list = []
    for taxonomy in aggregated_taxonomies():
        ids, name_fr, name_en, root_taxonomy_class_ids, taxonomy_versions = taxonomy
        taxonomy_infos = list(zip(ids, root_taxonomy_class_ids, taxonomy_versions))
        if name is not None:
            if name not in (name_fr, slugify(name_fr), name_en, slugify(name_en or "")):
                continue
        if version is not None:
            if version in taxonomy_versions:
                index = taxonomy_versions.index(version)
                taxonomy_infos = taxonomy_infos[index : index + 1]
            else:
                raise HTTPException(
                    404, f"Version not found name={name} version={version}"
                )

        versions = [
            TaxonomyVersion(taxonomy_id=i, root_taxonomy_class_id=c, version=v)
            for i, c, v in taxonomy_infos
        ]
        taxonomy_group = TaxonomyGroup(
            name_fr=taxonomy.name_fr,
            name_en=taxonomy.name_en,
            slug=slugify(taxonomy.name_fr),
            versions=versions,
        )

        taxonomy_list.append(taxonomy_group)

    if not taxonomy_list:  # pragma: no cover
        message = (
            "Could't find any taxonomy. " "The data is not loaded in the database yet."
        )
        sentry_sdk.capture_exception(error=ValueError(message))
        raise HTTPException(
            503, message + " This error was reported to the developers."
        )
    return taxonomy_list


name_slug_path = Path(
    ..., description='Example of name slug for "Couverture de sol": couverture-de-sol'
)


@router.get(
    "/taxonomy/{name_slug}/{version}", response_model=Taxonomy, summary="Get by slug"
)
def get_by_slug(version: str, name_slug: str = name_slug_path):
    for taxonomy in aggregated_taxonomies():
        ids, name_fr, name_en, root_taxonomy_class_ids, taxonomy_versions = taxonomy
        if slugify(name_fr) == name_slug and version in taxonomy_versions:
            index = taxonomy_versions.index(version)
            taxonomy_id = ids[index]
            taxonomy_class_root = root_taxonomy_class_ids[index]
            return Taxonomy(
                id=taxonomy_id,
                name_fr=taxonomy.name_fr,
                name_en=taxonomy.name_en,
                slug=name_slug,
                version=version,
                root_taxonomy_class_id=taxonomy_class_root,
            )
    raise HTTPException(404, "No taxonomy found")
