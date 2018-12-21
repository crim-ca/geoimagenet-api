import os
import re
from pathlib import Path

import pytest
from geoimagenet_api import config


@pytest.fixture(autouse=True)
def force_reload_config():
    config.config.config_ini = None


@pytest.fixture(autouse=True)
def skip_initial_db_check():
    os.environ["GEOIMAGENET_API_CHECK_DB_CONNECTION_ON_STARTUP"] = 'false'


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


def test_defaults(ignore_custom_ini):
    """Test that the default config is loaded"""
    db = config.get("postgis_db", str)
    username = config.get("postgis_username", str)
    password = config.get("postgis_password", str)

    assert (db, username, password) == ("postgres", "postgres", "postgres")


def test_boolean(ignore_custom_ini):
    """Test for boolean type conversion in config"""
    check = config.get("check_db_connection_on_startup", bool)
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


def test_custom_ini(temp_custom_ini):
    """Test that the default config is loaded"""
    db = config.get("postgis_db", str)

    assert db == "bananas"


def test_environment_variable():
    os.environ["GEOIMAGENET_API_POSTGIS_DB"] = 'bananas'
    db = config.get("postgis_db", str)

    assert db == "bananas"
