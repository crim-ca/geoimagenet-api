from slugify import slugify
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from geoimagenet_api.openapi_schemas import Taxonomy, TaxonomyVersion, TaxonomyGroup
from geoimagenet_api.database.models import Taxonomy as DBTaxonomy
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import dataclass_from_object


def aggregated_taxonomies():
    with connection_manager.get_db_session() as session:
        return (
            session.query(
                func.array_agg(DBTaxonomy.id),
                DBTaxonomy.name,
                func.array_agg(DBTaxonomy.version),
            )
            .group_by(DBTaxonomy.name)
            .all()
        )


def search(name=None, version=None):
    if version and not name:
        return "Please provide a `name` if you provide a `version`.", 400

    taxonomy_list = []
    for taxonomy in aggregated_taxonomies():
        ids, taxonomy_name, taxonomy_versions = taxonomy
        if name is not None:
            if name not in (taxonomy_name, slugify(taxonomy_name)):
                continue
        if version is not None:
            if version in taxonomy_versions:
                index = taxonomy_versions.index(version)
                ids = ids[index : index + 1]
                taxonomy_versions = taxonomy_versions[index : index + 1]
            else:
                return "Version not found", 404

        versions = [
            TaxonomyVersion(taxonomy_id=i, version=v) for i, v in zip(ids, taxonomy_versions)
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
        ids, taxonomy_name, taxonomy_versions = taxonomy
        if slugify(taxonomy_name) == name_slug and version in taxonomy_versions:
            taxonomy_id = ids[taxonomy_versions.index(version)]
            return Taxonomy(
                id=taxonomy_id,
                name=taxonomy.name,
                slug=name_slug,
                version=version,
            )
    return "Taxonomy not found", 404
