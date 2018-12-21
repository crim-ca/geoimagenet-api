import os
import re
from pathlib import Path

import pytest
from geoimagenet_api import config


@pytest.fixture(autouse=True)
def force_reload_config():
    config.config.config_ini = None


def test_key_error():
    with pytest.raises(KeyError):
        config.get("something_impossible")


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
    db = config.get("postgis_db")
    username = config.get("postgis_username")
    password = config.get("postgis_password")

    assert (db, username, password) == ("postgres", "postgres", "postgres")


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
    db = config.get("postgis_db")

    assert db == "bananas"


