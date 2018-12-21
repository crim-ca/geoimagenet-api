from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from geoimagenet_api.config import get_database_url


engine = create_engine(get_database_url(), echo=True)
Session = sessionmaker(bind=engine)


def check_connection():
    """Checks that the connection to the database is successful"""
    engine.table_names()
