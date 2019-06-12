import pytest

from geoimagenet_api.database.models import Taxonomy, TaxonomyClass
from geoimagenet_api.database.connection import connection_manager


@pytest.fixture
def dummy_taxonomy_0_9(request):
    dummy_taxonomy(request, version="0.9")


@pytest.fixture
def dummy_taxonomy_1_1(request):
    dummy_taxonomy(request, version="1.1")


def dummy_taxonomy(request, version):
    with connection_manager.get_db_session() as session:
        taxo = Taxonomy(name_fr="dummy", version=version)
        session.add(taxo)
        session.flush()
        taxo_class = TaxonomyClass(taxonomy_id=taxo.id, name_fr="dummy class")
        session.add(taxo_class)
        session.commit()

        def finalizer():
            session.delete(taxo_class)
            session.delete(taxo)
            session.commit()

    request.addfinalizer(finalizer)


def test_taxonomy_class_latest_version(client, dummy_taxonomy_0_9):
    r = client.get("/taxonomy_classes")
    assert r.status_code == 200
    names = set([t["name_fr"] for t in r.json()])
    assert names == {"Couverture de sol", "Objets"}


def test_taxonomy_class_latest_version_dummy(client, dummy_taxonomy_1_1):
    r = client.get("/taxonomy_classes")
    assert r.status_code == 200
    names = set([t["name_fr"] for t in r.json()])
    assert names == {"dummy class"}


def test_taxonomy_class_sluggified_name(client):
    query = {"taxonomy_name": "couverture-de-sol", "name": "Residential"}
    r = client.get("/taxonomy_classes", params=query)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert "name_fr" in r.json()[0]


def test_taxonomy_name_not_found(client):
    query = {"taxonomy_name": "not-found", "name": "Residential"}
    r = client.get("/taxonomy_classes", params=query)
    assert r.status_code == 404


def test_taxonomy_class_name_not_found(client):
    query = {"taxonomy_name": "couverture-de-sol", "name": "not-found"}
    r = client.get("/taxonomy_classes", params=query)
    assert r.status_code == 404


def test_taxonomy_class_depth_0(client):
    query = {"taxonomy_name": "Objets", "name": "Objets", "depth": "0"}
    r = client.get("/taxonomy_classes", params=query)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert len(r.json()[0]["children"]) == 0


def test_taxonomy_class_depth_1(client):
    query = {"taxonomy_name": "Objets", "name": "Objets", "depth": "1"}
    r = client.get("/taxonomy_classes", params=query)
    assert len(r.json()) == 1
    assert len(r.json()[0]["children"]) >= 1


def test_taxonomy_class_by_id_route(client):
    id_ = 1
    r = client.get(f"/taxonomy_classes/{id_}")
    assert r.json()["name_fr"] == "Objets"


def test_taxonomy_class_by_id_route_not_found(client):
    id_ = 9999
    r = client.get(f"/taxonomy_classes/{id_}")
    assert r.status_code == 404


def test_taxonomy_class_by_id_route_depth_0(client):
    id_ = 1
    query = {"depth": 0}
    r = client.get(f"/taxonomy_classes/{id_}", params=query)
    assert len(r.json()["children"]) == 0
    assert r.json()["name_fr"] == "Objets"


def test_taxonomy_class_by_id_route_depth_1(client):
    id_ = 1
    query = {"depth": 1}
    r = client.get(f"/taxonomy_classes/{id_}", params=query)
    assert len(r.json()["children"]) >= 1
    assert r.json()["name_fr"] == "Objets"


def test_taxonomy_class_by_id_route_infinite_depth(client):
    id_ = 1
    query = {"depth": -1}
    r = client.get(f"/taxonomy_classes/{id_}", params=query)

    def max_depth(obj, depth=0):
        return max([max_depth(c["children"], depth + 1) for c in obj] + [depth])

    assert len(r.json()["children"]) >= 1
    depth = max_depth([r.json()])
    assert depth >= 3
