def test_get_users(client):
    r = client.get("/users")
    demo_users = [
        {'id': 1, 'username': 'admin', 'name': 'Demo admin'},
        {'id': 2, 'username': 'observateur', 'name': 'Demo observateur'},
        {'id': 3, 'username': 'annotateur', 'name': 'Demo annotateur'},
        {'id': 4, 'username': 'validateur', 'name': 'Demo validateur'}
    ]
    for user in demo_users:
        assert user in r.json()

    assert client.get('/users/observateur').json()['name'] == "Demo observateur"
    assert client.get('/users/annotateur').json()['name'] == "Demo annotateur"
    assert client.get('/users/validateur').json()['name'] == "Demo validateur"
    assert client.get('/users/admin').json()['name'] == "Demo admin"

    assert client.get('/users/qqqqq').status_code == 404

    query = {"name": "Demo observateur"}
    assert client.get("/users", params=query).json()[0]['username'] == "observateur"
    query = {"username": "observateur"}
    assert client.get("/users", params=query).json()[0]['username'] == "observateur"
    query = {"username": "observateur", "name": "Demo observateur"}
    assert client.get("/users", params=query).json()[0]['username'] == "observateur"
    query = {"username": "qqqqq", "name": "Demo observateur"}
    assert client.get("/users", params=query).status_code == 404
