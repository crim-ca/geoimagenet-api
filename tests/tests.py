"""
Important: Some tests don't seem to assert anything.
But the server is setup to validate every input and output using the openapi schema.

So if any json is not valid, it would raise an error.
"""

import pytest

from geoimagenet_api.tests.utils import get, post, assert_http_error


pytestmark = pytest.mark.usefixtures("server")  # The server is always started


def test_api():
    r = get("/")
    assert r.status_code == 200


def test_not_found():
    with assert_http_error(404):
        get("/yadayada")


def test_taxonomy():
    get("/taxonomy")
