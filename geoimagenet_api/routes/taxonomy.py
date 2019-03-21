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


def search(name=None, version=None):
    if version and not name:
        return "Please provide a `name` if you provide a `version`.", 400

    taxonomy_list = []
    for taxonomy in aggregated_taxonomies():
        ids, name_fr, name_en, root_taxonomy_class_ids, taxonomy_versions = taxonomy
        taxonomy_infos = list(zip(ids, root_taxonomy_class_ids, taxonomy_versions))
        if name is not None:
            if name not in (name_fr, slugify(name_fr), name_en, slugify(name_en)):
                continue
        if version is not None:
            if version in taxonomy_versions:
                index = taxonomy_versions.index(version)
                taxonomy_infos = taxonomy_infos[index : index + 1]
            else:
                return f"Version not found name={name} version={version}", 404

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

    if not taxonomy_list:
        return "No taxonomy found", 404
    return taxonomy_list


def get_by_slug(name_slug, version):
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
    return "Taxonomy not found", 404
