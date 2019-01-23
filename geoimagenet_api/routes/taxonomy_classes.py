from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from geoimagenet_api.openapi_schemas import TaxonomyClass
from geoimagenet_api.database.models import TaxonomyClass as DBTaxonomyClass
from geoimagenet_api.database.models import Taxonomy as DBTaxonomy
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import dataclass_from_object


def search(taxonomy_name, id=None, name=None, depth=-1):
    with connection_manager.get_db_session() as session:
        depth = 9999 if depth == -1 else depth
        try:
            taxonomy = session.query(DBTaxonomy).filter_by(name=taxonomy_name).one()
        except NoResultFound:
            return f"Taxonomy not found: {taxonomy_name}", 404

        filter_by = {"taxonomy_id": taxonomy.id}
        if id is None and name is None:
            # todo add response code 400
            return "Please provide one of: id, name", 400
        if id is not None:
            filter_by["id"] = id
        if name is not None:
            filter_by["name"] = name

        taxo = session.query(DBTaxonomyClass).filter_by(**filter_by).all()
        taxo = [dataclass_from_object(TaxonomyClass, t, depth=depth) for t in taxo]

    if not taxo:
        return "No taxonomy class found", 404
    return taxo


def get(id, depth=-1):
    with connection_manager.get_db_session() as session:
        depth = 9999 if depth == -1 else depth
        taxo = session.query(DBTaxonomyClass).filter_by(id=id).first()
        taxo = dataclass_from_object(TaxonomyClass, taxo, depth=depth)
    if not taxo:
        return "Taxonomy class id not found", 404
    return taxo
