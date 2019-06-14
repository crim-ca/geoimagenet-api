def test_get_users(client):
    assert client.get('/users/observateur').json()['email'] == "observateur@crim.ca"
    assert client.get('/users/annotateur').json()['email'] == "annotateur@crim.ca"
    assert client.get('/users/validateur').json()['email'] == "validateur@crim.ca"
    assert client.get('/users/admin').json()['email'] == "admin@crim.ca"

    assert client.get('/users/qqqqq').status_code == 404
