from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://user:password@localhost:5432/mydatabase"

def get_engine():
    return create_engine(DATABASE_URL, echo=True)

def get_session():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()