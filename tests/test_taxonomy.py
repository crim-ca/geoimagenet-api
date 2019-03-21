from tests.utils import api_url


def test_taxonomy_search_all(client):
    r = client.get(api_url(f"/taxonomy"))
    assert len(r.json) >= 2


def test_taxonomy_versions(client):
    r = client.get(api_url(f"/taxonomy"))
    assert r.status_code == 200
    assert isinstance(r.json[0]["versions"], list)
    assert len(r.json[0]["versions"]) >= 1


def test_taxonomy_root_id(client):
    query = {"name": "Objets", "version": "1"}
    r = client.get(api_url(f"/taxonomy"), query_string=query)
    assert r.json[0]["versions"][0]["root_taxonomy_class_id"] == 1
    query = {"name": "Couverture de sol", "version": "1"}
    r = client.get(api_url(f"/taxonomy"), query_string=query)
    assert r.json[0]["versions"][0]["root_taxonomy_class_id"] == 205


def test_taxonomy_versions_400_version_only(client):
    query = {"version": "1"}
    r = client.get(api_url(f"/taxonomy"), query_string=query)
    assert r.status_code == 400


def test_taxonomy_versions_version_not_found(client):
    query = {"name": "Objets", "version": "10"}
    r = client.get(api_url(f"/taxonomy"), query_string=query)
    assert r.status_code == 404
    assert "Version not found" in r.json


def test_taxonomy_search_by_slug(client):
    query = {"name": "couverture-de-sol", "version": "1"}
    r = client.get(api_url(f"/taxonomy"), query_string=query)
    assert len(r.json) == 1
    assert r.json[0]["name_fr"] == "Couverture de sol"


def test_taxonomy_search_by_name(client):
    query = {"name": "Couverture de sol", "version": "1"}
    r = client.get(api_url(f"/taxonomy"), query_string=query)
    assert len(r.json) == 1
    assert r.json[0]["name_fr"] == "Couverture de sol"


def test_taxonomy_get_by_slug(client):
    name_slug = "couverture-de-sol"
    version = "1"
    r = client.get(api_url(f"/taxonomy/{name_slug}/{version}"))
    assert r.status_code == 200
    assert r.json["name_fr"] == "Couverture de sol"
    assert r.json["root_taxonomy_class_id"] == 205


def test_taxonomy_get_by_slug_not_found(client):
    name_slug = "not-found"
    version = "10"
    r = client.get(api_url(f"/taxonomy/{name_slug}/{version}"))
    assert r.status_code == 404
