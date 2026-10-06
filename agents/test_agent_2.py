import unittest
from contextlib import contextmanager
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import Agent1
import Agent2
from Agent2 import _calculate_pair_statistics, _parse_pair_verdict
from models import Base, Escalation, InteractionFinding, RoutingEvents


class PairStatisticsTests(unittest.TestCase):
    def test_detects_a_large_overlap_failure_increase(self):
        devices_a = {}
        devices_b = {}

        for index in range(40):
            outcome = "failure" if index < 20 else "success"
            devices_a[f"overlap-{index}"] = outcome
            devices_b[f"overlap-{index}"] = outcome

        for index in range(50):
            devices_a[f"only-a-{index}"] = "failure" if index == 0 else "success"
            devices_b[f"only-b-{index}"] = "failure" if index == 0 else "success"

        stats = _calculate_pair_statistics(devices_a, devices_b)

        self.assertIsNotNone(stats)
        self.assertEqual(stats.overlap_sample_size, 40)
        self.assertEqual(stats.comparison_sample_size, 100)
        self.assertEqual(stats.overlap_failure_rate, 0.5)
        self.assertEqual(stats.comparison_failure_rate, 0.02)
        self.assertLess(stats.p_value, 0.05)

    def test_returns_none_when_overlap_is_too_small(self):
        devices_a = {f"device-{i}": "success" for i in range(29)}
        devices_b = dict(devices_a)

        self.assertIsNone(_calculate_pair_statistics(devices_a, devices_b))

    def test_either_overlap_failure_counts_as_combined_failure(self):
        devices_a = {f"overlap-{i}": "success" for i in range(30)}
        devices_b = {f"overlap-{i}": "failure" for i in range(30)}
        devices_a.update({f"only-a-{i}": "success" for i in range(30)})

        stats = _calculate_pair_statistics(devices_a, devices_b)

        self.assertIsNotNone(stats)
        self.assertEqual(stats.overlap_failures, 30)


class VerdictParserTests(unittest.TestCase):
    def test_accepts_a_flag_name(self):
        verdict, reason = _parse_pair_verdict(
            "flag_a\nTemporarily reduce flag A and measure again.",
            "flag_a",
            "flag_b",
        )

        self.assertEqual(verdict, "flag_a")
        self.assertIn("reduce", reason)

    def test_accepts_both(self):
        verdict, _ = _parse_pair_verdict("BOTH\nTest the pair separately.", "a", "b")
        self.assertEqual(verdict, "BOTH")

    def test_malformed_response_defaults_to_unclear(self):
        verdict, reason = _parse_pair_verdict("Probably flag_a", "flag_a", "flag_b")

        self.assertEqual(verdict, "UNCLEAR")
        self.assertIn("Could not parse", reason)


class Agent2WorkflowTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.session_factory = sessionmaker(bind=engine)

    @contextmanager
    def get_session(self):
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()

    def test_records_finding_and_resolves_escalations(self):
        with self.get_session() as session:
            session.add(Escalation(flag_name="flag_a", reason="needs pair analysis"))
            session.add(Escalation(flag_name="flag_b", reason="needs pair analysis"))

            for index in range(40):
                outcome = "failure" if index < 20 else "success"
                device_id = f"overlap-{index}"
                session.add(
                    RoutingEvents(
                        device_id=device_id,
                        flag_name="flag_a",
                        bucket=10,
                        decision="new",
                        outcome=outcome,
                    )
                )
                session.add(
                    RoutingEvents(
                        device_id=device_id,
                        flag_name="flag_b",
                        bucket=10,
                        decision="new",
                        outcome=outcome,
                    )
                )

            for index in range(50):
                session.add(
                    RoutingEvents(
                        device_id=f"only-a-{index}",
                        flag_name="flag_a",
                        bucket=10,
                        decision="new",
                        outcome="failure" if index == 0 else "success",
                    )
                )
                session.add(
                    RoutingEvents(
                        device_id=f"only-b-{index}",
                        flag_name="flag_b",
                        bucket=10,
                        decision="new",
                        outcome="failure" if index == 0 else "success",
                    )
                )
            session.commit()

        with (
            patch.object(Agent2, "get_session", self.get_session),
            patch.object(
                Agent2,
                "ask_gemini",
                return_value="UNCLEAR\nReduce one flag at a time and measure the overlap again.",
            ),
        ):
            finding_recorded = Agent2.evaluate_flag_pair("flag_a", "flag_b")

        self.assertTrue(finding_recorded)
        with self.get_session() as session:
            finding = session.query(InteractionFinding).one()
            escalations = session.query(Escalation).all()

        self.assertEqual(finding.flag_a, "flag_a")
        self.assertEqual(finding.flag_b, "flag_b")
        self.assertEqual(finding.likely_cause, "UNCLEAR")
        self.assertEqual(finding.overlap_sample_size, 40)
        self.assertAlmostEqual(finding.overlap_failure_rate, 0.50)
        self.assertAlmostEqual(finding.baseline_failure_rate, 0.02)
        self.assertLess(finding.p_value, 0.05)
        self.assertTrue(all(escalation.resolved for escalation in escalations))


