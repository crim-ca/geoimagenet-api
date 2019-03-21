from tests.utils import api_url


def test_taxonomy_class_sluggified_name(client):
    query = {"taxonomy_name": "couverture-de-sol", "name": "Residential"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)
    assert r.status_code == 200
    assert len(r.json) == 1


def test_taxonomy_class_depth_0(client):
    query = {"taxonomy_name": "Objets", "name": "Objets", "depth": "0"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)
    assert r.status_code == 200
    assert len(r.json) == 1
    assert len(r.json[0]["children"]) == 0


def test_taxonomy_class_depth_1(client):
    query = {"taxonomy_name": "Objets", "name": "Objets", "depth": "1"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)
    assert len(r.json) == 1
    assert len(r.json[0]["children"]) >= 1


def test_taxonomy_class_by_id_query_param(client):
    query = {"taxonomy_name": "Objets", "id": "2"}
    r = client.get(api_url("/taxonomy_classes"), query_string=query)
    assert len(r.json) == 1
    assert r.json[0]["name_fr"] == "Bâtiment résidentiel"


def test_taxonomy_class_by_id_route(client):
    id_ = 1
    r = client.get(api_url(f"/taxonomy_classes/{id_}"))
    assert r.json["name_fr"] == "Objets"


def test_taxonomy_class_by_id_route_depth_1(client):
    id_ = 1
    query = {"depth": "1"}
    r = client.get(api_url(f"/taxonomy_classes/{id_}"), query_string=query)
    assert len(r.json["children"]) >= 1
    assert r.json["name_fr"] == "Objets"


def test_taxonomy_class_by_id_route_infinite_depth(client):
    id_ = 1
    query = {"depth": "-1"}
    r = client.get(api_url(f"/taxonomy_classes/{id_}"), query_string=query)

    def max_depth(obj, depth=0):
        return max([max_depth(c["children"], depth + 1) for c in obj] + [depth])

    assert len(r.json["children"]) >= 1
    depth = max_depth([r.json])
    assert depth >= 3
