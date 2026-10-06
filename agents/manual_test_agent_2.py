"""Seed a local cross-flag failure and run Agent 2 against it.

Requirements:
* local PostgreSQL is running;
* the Manager-owned routing_events and escalations tables already exist;
* GEMINI_API_KEY is configured in agents/.env.

This script inserts two unresolved escalations directly so the test isolates
Agent 2's behavior.
"""

import random

from Agent2 import evaluate_all_escalations
from db import engine, get_session
from models import Escalation, InteractionFinding, RoutingEvents

FLAG_A = "test_interaction_flag_a"
FLAG_B = "test_interaction_flag_b"
DEVICE_COUNT = 5000
ROLLOUT_A = 0.20
ROLLOUT_B = 0.20
OVERLAP_FAILURE_RATE = 0.40
OTHER_FAILURE_RATE = 0.03


def create_agent_2_table() -> None:
    InteractionFinding.__table__.create(bind=engine, checkfirst=True)


def clear_previous_test_data() -> None:
    with get_session() as session:
        session.query(RoutingEvents).filter(
            RoutingEvents.flag_name.in_([FLAG_A, FLAG_B])
        ).delete(synchronize_session=False)
        session.query(Escalation).filter(
            Escalation.flag_name.in_([FLAG_A, FLAG_B])
        ).delete(synchronize_session=False)
        session.query(InteractionFinding).filter(
            InteractionFinding.flag_a.in_([FLAG_A, FLAG_B])
        ).delete(synchronize_session=False)
        session.commit()


def seed_interaction() -> None:
    random_source = random.Random(42)

    with get_session() as session:
        session.add(Escalation(flag_name=FLAG_A, reason="Agent 1 requested cross-flag analysis"))
        session.add(Escalation(flag_name=FLAG_B, reason="Agent 1 requested cross-flag analysis"))

        for index in range(DEVICE_COUNT):
            device_id = f"shared-device-{index}"
            in_a = random_source.random() < ROLLOUT_A
            in_b = random_source.random() < ROLLOUT_B
            failure_rate = OVERLAP_FAILURE_RATE if in_a and in_b else OTHER_FAILURE_RATE
            outcome = "failure" if random_source.random() < failure_rate else "success"

            session.add(
                RoutingEvents(
                    device_id=device_id,
                    flag_name=FLAG_A,
                    bucket=random_source.randint(1, 20) if in_a else random_source.randint(21, 100),
                    decision="new" if in_a else "legacy",
                    outcome=outcome,
                )
            )
            session.add(
                RoutingEvents(
                    device_id=device_id,
                    flag_name=FLAG_B,
                    bucket=random_source.randint(1, 20) if in_b else random_source.randint(21, 100),
                    decision="new" if in_b else "legacy",
                    outcome=outcome,
                )
            )
        session.commit()


if __name__ == "__main__":
    create_agent_2_table()
    clear_previous_test_data()
    seed_interaction()
    evaluate_all_escalations()
