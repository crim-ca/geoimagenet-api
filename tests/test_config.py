import pytest
from geoimagenet_api import config


def test_key_error():
    with pytest.raises(KeyError):
        config.get("something_impossible")


def test_defaults():
    """Test that the default config is loaded"""
    db = config.get("postgis_db")
    username = config.get("postgis_username")
    password = config.get("postgis_password")

    assert (db, username, password) == ('postgres', 'postgres', 'postgres')



