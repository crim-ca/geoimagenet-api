from sqlalchemy.exc import IntegrityError

from geoimagenet_api.openapi_schemas import User
from geoimagenet_api.database.models import Person
from geoimagenet_api.database import session_factory
from geoimagenet_api.utils import dataclass_from_object


def search(username=None, name=None):
    filter_by = {k: v for k, v in locals().items() if v is not None}
    session = session_factory()
    persons = session.query(Person).filter_by(**filter_by)
    users = [dataclass_from_object(User, p) for p in persons]
    if not users:
        return "No user found", 404
    return users


def get(username):
    session = session_factory()
    person = session.query(Person).filter_by(username=username).first()
    user = dataclass_from_object(User, person)
    if not user:
        return "username not found", 404
    return user


def post(username, name):
    session = session_factory()
    person = Person(username=username, name=name)
    session.add(person)
    try:
        session.commit()
    except IntegrityError:
        return "A user with this username already exists", 409
    return dataclass_from_object(User, person)
