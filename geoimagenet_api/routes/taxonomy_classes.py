from sqlalchemy.exc import IntegrityError

from geoimagenet_api.openapi_schemas import TaxonomyClass
from geoimagenet_api.database.models import TaxonomyClass as DBTaxonomyClass
from geoimagenet_api.database import Session
from geoimagenet_api.utils import dataclass_from_object


def search(taxonomy_group_name, taxonomy_class_id=None, name=None, depth=0):
    filter_by = {k: v for k, v in locals().items() if v is not None}
    del filter_by["depth"]
    session = Session()
    taxo = session.query(DBTaxonomyClass).filter_by(**filter_by)
    # todo: depth
    taxo = [dataclass_from_object(TaxonomyClass, t) for t in taxo]
    if not taxo:
        return "Not Found", 404
    return taxo


def get(id, depth=0):
    session = Session()
    taxo = session.query(DBTaxonomyClass).filter_by(id=id).first()
    # todo: depth
    taxo = dataclass_from_object(TaxonomyClass, taxo)
    if not taxo:
        return "Not Found", 404
    return taxo


def post(name, taxonomy_group_id):
    session = Session()
    taxo = DBTaxonomyClass(name=name, taxonomy_group_id=taxonomy_group_id)
    # todo: conflict
    session.add(taxo)
    try:
        session.commit()
    except IntegrityError:
        return "Conflict", 409
    return dataclass_from_object(TaxonomyClass, taxo)
