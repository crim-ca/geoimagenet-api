from multiprocessing import Process

import pytest

from geoimagenet_api import app
from tests import TEST_SERVER_PORT


@pytest.fixture(scope="module")
def server(request):
    """Start a test server that validates both requests and responses"""
    app.app.validate_responses = True
    app.port = TEST_SERVER_PORT

    process = Process(target=app.run)
    process.start()

    request.addfinalizer(process.terminate)
