# This is a manual test script, not a formal automated test. It
# seeds routing_events with three synthetic scenarios, each one
# designed to trigger a different one of Agent 1's three possible
# outcomes, then runs evaluate_flag against each and prints what it
# decided. This exists so Agent 1 can be tested now, before the full
# Phase B scenario generator is built.
#
# Before running this:
# - Postgres and Redis must both be running (docker ps to check)
# - The Manager must be running (uvicorn app.main:app --reload
#   --port 8001), since the "broken" scenario below is expected to
#   trigger a real rollback request to it
# - GEMINI_API_KEY must be set, since any scenario that is
#   statistically significant will trigger a real call to Gemini

import random

import requests

from db import get_session
from models import RoutingEvents
from Agent1 import evaluate_flag
from llm import ask_gemini

MANAGER_URL = "http://localhost:8001"


def ensure_flag_exists(flag_name: str) -> None:
    # Agent 1's rollback path calls PUT /flags/{name}, which only
    # succeeds if the flag already exists. This creates it first,
    # ignoring a 409 if it was already created by an earlier run of
    # this same script.
    response = requests.post(
        f"{MANAGER_URL}/flags/",
        json={"name": flag_name, "rollout_percentage": 50},
        timeout=10,
    )
    if response.status_code not in (201, 409):
        response.raise_for_status()


def seed_events(
    flag_name: str,
    n_new: int,
    new_failure_rate: float,
    n_legacy: int,
    legacy_failure_rate: float,
) -> None:
    with get_session() as session:
        for i in range(n_new):
            outcome = "failure" if random.random() < new_failure_rate else "success"
            session.add(
                RoutingEvents(
                    device_id=f"test-{flag_name}-new-{i}",
                    flag_name=flag_name,
                    bucket=random.randint(1, 25),
                    decision="new",
                    outcome=outcome,
                )
            )
        for i in range(n_legacy):
            outcome = "failure" if random.random() < legacy_failure_rate else "success"
            session.add(
                RoutingEvents(
                    device_id=f"test-{flag_name}-legacy-{i}",
                    flag_name=flag_name,
                    bucket=random.randint(26, 100),
                    decision="legacy",
                    outcome=outcome,
                )
            )
        session.commit()


# Each tuple below is: flag name, new-pipeline sample size and
# failure rate, legacy sample size and failure rate. The rates were
# chosen and verified by simulation to reliably produce the intended
# outcome, rather than guessed.
SCENARIOS = [
    ("test_healthy_flag", 200, 0.04, 200, 0.03),  # expected: healthy, no action
    ("test_marginal_flag", 600, 0.07, 600, 0.03),  # expected: significant but small, escalate
    ("test_broken_flag", 200, 0.40, 200, 0.03),  # expected: clearly unhealthy, rollback
]

if __name__ == "__main__":
    for flag_name, n_new, new_rate, n_legacy, legacy_rate in SCENARIOS:
        print(f"--- seeding {flag_name} ---")
        ensure_flag_exists(flag_name)
        seed_events(flag_name, n_new, new_rate, n_legacy, legacy_rate)

    for flag_name, *_ in SCENARIOS:
        print(f"\n--- evaluating {flag_name} ---")
        evaluate_flag(flag_name)