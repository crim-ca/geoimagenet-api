from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from geoimagenet_api import config


def get_engine():
    verbose_sqlalchemy = config.get("verbose_sqlalchemy", bool)
    return create_engine(config.get_database_url(), echo=verbose_sqlalchemy)


def session_factory():
    engine = get_engine()
    return sessionmaker(bind=engine)()


def wait_for_db_connection(seconds=30):
    """Wait for a successful database connection for a specified time"""
    engine = get_engine()
    while seconds >= 1:
        try:
            engine.execute("SELECT 1;")
            return
        except OperationalError:
            print(f"Can't connect to postgis url. Retrying {seconds}s. ({engine.url})")
            seconds -= 1
            import time
            time.sleep(1)
    import sys
    sys.exit(1)

