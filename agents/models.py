from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

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

class InteractionFinding(Base):
    __tablename__ = "interaction_findings"

    id = Column(Integer, primary_key=True, index=True)
    flag_a = Column(String, nullable=False)
    flag_b = Column(String, nullable=False)
    overlap_sample_size = Column(Integer, nullable=False)
    overlap_failure_rate = Column(Float, nullable=False)
    baseline_failure_rate = Column(Float, nullable=False)
    p_value = Column(Float, nullable=False)
    likely_cause = Column(String, nullable=False) # Gemini output
    reason = Column(String, nullable=False) # Gemini's reason
    created_at = Column(DateTime(timezone=True), server_default=func.now())