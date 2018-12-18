from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


engine = create_engine("postgresql://postgres:postgres@192.168.99.201/gis", echo=True)
Session = sessionmaker(bind=engine)
