import contextlib

import requests
from requests import exceptions

from geoimagenet_api.tests import TEST_SERVER_URL


def join_url(*args):
    return "/".join(s.strip("/") for s in args)


def raise_for_status_with_detail(response):
    try:
        response.raise_for_status()
    except exceptions.HTTPError as e:
        detail = response.json().get("detail")
        message = "HTTPError {}: {}".format(response.status_code, detail)
        e.args = tuple([message, *e.args[1:]])
        raise e


def get(path):
    url = join_url(TEST_SERVER_URL, path)
    response = requests.get(url)
    raise_for_status_with_detail(response)
    return response


def post(path, data):
    url = join_url(TEST_SERVER_URL, path)
    response = requests.post(url, data=data)
    raise_for_status_with_detail(response)
    return response


@contextlib.contextmanager
def assert_http_error(code):
    try:
        yield
    except exceptions.HTTPError as error:
        assert error.response.status_code == code
        return
    raise RuntimeError("Expected an http error: {}".format(code))
