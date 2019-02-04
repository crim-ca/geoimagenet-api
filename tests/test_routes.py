"""
Important: Some tests don't seem to assert anything.
But the server is setup to validate every input and output using the openapi schema.

So if any json is not valid, it would raise an error.
"""

from tests.utils import api_url


def test_root(client):
    r = client.get(api_url("/"))
    assert r.status_code == 200
    assert "name" in r.json
    assert "version" in r.json
    assert "authors" in r.json


def test_not_found(client):
    r = client.get(api_url("/yadayada"))
    assert r.status_code == 404
