from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from geoimagenet_api.config import get_database_url


engine = create_engine(get_database_url(), echo=True)
Session = sessionmaker(bind=engine)
