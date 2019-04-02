from typing import List

from fastapi import APIRouter
from starlette.exceptions import HTTPException
from geoimagenet_api.openapi_schemas import User
from geoimagenet_api.database.models import Person
from geoimagenet_api.database.connection import connection_manager

router = APIRouter()


@router.get("/users", response_model=List[User], summary="Search")
def search(username: str = None, name: str = None):
    with connection_manager.get_db_session() as session:
        query = session.query(Person)
        if username is not None:
            query = query.filter_by(username=username)
        if name is not None:
            query = query.filter_by(name=name)

        users_all = query.all()
        if not users_all:
            raise HTTPException(404, "No user found")
        return users_all


@router.get("/users/{username}", response_model=User, summary="Get user by username")
def get(username: str):
    with connection_manager.get_db_session() as session:
        person = session.query(Person).filter_by(username=username).first()
        if not person:
            raise HTTPException(404, "Username not found")

        return person