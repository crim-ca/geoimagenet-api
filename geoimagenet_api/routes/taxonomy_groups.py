from sqlalchemy.exc import IntegrityError

from geoimagenet_api.openapi_schemas import TaxonomyGroup
from geoimagenet_api.database.models import TaxonomyGroup as DBTaxonomyGroup
from geoimagenet_api.database import session_factory
from geoimagenet_api.utils import dataclass_from_object


def search(name=None, version=None):
    filter_by = {k: v for k, v in locals().items() if v is not None}
    session = session_factory()
    taxo = session.query(DBTaxonomyGroup).filter_by(**filter_by)
    taxo = [dataclass_from_object(TaxonomyGroup, t) for t in taxo]
    if not taxo:
        return "No taxonomy group found", 404
    return taxo


def get(id):
    session = session_factory()
    taxo = session.query(DBTaxonomyGroup).filter_by(id=id).first()
    taxo = dataclass_from_object(TaxonomyGroup, taxo)
    if not taxo:
        return "Taxonomy group id not found", 404
    return taxo


def post(name, version):
    session = session_factory()
    taxo = DBTaxonomyGroup(name=name, version=version)
    # todo: conflict
    session.add(taxo)
    try:
        session.commit()
    except IntegrityError:
        return "A taxonomy class having this name and version already exists", 409
    return dataclass_from_object(TaxonomyGroup, taxo)
