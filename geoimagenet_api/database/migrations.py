from contextlib import contextmanager
import os
from pathlib import Path
import sys
import json
from copy import copy

from sqlalchemy.exc import IntegrityError
from sqlalchemy_utils import database_exists, create_database
import alembic.config

from geoimagenet_api.database.connection import get_engine, session_factory
from geoimagenet_api.database.models import TaxonomyClass, Taxonomy


@contextmanager
def cwd(path):
    """Temporarily change cwd"""
    old_pwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_pwd)


def ensure_database_exists():
    """If the database name given in the config doesn't exist, create it"""
    engine = get_engine()
    if not database_exists(engine.url):
        create_database(engine.url)
        engine.execute("CREATE EXTENSION postgis;")


def migrate():
    """Entrypoint for command-line migrations.

    Use the `migrate` command exactly like `alembic`.
    Ex: `migrate upgrade head`
    """
    here = str(Path(__file__).parent)
    print(":: running_migrations ::")
    with cwd(here):
        argv = ["--raiseerr"] + sys.argv[1:]
        alembic.config.main(argv=argv)


def try_insert(session, class_, **kwargs):
    db_object = session.query(class_).filter_by(**kwargs).first()
    if db_object is None:
        db_object = class_(**kwargs)
        session.add(db_object)
        session.flush()
    return db_object


def load_taxonomy():
    here = Path(__file__).parent
    session = session_factory()

    objets = here / "json_data" / "objets.json"
    couverture = here / "json_data" / "couverture_de_sol.json"

    def recurse_json(obj, parent_taxonomy=None):
        if parent_taxonomy is None:
            taxonomy = try_insert(
                session, Taxonomy, name=obj["name"], version=str(obj["version"])
            )
            taxonomy_id = taxonomy.id
            parent_id = None
        else:
            taxonomy_id = parent_taxonomy.taxonomy_id
            parent_id = parent_taxonomy.id

        taxonomy_class = try_insert(
            session,
            TaxonomyClass,
            taxonomy_id=taxonomy_id,
            name=obj["name"],
            parent_id=parent_id,
        )

        if "value" in obj:
            taxonomy_class.children = [
                recurse_json(o, taxonomy_class) for o in obj["value"]
            ]

        return taxonomy_class

    recurse_json(json.load(objets.open()))
    recurse_json(json.load(couverture.open()))

    session.commit()


def init_database_data():
    """Entrypoint to build an empty database with data.

    While unique constraints shouldn't allow duplicate data,
    you should be careful when loading data into the database.
    Any required migrations will be applied prior to inserting the data.
    """
    ensure_database_exists()
    old_argv = copy(sys.argv)
    sys.argv = [sys.argv[0], "upgrade", "head"]
    migrate()
    sys.argv = old_argv

    load_taxonomy()


if __name__ == "__main__":
    init_database_data()
