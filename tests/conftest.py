import pytest

from geoimagenet_api import app


@pytest.fixture(scope="module")
def client():
    app.app.validate_responses = True
    with app.app.test_client() as c:
        yield c
