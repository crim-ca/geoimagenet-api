"""
Important: Some tests don't seem to assert anything.
But the server is setup to validate every input and output using the openapi schema.

So if any json is not valid, it would raise an error.
"""
import string

import pytest
import pp

import random

from tests.utils import api_url


def test_root(client):
    r = client.get(api_url("/"))
    assert r.status_code == 200
    assert "name" in r.json
    assert "version" in r.json


def test_not_found(client):
    r = client.get(api_url("/yadayada"))
    assert r.status_code == 404


@pytest.fixture
def random_user_name():
    length = 10
    return "".join(random.choice(string.ascii_uppercase) for _ in range(length))


def test_add_user(client, random_user_name):
    """Adds a new user and get it using different routes"""
    username = random_user_name
    full_name = "Test User"

    query = {"username": username, "name": full_name}

    r = client.post(api_url("/users"), query_string=query)
    assert r.json["name"] == full_name
    assert r.json["username"]

    r = client.get(api_url("/users"))
    assert any(
        user["username"] == username and user["name"] == full_name for user in r.json
    )

    r = client.get(api_url(f"/users/{username}"))
    assert r.json["username"] == username and r.json["name"] == full_name


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


def test_taxonomy_class_by_id_query_param(client):
    query = {"taxonomy_group_name": "Objets", "id": "2"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)
    assert len(r.json) == 1
    assert r.json[0]["name"]


def test_taxonomy_class_by_id_route(client):
    id_ = 1
    r = client.get(api_url(f"/taxonomy_classes/{id_}"))
    assert r.json["name"] == "Objets"


def test_taxonomy_class_by_id_route_depth_1(client):
    id_ = 1
    query = {"depth": "1"}
    r = client.get(api_url(f"/taxonomy_classes/{id_}"), query_string=query)
    assert len(r.json["children"]) >= 1
    assert len(r.json["children"][0]["children"]) == 0
    assert r.json["name"] == "Objets"


def test_taxonomy_class_by_id_route_infinite_depth(client):
    id_ = 1
    query = {"depth": "-1"}
    r = client.get(api_url(f"/taxonomy_classes/{id_}"), query_string=query)

    def max_depth(obj, depth=0):
        return max([max_depth(c["children"], depth + 1) for c in obj] + [depth])

    assert len(r.json["children"]) >= 1
    depth = max_depth([r.json])
    assert depth >= 3


def test_taxonomy_groups(client):
    query = {"taxonomy_group_name": "Objets", "name": "Objets", "depth": "1"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)
    assert len(r.json) == 1
    assert len(r.json[0]["children"]) >= 1
