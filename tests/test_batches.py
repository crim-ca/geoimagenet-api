from tests.utils import api_url


def test_batches_search_all(client):
    r = client.get(api_url(f"/batches"))
