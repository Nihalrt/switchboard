from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from .database import Base

class Flag(Base):
    # Name given to the table inside the db
    __tablename__ = 'flags'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    rollout_percentage = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class RoutingEvents(base):
    __tablename__ = "Routing_events"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    flag_name = Column(String, index=True, nullable=False)
    bucket = Column(String, nullable=False)
    decision = Column(String, nullable=False)
    outcome = Column(String, nullable=True)

class Escalation(base):
    __tablename__ = "Escalations"

    id = Column(integer=True, primary_key=True, index=True)
    flag_name = Column(String, index=True, nullable=False)
    reason = Column(String, nullable=False)
    # False means that Agent2 has failed to resolve the issue, True says otherwise
    resolved = Column(String, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())