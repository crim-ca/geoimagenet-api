def test_get_users(client):
    assert client.get('/users/observateur').json()['name'] == "Demo observateur"
    assert client.get('/users/annotateur').json()['name'] == "Demo annotateur"
    assert client.get('/users/validateur').json()['name'] == "Demo validateur"
    assert client.get('/users/admin').json()['name'] == "Demo admin"

    assert client.get('/users/qqqqq').status_code == 404
