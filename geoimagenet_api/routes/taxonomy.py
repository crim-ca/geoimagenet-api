from slugify import slugify
from sqlalchemy.exc import IntegrityError

from geoimagenet_api.openapi_schemas import Taxonomy
from geoimagenet_api.database.models import Taxonomy as DBTaxonomy
from geoimagenet_api.database import session_factory
from geoimagenet_api.utils import dataclass_from_object


def search(name=None, version=None):
    session = session_factory()
    # we won't have a lot of taxonomy elements so this shouldn't be slow
    taxonomy_list = []
    for taxonomy in session.query(DBTaxonomy):
        if name is not None:
            if name not in (taxonomy.name, slugify(taxonomy.name)):
                continue
        if version is not None:
            if not taxonomy.version == version:
                continue
        taxonomy_list.append(
            Taxonomy(
                id=taxonomy.id,
                name=taxonomy.name,
                slug=slugify(taxonomy.name),
                version=taxonomy.version,
            )
        )

    if not taxonomy_list:
        return "No taxonomy found", 404
    return taxonomy_list


def get_by_slug(name_slug, version):
    session = session_factory()
    # we won't have a lot of taxonomy elements so this shouldn't be slow
    for taxonomy in session.query(DBTaxonomy):
        if slugify(taxonomy.name) == name_slug and taxonomy.version == version:
            return Taxonomy(
                id=taxonomy.id,
                name=taxonomy.name,
                slug=name_slug,
                version=taxonomy.version,
            )
    return "Taxonomy not found", 404


def post(name, version):
    session = session_factory()
    taxo = DBTaxonomy(name=name, version=version)
    # todo: conflict
    session.add(taxo)
    try:
        session.commit()
    except IntegrityError:
        return "A taxonomy class having this name and version already exists", 409
    return dataclass_from_object(Taxonomy, taxo)
