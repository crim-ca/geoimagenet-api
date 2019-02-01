from slugify import slugify
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from geoimagenet_api.openapi_schemas import Taxonomy, TaxonomyVersion, TaxonomyGroup
from geoimagenet_api.database.models import (
    Taxonomy as DBTaxonomy,
    TaxonomyClass as DBTaxonomyClass,
)
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import dataclass_from_object


def aggregated_taxonomies():
    with connection_manager.get_db_session() as session:
        query = (
            session.query(
                func.array_agg(DBTaxonomy.id),
                DBTaxonomy.name,
                func.array_agg(DBTaxonomyClass.id.label("taxonomy_class_root_id")),
                func.array_agg(DBTaxonomy.version),
            )
            .join(DBTaxonomyClass)
            .filter(DBTaxonomyClass.parent_id == None)
            .group_by(DBTaxonomy.name)
        )
        return query.all()


def search(name=None, version=None):
    if version and not name:
        return "Please provide a `name` if you provide a `version`.", 400

    taxonomy_list = []
    for taxonomy in aggregated_taxonomies():
        ids, taxonomy_name, taxonomy_class_root_ids, taxonomy_versions = taxonomy
        taxonomy_group = list(zip(ids, taxonomy_class_root_ids, taxonomy_versions))
        if name is not None:
            if name not in (taxonomy_name, slugify(taxonomy_name)):
                continue
        if version is not None:
            if version in taxonomy_versions:
                index = taxonomy_versions.index(version)
                taxonomy_group = taxonomy_group[index : index + 1]
            else:
                return f"Version not found name={name} version={version}", 404

        versions = [
            TaxonomyVersion(taxonomy_id=i, taxonomy_class_root_id=c, version=v)
            for i, c, v in taxonomy_group
        ]
        taxonomy = TaxonomyGroup(
            name=taxonomy.name, slug=slugify(taxonomy.name), versions=versions
        )

        taxonomy_list.append(taxonomy)

    if not taxonomy_list:
        return "No taxonomy found", 404
    return taxonomy_list


def get_by_slug(name_slug, version):
    for taxonomy in aggregated_taxonomies():
        ids, taxonomy_name, taxonomy_class_root_ids, taxonomy_versions = taxonomy
        if slugify(taxonomy_name) == name_slug and version in taxonomy_versions:
            index = taxonomy_versions.index(version)
            taxonomy_id = ids[index]
            taxonomy_class_root = taxonomy_class_root_ids[index]
            return Taxonomy(
                id=taxonomy_id,
                name=taxonomy.name,
                slug=name_slug,
                version=version,
                taxonomy_class_root_id=taxonomy_class_root,
            )
    return "Taxonomy not found", 404
