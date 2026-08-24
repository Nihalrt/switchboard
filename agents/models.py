from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class RoutingEvents(Base):
    __tablename__ = "routing_events"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    flag_name = Column(String, index=True, nullable=False)
    bucket = Column(Integer, nullable=False)
    decision = Column(String, nullable=False)
    outcome = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True))


class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, index=True)
    flag_name = Column(String, index=True, nullable=False)
    reason = Column(String, nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True))