from contextlib import contextmanager
import os
from pathlib import Path

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


def upgrade_head():
    here = str(Path(__file__).parent)
    with cwd(here):
        argv = ["--raiseerr", "upgrade", "head"]
        alembic.config.main(argv=argv)
