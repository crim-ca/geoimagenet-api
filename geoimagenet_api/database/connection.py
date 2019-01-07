from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from geoimagenet_api import config


def get_engine():
    verbose_sqlalchemy = config.get("verbose_sqlalchemy", bool)
    return create_engine(config.get_database_url(), echo=verbose_sqlalchemy)


def session_factory():
    engine = get_engine()
    return sessionmaker(bind=engine)()


def check_connection():
    """Checks that the connection to the database is successful"""
    engine = get_engine()
    engine.table_names()