class Agent1ToAgent2WorkflowTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.session_factory = sessionmaker(bind=engine)

    @contextmanager
    def get_session(self):
        session = self.session_factory()
        try:
            yield session
        finally:
            session.close()

    def test_agent_1_escalations_are_consumed_by_agent_2(self):
        with self.get_session() as session:
            for index in range(40):
                outcome = "failure" if index < 20 else "success"
                device_id = f"overlap-{index}"
                for flag_name in ("flag_a", "flag_b"):
                    session.add(
                        RoutingEvents(
                            device_id=device_id,
                            flag_name=flag_name,
                            bucket=10,
                            decision="new",
                            outcome=outcome,
                        )
                    )

            for index in range(50):
                outcome = "failure" if index == 0 else "success"
                session.add(
                    RoutingEvents(
                        device_id=f"only-a-{index}",
                        flag_name="flag_a",
                        bucket=10,
                        decision="new",
                        outcome=outcome,
                    )
                )
                session.add(
                    RoutingEvents(
                        device_id=f"only-a-{index}",
                        flag_name="flag_b",
                        bucket=90,
                        decision="legacy",
                        outcome=outcome,
                    )
                )
                session.add(
                    RoutingEvents(
                        device_id=f"only-b-{index}",
                        flag_name="flag_a",
                        bucket=90,
                        decision="legacy",
                        outcome=outcome,
                    )
                )
                session.add(
                    RoutingEvents(
                        device_id=f"only-b-{index}",
                        flag_name="flag_b",
                        bucket=10,
                        decision="new",
                        outcome=outcome,
                    )
                )

            for index in range(60):
                for flag_name in ("flag_a", "flag_b"):
                    session.add(
                        RoutingEvents(
                            device_id=f"neither-{index}",
                            flag_name=flag_name,
                            bucket=90,
                            decision="legacy",
                            outcome="success",
                        )
                    )
            session.commit()

        with (
            patch.object(Agent1, "get_session", self.get_session),
            patch.object(
                Agent1,
                "ask_gemini",
                return_value="ESCALATE\nThe flag needs cross-flag analysis.",
            ),
        ):
            Agent1.evaluate_flag("flag_a")
            Agent1.evaluate_flag("flag_b")

        with self.get_session() as session:
            escalations = session.query(Escalation).all()
            self.assertEqual({row.flag_name for row in escalations}, {"flag_a", "flag_b"})
            self.assertTrue(all(not row.resolved for row in escalations))

        with (
            patch.object(Agent2, "get_session", self.get_session),
            patch.object(
                Agent2,
                "ask_gemini",
                return_value="UNCLEAR\nReduce one flag at a time and measure again.",
            ),
        ):
            Agent2.evaluate_all_escalations()

        with self.get_session() as session:
            finding = session.query(InteractionFinding).one()
            escalations = session.query(Escalation).all()

        self.assertEqual((finding.flag_a, finding.flag_b), ("flag_a", "flag_b"))
        self.assertEqual(finding.overlap_sample_size, 40)
        self.assertAlmostEqual(finding.overlap_failure_rate, 0.50)
        self.assertAlmostEqual(finding.baseline_failure_rate, 0.02)
        self.assertLess(finding.p_value, 0.05)
        self.assertEqual(finding.likely_cause, "UNCLEAR")
        self.assertTrue(all(escalation.resolved for escalation in escalations))


if __name__ == "__main__":
    unittest.main()
