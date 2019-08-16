import pytest
from unittest import mock

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import Person

from geoimagenet_api.openapi_schemas import User

import geoimagenet_api.endpoints.users as users_routes


def test_get_logged_user():
    request = mock.Mock()
    request.cookies = {"auth_tkt": "long_auth_token"}

    mock_json = {
        "code": 200,
        "type": "application/json",
        "user": {
            "user_id": 99,
            "user_name": "super_admin",
            "email": "super_admin@mail.com",
            "group_names": ["anonymous"],
        },
        "detail": "Get user successful.",
    }

    with mock.patch("geoimagenet_api.endpoints.users.requests") as mock_requests:
        response = mock.Mock()
        response.json.return_value = mock_json
        mock_requests.get.return_value = response
        user_id = users_routes.get_logged_user_id(request)
        assert user_id == 99

    # cleanup
    with connection_manager.get_db_session() as session:
        session.query(Person).filter_by(id=99).delete()
        session.commit()


def test_create_user_if_its_not_in_database():
    magpie_user = User(
        id=99,
        username="super_user",
        email="email",
    )
    users_routes._update_user_data(magpie_user)
    with connection_manager.get_db_session() as session:
        assert session.query(Person).filter_by(id=99).scalar().username == "super_user"


def test_update_user_information():
    magpie_user = User(
        id=99,
        username="username",
        email="email",
        firstname="firstname",
        lastname="lastname",
        organisation="organisation",
    )
    users_routes._update_user_data(magpie_user)

    magpie_user = User(
        id=99,
        username="super_username",
        email="super_email",
        firstname="super_firstname",
        lastname="super_lastname",
        organisation="super_organisation",
    )
    users_routes._update_user_data(magpie_user)
    with connection_manager.get_db_session() as session:
        user = session.query(Person).filter_by(id=99).scalar()
        assert user.username == "super_username"
        assert user.email == "super_email"
        assert user.firstname == "super_firstname"
        assert user.lastname == "super_lastname"
        assert user.organisation == "super_organisation"
