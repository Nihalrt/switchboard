import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager

DATABASE = os.getenv(
    "DATABASE_URL",
    "postgresql://switchboard:switchboard@localhost:5432/switchboard"
)

engine = create_engine(DATABASE)
Sessionlocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
base = declarative_base()

def get_session():
    db_session = sessionlocal()
    try:
        yield db_session
    finally:
        db_session.close()







