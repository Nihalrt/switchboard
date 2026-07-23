import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

def login_db():
    """
    Desc: The function basically logs into the db. If reading the key from the .env file
    fails, func uses the locally set postgress as a fallback.

    """

    return os.getenv("DATABASE_URL", "postgresql://switchboard:switchboard@localhost:5432/switchboard")

engine = create_engine(login_db())
# SessionLocal is not a db session itself. Basically, it opens a new session
# everytime you converse with db, or send queries and then is closed after done.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Starting point of every table defined in the database
base = declarative_base()

def get_db():
    """
    Desc: Creates a db session for each incoming req, giving each req it's own db session
    closed right away after the session. Using "yield db" here so that it can be closed after every session. 
    """
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()