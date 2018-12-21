from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from geoimagenet_api import config


verbose_sqlalchemy = config.get('verbose_sqlalchemy', bool)
engine = create_engine(config.get_database_url(), echo=verbose_sqlalchemy)
Session = sessionmaker(bind=engine)


def check_connection():
    """Checks that the connection to the database is successful"""
    engine.table_names()
