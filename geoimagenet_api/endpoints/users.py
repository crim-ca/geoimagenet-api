from typing import Optional

import requests
import sentry_sdk
from geoimagenet_api.database.connection import connection_manager
from starlette.requests import Request

from geoimagenet_api.config import config

from fastapi import APIRouter, HTTPException

from geoimagenet_api.database.models import Person
from geoimagenet_api.openapi_schemas import User
from geoimagenet_api.utils import get_config_url

router = APIRouter()


def _get_magpie_user(request: Request) -> User:
    """Requests the current logged in user id from magpie.

    Raises an instance of any `requests.exceptions.RequestException` when there is a connection error.
    """
    magpie_url = get_config_url(request, "magpie_url")
    user_url = f"{magpie_url}/users/current"

    verify_ssl = config.get("magpie_verify_ssl", bool)
    response = requests.get(
        user_url, cookies=request.cookies, verify=verify_ssl, timeout=5
    )
    response.raise_for_status()

    data = response.json()
    user_data = data["user"]

    magpie_user = User(
        id=user_data.get("user_id"),
        username=user_data.get("user_name"),
        email=user_data.get("email"),
    )

    _update_user_data(magpie_user)

    return magpie_user


def _update_user_data(magpie_user: User):
    """If the user doesn't exist in the database, create it"""
    if magpie_user.id is not None:
        with connection_manager.get_db_session() as session:
            stored_user_data = (
                session.query(Person).filter_by(id=magpie_user.id).first()
            )
            if not stored_user_data:
                session.add(
                    Person(
                        id=magpie_user.id,
                        username=magpie_user.username,
                        email=magpie_user.email,
                        firstname=magpie_user.firstname,
                        lastname=magpie_user.lastname,
                        organisation=magpie_user.organisation,
                    )
                )
                session.commit()
            else:
                stored_user_data.username = magpie_user.username
                stored_user_data.email = magpie_user.email
                stored_user_data.firstname = magpie_user.firstname
                stored_user_data.lastname = magpie_user.lastname
                stored_user_data.organisation = magpie_user.organisation
                session.commit()


def get_logged_user_id(request: Request, raise_if_logged_out=True) -> Optional[int]:
    try:
        logged_user = _get_magpie_user(request)
    except requests.exceptions.RequestException:  # pragma: no cover
        sentry_sdk.capture_exception()
        raise HTTPException(
            503,
            "There was a problem connecting to magpie. This error was reported to the developers.",
        )
    if raise_if_logged_out and logged_user.id is None:  # pragma: no cover
        raise HTTPException(403, "You are not logged in.")
    return logged_user.id
