from contextlib import contextmanager
import os
from pathlib import Path
import sys
import json
from copy import copy

from sqlalchemy.exc import IntegrityError
from sqlalchemy_utils import database_exists, create_database
import alembic.config

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database import models


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
    engine = connection_manager.engine
    if not database_exists(engine.url):
        create_database(engine.url, template="template_postgis")


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


def write_taxonomy(json_path: Path):
    """Writes taxonomy to the database from a json file.

    First checks if the taxonomy name and version is in the taxonomy table.
    If it's there, it stops.
    If not, it writes the taxonomy and taxonomy_class items.

    If any error is raised, the session is rolled back and nothing is written.
    """
    with connection_manager.get_db_session() as session:

        def recurse_json(obj, taxonomy_id, parent_id=None):
            taxonomy_class = models.TaxonomyClass(
                taxonomy_id=taxonomy_id, name=obj["name"], parent_id=parent_id
            )
            session.add(taxonomy_class)
            session.flush()

            if "value" in obj:
                taxonomy_class.children = [
                    recurse_json(o, taxonomy_id, taxonomy_class.id)
                    for o in obj["value"]
                ]

            return taxonomy_class

        def taxonomy_exists(name, version):
            query = session.query(models.Taxonomy).filter_by(name=name, version=version)
            return query.scalar() is not None

        data = json.loads(json_path.read_text())

        name = data["name"]
        version = str(data["version"])

        if not taxonomy_exists(name, version):
            taxonomy = models.Taxonomy(name=name, version=version)
            session.add(taxonomy)
            session.flush()
            recurse_json(data, taxonomy.id)

            session.commit()


def load_taxonomies():
    json_data = Path(__file__).parent / "json_data"
    write_taxonomy(json_data / "objets.json")
    write_taxonomy(json_data / "couverture_de_sol.json")


def load_testing_data():
    with connection_manager.get_db_session() as session:

        # add some Users
        demo_admin = models.Person(username="admin", name="Demo admin")
        session.add(demo_admin)
        demo_observateur = models.Person(username="observateur", name="Demo observateur")
        session.add(demo_observateur)
        demo_annotateur = models.Person(username="annotateur", name="Demo annotateur")
        session.add(demo_annotateur)
        demo_validateur = models.Person(username="validateur", name="Demo validateur")
        session.add(demo_validateur)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()


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

    load_taxonomies()

    if "--testing" in sys.argv:
        load_testing_data()


if __name__ == "__main__":
    init_database_data()
