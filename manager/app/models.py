from sqlalchemy import Boolean, Column, Integer, String, DateTime
from sqlalchemy.sql import func
from .database import Base

class Flag(Base):
    __tablename__ = 'flags'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    rollout_percentage = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class RoutingEvents(Base):
    __tablename__ = "routing_events"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    flag_name = Column(String, index=True, nullable=False)
    bucket = Column(Integer, nullable=False)
    decision = Column(String, nullable=False)
    outcome = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, index=True)
    flag_name = Column(String, index=True, nullable=False)
    reason = Column(String, nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
