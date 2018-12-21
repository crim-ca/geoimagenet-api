from contextlib import contextmanager
import os
from pathlib import Path
import sys
import json
from copy import copy

import alembic.config
from geoimagenet_api.database.connection import Session
from geoimagenet_api.database.models import TaxonomyClass, TaxonomyGroup


@contextmanager
def cwd(path):
    """Temporarily change cwd"""
    old_pwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_pwd)


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


def load_taxonomy():
    here = Path(__file__).parent
    session = Session()

    objets = here / "json_data" / "objets.json"
    couverture = here / "json_data" / "couverture_de_sol.json"

    def recurse_json(obj, parent_taxonomy=None):
        if parent_taxonomy is None:
            taxonomy_group = TaxonomyGroup(name=obj["name"], version=obj["version"])
            session.add(taxonomy_group)
            session.flush()
            taxonomy_group_id = taxonomy_group.id
            parent_id = None
        else:
            taxonomy_group_id = parent_taxonomy.taxonomy_group_id
            parent_id = parent_taxonomy.id

        taxonomy_class = TaxonomyClass(
            taxonomy_group_id=taxonomy_group_id, name=obj["name"], parent_id=parent_id
        )
        session.add(taxonomy_class)
        session.flush()

        if 'value' in obj:
            taxonomy_class.children = [recurse_json(o, taxonomy_class) for o in obj["value"]]

        return taxonomy_class

    recurse_json(json.load(objets.open()))
    recurse_json(json.load(couverture.open()))

    session.commit()


def init_database_data():
    """Entrypoint to build an empty database with data.

    While unique constraints shouldn't allow duplicate data,
    You should be careful when loading data into the database.
    Any required migrations will be applied prior to inserting the data.
    """
    old_argv = copy(sys.argv)
    sys.argv = [sys.argv[0], "upgrade", "head"]
    migrate()
    sys.argv = old_argv

    load_taxonomy()


if __name__ == "__main__":
    init_database_data()
