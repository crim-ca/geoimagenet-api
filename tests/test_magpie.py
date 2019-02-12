import pytest
from unittest import mock

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
        user_id = users_routes.get_user_id_from_cookies(request)
        assert user_id == 99
