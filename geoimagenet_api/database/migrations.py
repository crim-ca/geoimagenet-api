from contextlib import contextmanager
import os
from pathlib import Path
import sys

import alembic.config


@contextmanager
def cwd(path):
    """Temporarily change cwd"""
    old_pwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_pwd)


def main():
    """Entrypoint for command-line migrations.

    Use the `migrate` command exactly like `alembic`.
    Ex: `migrate upgrade head`
    """
    here = str(Path(__file__).parent)
    print(":: running_migrations ::")
    with cwd(here):
        argv = ["--raiseerr"] + sys.argv[1:]
        alembic.config.main(argv=argv)

