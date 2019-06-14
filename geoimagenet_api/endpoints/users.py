from typing import List, Union

import requests
import sentry_sdk
from starlette.requests import Request

from geoimagenet_api.config import config

from fastapi import APIRouter
from starlette.exceptions import HTTPException
from geoimagenet_api.openapi_schemas import User
from geoimagenet_api.database.models import Person
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import get_config_url

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


def get_magpie_user_id(request: Request) -> Union[None, int]:
    """Requests the current logged in user id from magpie.

    Raises an instance of any `requests.exceptions` when there is a connection error.
    """

    # todo: if the user doesn't exist in the database, create it

    magpie_url = get_config_url(request, "magpie_url")
    user_url = f"{magpie_url}/users/current"

    verify_ssl = config.get("magpie_verify_ssl", bool)
    response = requests.get(user_url, cookies=request.cookies, verify=verify_ssl)
    response.raise_for_status()

    data = response.json()
    user_data = data['user']
    user_id = user_data.get('user_id')

    return user_id


@router.get("/users/current", response_model=User, summary="Get currently logged in user")
def current(request: Request):
    try:
        logged_user = get_magpie_user_id(request)
    except requests.exceptions.RequestException:
        sentry_sdk.capture_exception()
        return "There was a problem connecting to magpie. This error was reported to the developers.", 503
    if logged_user is None:
        return "You are not logged in to magpie.", 204
    return logged_user, 200
