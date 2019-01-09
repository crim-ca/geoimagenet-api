from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from geoimagenet_api.openapi_schemas import TaxonomyClass
from geoimagenet_api.database.models import TaxonomyClass as DBTaxonomyClass
from geoimagenet_api.database.models import TaxonomyGroup as DBTaxonomyGroup
from geoimagenet_api.database import session_factory
from geoimagenet_api.utils import dataclass_from_object


def search(taxonomy_group_name, id=None, name=None, depth=-1):
    session = session_factory()
    depth = 9999 if depth == -1 else depth
    try:
        taxonomy_group = session.query(DBTaxonomyGroup).filter_by(name=taxonomy_group_name).one()
    except NoResultFound:
        return f"Taxonomy group not found: {taxonomy_group_name}", 404

    filter_by = {'taxonomy_group_id': taxonomy_group.id}
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
    session = session_factory()
    depth = 9999 if depth == -1 else depth
    taxo = session.query(DBTaxonomyClass).filter_by(id=id).first()
    taxo = dataclass_from_object(TaxonomyClass, taxo, depth=depth)
    if not taxo:
        return "Taxonomy class id not found", 404
    return taxo


def post(name, taxonomy_group_id):
    session = session_factory()
    taxo = DBTaxonomyClass(name=name, taxonomy_group_id=taxonomy_group_id)
    session.add(taxo)
    try:
        session.commit()
    except IntegrityError:
        return "A taxonomy class having this name and parent_id already exists", 409
    return dataclass_from_object(TaxonomyClass, taxo)
