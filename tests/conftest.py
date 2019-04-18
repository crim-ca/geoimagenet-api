import os
import random

import pytest
from sqlalchemy_utils import drop_database, create_database, database_exists
from starlette.testclient import TestClient

from geoimagenet_api.database import migrations
from geoimagenet_api import app, application
from geoimagenet_api.database.connection import connection_manager


@pytest.fixture
def noisy_sqlalchemy(request):
    os.environ["GEOIMAGENET_API_VERBOSE_SQLALCHEMY"] = "True"
    connection_manager.reload_config()

    def not_noizy():
        os.environ["GEOIMAGENET_API_VERBOSE_SQLALCHEMY"] = "false"
        connection_manager.reload_config()

    request.addfinalizer(not_noizy)


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

    if database_exists(db_url):
        drop_database(db_url)
    create_database(db_url, template="template_postgis")

    # run migrations and initiate base data
    migrations.init_database_data()
    migrations.load_testing_data()

    randomize_taxonomy_classes()


def randomize_taxonomy_classes():
    """Randomize the return value of TaxonomyClass. This is necessary to test some algorithms."""
    from geoimagenet_api.database.models import TaxonomyClass

    with connection_manager.get_db_session() as session:
        ids = session.query(TaxonomyClass.id).all()
        for n in range(len(ids)):
            session.execute(
                "UPDATE taxonomy_class SET id = id WHERE id = :id;",
                {"id": random.choice(ids).id},
            )
        session.commit()


@pytest.fixture(scope="module")
def client():
    yield TestClient(app)


@pytest.fixture(scope="module")
def client_application():
    yield TestClient(application)
