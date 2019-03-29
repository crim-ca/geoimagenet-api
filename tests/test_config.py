import os
import re
from pathlib import Path
from unittest import mock

import pytest
from geoimagenet_api import config
from geoimagenet_api.config.config import ENVIRONMENT_PREFIX


@pytest.fixture(autouse=True)
def force_reload_config():
    config.config.config_ini = None


@pytest.fixture(autouse=True)
def skip_initial_db_check():
    os.environ["GEOIMAGENET_API_CHECK_DB_CONNECTION_ON_STARTUP"] = "false"


def test_key_error():
    with pytest.raises(KeyError):
        config.get("something_impossible", str)


@pytest.fixture
def ignore_custom_ini(request):
    """
    Replace the config.ini file for the duration of the test and put it back afterwards.
    """
    custom_ini_path = Path(config.__file__).with_name("custom.ini")
    previous_custom_data = None
    if os.path.exists(custom_ini_path):
        previous_custom_data = custom_ini_path.read_text()
        custom_ini_path.unlink()

    def write_data_back():
        if previous_custom_data is not None:
            custom_ini_path.write_text(previous_custom_data)

    request.addfinalizer(write_data_back)


@pytest.fixture
def ignore_environment_variables(request):
    """
    Replace environment variables for the duration of the test and put them back afterwards.
    """
    previous_environ = {
        k: v for k, v in os.environ.items() if k.startswith(ENVIRONMENT_PREFIX)
    }
    for k in previous_environ:
        os.environ.pop(k)

    def set_os_environ_back():
        if previous_environ:
            for k, v in previous_environ.items():
                os.environ[k] = v

    request.addfinalizer(set_os_environ_back)


def test_defaults(ignore_custom_ini, ignore_environment_variables):
    """Test that the default config is loaded"""
    db = config.get("postgis_db", str)
    username = config.get("postgis_user", str)
    password = config.get("postgis_password", str)

    assert (db, username, password) == ("postgres", "postgres", "postgres")


def test_boolean(ignore_custom_ini, ignore_environment_variables):
    """Test for boolean type conversion in config"""
    check = config.get("verbose_sqlalchemy", bool)
    assert not check


@pytest.fixture
def temp_custom_ini(request):
    """
    Replace the config.ini file for the duration of the test and put it back afterwards.
    """
    custom_ini_path = Path(config.__file__).with_name("custom.ini")
    previous_custom_data = None
    if os.path.exists(custom_ini_path):
        previous_custom_data = custom_ini_path.read_text()
    default_config_data = Path(config.__file__).with_name("default.ini").read_text()

    test_config_data = re.sub(
        r"postgis_db = (.+)", "postgis_db = bananas", default_config_data
    )
    custom_ini_path.write_text(test_config_data)

    def write_data_back():
        if previous_custom_data is not None:
            custom_ini_path.write_text(previous_custom_data)

    request.addfinalizer(write_data_back)


def test_custom_ini(temp_custom_ini, ignore_environment_variables):
    """Test that the default config is loaded"""
    db = config.get("postgis_db", str)

    assert db == "bananas"


@pytest.fixture
def temp_environment_variable_db(request):
    old = os.environ.get("GEOIMAGENET_API_POSTGIS_DB")

    os.environ["GEOIMAGENET_API_POSTGIS_DB"] = "bananas"

    def put_back_environment():
        if old is not None:
            os.environ["GEOIMAGENET_API_POSTGIS_DB"] = old
        else:
            del os.environ["GEOIMAGENET_API_POSTGIS_DB"]

    request.addfinalizer(put_back_environment)


def test_environment_variable(temp_environment_variable_db):
    db = config.get("postgis_db", str)

    assert db == "bananas"


def test_convert_bool():
    with pytest.raises(ValueError):
        config.config._convert_bool("hehe")

    assert config.config._convert_bool("1")
    assert config.config._convert_bool("true")
    assert config.config._convert_bool("YES")

    assert not config.config._convert_bool("0")
    assert not config.config._convert_bool("false")
    assert not config.config._convert_bool("NO")


def test_sentry(ignore_custom_ini, ignore_environment_variables):
    old = os.environ.get("GEOIMAGENET_API_SENTRY_URL", "")

    os.environ["GEOIMAGENET_API_SENTRY_URL"] = "http://test"

    import importlib
    import geoimagenet_api

    with mock.patch("geoimagenet_api.sentry_sdk.init") as p:
        importlib.reload(geoimagenet_api)
        assert p.called
        assert p.call_args_list[0][1]["dsn"] == "http://test"

    assert geoimagenet_api.sentry_sdk

    os.environ["GEOIMAGENET_API_SENTRY_URL"] = old
