"""
Important: Some tests don't seem to assert anything.
But the server is setup to validate every input and output using the openapi schema.

So if any json is not valid, it would raise an error.
"""

import pytest

from tests.utils import api_url


def test_root(client):
    r = client.get(api_url("/"))
    assert r.status_code == 200
    assert "name" in r.json
    assert "version" in r.json


def test_not_found(client):
    r = client.get(api_url("/yadayada"))
    assert r.status_code == 404


def test_taxonomy_class_depth_0(client):
    query = {"taxonomy_group_name": "Objets", "name": "Objets", "depth": "0"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)
    assert len(r.json) == 1
    assert len(r.json[0]["children"]) == 0


def test_taxonomy_class_depth_1(client):
    query = {"taxonomy_group_name": "Objets", "name": "Objets", "depth": "1"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)
    assert len(r.json) == 1
    assert len(r.json[0]["children"]) >= 1
