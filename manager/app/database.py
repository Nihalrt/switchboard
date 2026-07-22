from sqlalchemy import Column, Integer, String, Datetime
from sqlalchemy.sql import func
from .database import Base

class Flag(base):
    # Name given to the table inside the db
    __tablename__ = 'flags'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    rollout_percentage = Column(Integer, nullable=False, default=0)
    created_at = Column(Datetime(timezone=True), server_default=func.now())
    updated_at = Column(Datetime(timezone=True), server_default=func.now(), onupdate=func.now())
