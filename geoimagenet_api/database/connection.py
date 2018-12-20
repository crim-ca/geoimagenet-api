from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from geoimagenet_api import config

db = config.get("postgis_db")
username = config.get("postgis_username")
password = config.get("postgis_password")

connection_string = f"postgresql://{username}:{password}@192.168.99.201/{db}"

engine = create_engine(connection_string, echo=True)
Session = sessionmaker(bind=engine)
