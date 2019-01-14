import os

import pytest
from sqlalchemy_utils import drop_database, create_database

from geoimagenet_api.database import migrations
from geoimagenet_api import make_app
from geoimagenet_api.database.connection import connection_manager


@pytest.fixture(scope="session", autouse=True)
def reset_test_database():
    """Reset the database to a brand new clean state.

    - Create the database if it doesn't exist and install postgis extension
    - Drop all tables except 'spatial_ref_sys'
    - Initialize the database with data (taxonomy, etc.)
    """

    # configuration
    os.environ["GEOIMAGENET_API_POSTGIS_DB"] = "geoimagenet_test"
    os.environ["GEOIMAGENET_API_VERBOSE_SQLALCHEMY"] = "false"
    connection_manager.reload_config()

    db_url = connection_manager.engine.url

    drop_database(db_url)
    create_database(db_url, template="template_postgis")

    # run migrations and initiate base data
    migrations.init_database_data()


@pytest.fixture(scope="module")
def client():
    app = make_app(validate_responses=True)

    with app.app.test_client() as c:
        yield c
