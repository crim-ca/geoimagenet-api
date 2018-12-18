from sqlalchemy.exc import IntegrityError

from geoimagenet_api.openapi_schemas import Person
from geoimagenet_api.database.models import Person as DBPerson
from geoimagenet_api.database import Session
from geoimagenet_api.utils import dataclass_from_object


def search(username=None, name=None):
    filter_by = {k: v for k, v in locals().items() if v is not None}
    session = Session()
    persons = session.query(DBPerson).filter_by(**filter_by)
    persons = [dataclass_from_object(Person, p) for p in persons]
    if not persons:
        return "Not Found", 404
    return persons


def get(username):
    session = Session()
    person = session.query(DBPerson).filter_by(username=username).first()
    person = dataclass_from_object(Person, person)
    if not person:
        return "Not Found", 404
    return person


def post(username, name):
    session = Session()
    person = DBPerson(username=username, name=name)
    # todo: conflict
    session.add(person)
    try:
        session.commit()
    except IntegrityError:
        return "Conflict", 409
    return dataclass_from_object(Person, person)
