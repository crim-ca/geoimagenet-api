from multiprocessing import Process

import pytest

from geoimagenet_api import get_app
from geoimagenet_api.tests import TEST_SERVER_PORT


@pytest.fixture(scope="module")
def server(request):
    """Start a test server that validates both requests and responses"""
    app = get_app(validate_responses=True)
    app.port = TEST_SERVER_PORT

    process = Process(target=app.run)
    process.start()

    request.addfinalizer(process.terminate)
