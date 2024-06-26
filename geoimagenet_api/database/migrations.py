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
    if not database_exists(engine.url):  # pragma: no cover
        create_database(engine.url, template="template_postgis")


def _has_alembic_version():
    """Returns True if the database contains an alembic_version table."""
    with connection_manager.get_db_session() as session:
        result = session.execute(
            "SELECT table_name "
            "FROM information_schema.tables "
            "WHERE table_schema='public' "
            "AND table_type='BASE TABLE' "
            "AND table_name='alembic_version';"
        ).first()
        return result is not None


def migrate():
    """Entrypoint for command-line migrations.

    Use the `migrate` command exactly like `alembic`.
    Ex: `migrate upgrade head`
    """
    has_alembic_version = _has_alembic_version()

    here = str(Path(__file__).parent)
    print(":: running_migrations ::")
    with cwd(here):
        argv = ["--raiseerr"] + sys.argv[1:]
        alembic.config.main(argv=argv)

    if not has_alembic_version and sys.argv[1:3] == ["upgrade", "head"]:
        load_taxonomies()


def get_names(names):
    name_fr = names["fr"]
    name_en = names["en"] or None

    return name_fr, name_en


def write_taxonomy(json_path: Path):
    """Writes taxonomy to the database from a json file.

    First checks if the taxonomy name and version is in the taxonomy table.
    If it's there, it stops.
    If not, it writes the taxonomy and taxonomy_class items.

    If any error is raised, the session is rolled back and nothing is written.
    """
    with connection_manager.get_db_session() as session:

        def recurse_json(obj, taxonomy_id, parent_id=None):
            names = obj["name"]
            name_fr, name_en = get_names(names)

            taxonomy_class = models.TaxonomyClass(
                taxonomy_id=taxonomy_id,
                name_fr=name_fr,
                name_en=name_en,
                parent_id=parent_id,
                code=obj["code"],
            )
            session.add(taxonomy_class)
            session.flush()

            if "value" in obj:
                taxonomy_class.children = [
                    recurse_json(o, taxonomy_id, taxonomy_class.id)
                    for o in obj["value"]
                ]

            return taxonomy_class

        def taxonomy_exists(name_fr, version):
            query = session.query(models.Taxonomy).filter_by(
                name_fr=name_fr, version=version
            )
            return query.scalar() is not None

        data = json.loads(json_path.read_text())

        names = data["name"]
        name_fr, name_en = get_names(names)

        version = str(data["version"])

        if not taxonomy_exists(name_fr, version):
            taxonomy = models.Taxonomy(
                name_fr=name_fr, name_en=name_en, version=version
            )
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
        demo_admin = models.Person(
            username="admin", firstname="Demo", lastname="admin", email="admin@crim.ca"
        )
        session.add(demo_admin)
        demo_observateur = models.Person(
            username="observateur",
            firstname="Demo",
            lastname="observateur",
            email="observateur@crim.ca",
        )
        session.add(demo_observateur)
        demo_annotateur = models.Person(
            username="annotateur",
            firstname="Demo",
            lastname="annotateur",
            email="annotateur@crim.ca",
        )
        session.add(demo_annotateur)
        demo_validateur = models.Person(
            username="validateur",
            firstname="Demo",
            lastname="validateur",
            email="validateur@crim.ca",
        )
        session.add(demo_validateur)

        image_data = {
            "sensor_name": "Pleiades",
            "bands": "RGB",
            "bits": 8,
            "filename": "test_image",
            "extension": ".tif",
            "trace": "SRID=3857;POLYGON(("
                     "-8126322.82790897 5465442.18332275,"
                     "-8015003.3371157 5465442.18332275,"
                     "-8015003.3371157 5621521.48619207,"
                     "-8126322.82790897 5621521.48619207,"
                     "-8126322.82790897 5465442.18332275))",
        }
        session.add(models.Image(**image_data))
        image_data["filename"] = "test_image2"
        session.add(models.Image(**image_data))
        image_data["filename"] = "test_image3"
        session.add(models.Image(**image_data))
        try:
            session.commit()
        except IntegrityError:  # pragma: no cover
            session.rollback()
