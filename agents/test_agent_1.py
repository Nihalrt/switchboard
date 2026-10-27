import unittest
from contextlib import contextmanager
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import Agent1
from models import Base, RoutingEvents, Escalation


class Agent1SafetyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    @contextmanager
    def get_session(self):
        with self.sessions() as session:
            yield session

    def seed(self, new, legacy):
        with self.sessions() as session:
            for decision, outcomes in (("new", new), ("legacy", legacy)):
                for i, outcome in enumerate(outcomes):
                    session.add(RoutingEvents(device_id=f"{decision}-{i}", flag_name="f", bucket=1, decision=decision, outcome=outcome))
            session.commit()

    def test_uniform_outcomes_need_no_llm_or_rollback(self):
        for outcome in ("success", "failure"):
            with self.subTest(outcome=outcome):
                with self.sessions() as session:
                    session.query(RoutingEvents).delete()
                    session.commit()
                self.seed([outcome] * 40, [outcome] * 40)
                with patch.object(Agent1, "get_session", self.get_session), patch.object(Agent1, "ask_gemini") as llm, patch.object(Agent1, "rollback_flag") as rollback:
                    Agent1.evaluate_flag("f")
                    llm.assert_not_called()
                    rollback.assert_not_called()

    def test_pending_outcomes_do_not_satisfy_minimum_sample_size(self):
        self.seed(["failure"] * 10 + [None] * 90, ["success"] * 100)
        with patch.object(Agent1, "get_session", self.get_session), patch.object(Agent1, "ask_gemini") as llm:
            Agent1.evaluate_flag("f")
            llm.assert_not_called()

    def test_llm_cannot_roll_back_better_pipeline(self):
        self.seed(["success"] * 100, ["failure"] * 80 + ["success"] * 20)
        with patch.object(Agent1, "get_session", self.get_session), patch.object(Agent1, "ask_gemini", return_value="ROLLBACK\nWrong recommendation"), patch.object(Agent1, "rollback_flag") as rollback:
            Agent1.evaluate_flag("f")
            rollback.assert_not_called()
        with self.sessions() as session:
            self.assertEqual(session.query(Escalation).count(), 1)


if __name__ == "__main__":
    unittest.main()
