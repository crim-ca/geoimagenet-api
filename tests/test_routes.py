from starlette.testclient import TestClient

from geoimagenet_api import application


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["name"] == "GeoImageNet API"
    assert "name" in r.json()
    assert "version" in r.json()
    assert "authors" in r.json()


def test_redirect_v1():
    client = TestClient(application)
    r = client.get("/api", allow_redirects=True)
    assert r.status_code == 200
    assert r.json()["name"] == "GeoImageNet API"


def test_changelog(client):
    r = client.get("/changelog", allow_redirects=True)
    assert r.status_code == 200
    assert r.content.decode().startswith("Changelog")


def test_openapi_json(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert r.json()


def test_not_found(client):
    r = client.get("/yadayada")
    assert r.status_code == 404
