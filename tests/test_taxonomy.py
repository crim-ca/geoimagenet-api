from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.endpoints.taxonomy import get_latest_taxonomy_ids
from geoimagenet_api.database.models import Taxonomy


def test_taxonomy_search_all(client):
    r = client.get(f"/taxonomy")
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_taxonomy_versions(client):
    r = client.get(f"/taxonomy")
    assert r.status_code == 200
    groups = r.json()
    assert isinstance(groups[0]["versions"], list)
    assert len(groups[0]["versions"]) >= 1


def test_taxonomy_root_id(client):
    query = {"name": "Objets", "version": "1"}
    r = client.get(f"/taxonomy", params=query)
    groups = r.json()
    assert groups[0]["versions"][0]["root_taxonomy_class_id"] == 1

    query = {"name": "Couverture de sol", "version": "1"}
    r = client.get(f"/taxonomy", params=query)
    groups = r.json()
    assert groups[0]["versions"][0]["root_taxonomy_class_id"] == 195


def test_taxonomy_versions_400_version_only(client):
    query = {"version": "1"}
    r = client.get(f"/taxonomy", params=query)
    assert r.status_code in (400, 422)


def test_taxonomy_versions_version_not_found(client):
    query = {"name": "Objets", "version": "10"}
    r = client.get(f"/taxonomy", params=query)
    assert r.status_code == 404
    assert "Version not found" in r.json()["detail"]


def test_taxonomy_search_by_slug(client):
    query = {"name": "couverture-de-sol", "version": "1"}
    r = client.get(f"/taxonomy", params=query)
    assert len(r.json()) == 1
    assert r.json()[0]["name_fr"] == "Couverture de sol"


def test_taxonomy_search_by_name(client):
    query = {"name": "Couverture de sol", "version": "1"}
    r = client.get(f"/taxonomy", params=query)
    assert len(r.json()) == 1
    assert r.json()[0]["name_fr"] == "Couverture de sol"


def test_taxonomy_get_by_slug(client):
    name_slug = "couverture-de-sol"
    version = "1"
    r = client.get(f"/taxonomy/{name_slug}/{version}")
    assert r.status_code == 200
    assert r.json()["name_fr"] == "Couverture de sol"
    assert r.json()["root_taxonomy_class_id"] == 195


def test_taxonomy_get_by_slug_not_found(client):
    name_slug = "not-found"
    version = "10"
    r = client.get(f"/taxonomy/{name_slug}/{version}")
    assert r.status_code == 404


def test_get_latest_taxonomy_ids():
    # given
    with connection_manager.get_db_session() as session:
        session.add(Taxonomy(name_fr="test", version="1"))
        session.add(Taxonomy(name_fr="test", version="2"))
        latest_test = Taxonomy(name_fr="test", version="3")
        session.add(latest_test)

        latest_test2 = Taxonomy(name_fr="test2", version="v3")
        session.add(latest_test2)
        session.add(Taxonomy(name_fr="test2", version="v1"))
        session.add(Taxonomy(name_fr="test2", version="v2"))
        session.commit()
        test_id = latest_test.id
        test2_id = latest_test2.id

        # when
        ids = get_latest_taxonomy_ids()

        # then
        assert ids["test"] == test_id
        assert ids["test2"] == test2_id

        # cleanup
        session.query(Taxonomy).filter(Taxonomy.name_fr.in_(["test", "test2"])).delete(
            synchronize_session=False
        )
        session.commit()
