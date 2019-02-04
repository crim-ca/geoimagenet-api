from tests.utils import random_user_name, api_url


def test_add_user(client):
    """Adds a new user and get it using different routes"""
    username = random_user_name()
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