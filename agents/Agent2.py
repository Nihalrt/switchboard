"""Agent 2: detect failures caused by combinations of feature flags.

Agent 1 looks at one flag at a time. That means it can miss a problem that only
appears when the same device receives two new features together. Agent 2 starts
with Agent 1's unresolved escalations, checks every pair, and compares:

* overlap devices: in both flags' new pipelines;
* comparison devices: in exactly one of the two new pipelines.

Agent 2 records a finding when the overlap has a statistically significant,
higher failure rate. It deliberately does not roll back either flag because the
pair-level evidence cannot prove which individual flag should be disabled.
"""

from dataclasses import dataclass
from itertools import combinations

from scipy.stats import chi2_contingency

from db import get_session
from llm import ask_gemini
from models import Escalation, InteractionFinding, RoutingEvents

MIN_OVERLAP_SIZE = 30
MIN_COMPARISON_SIZE = 30
SIGNIFICANCE_THRESHOLD = 0.05
VALID_OUTCOMES = {"success", "failure"}


@dataclass(frozen=True)
class PairStatistics:
    """The evidence calculated for one pair of escalated flags."""

    overlap_sample_size: int
    comparison_sample_size: int
    overlap_failures: int
    comparison_failures: int
    overlap_failure_rate: float
    comparison_failure_rate: float
    p_value: float


def _unresolved_escalated_flags() -> list[str]:
    """Return each unresolved flag name once, in a stable order."""

    with get_session() as session:
        rows = (
            session.query(Escalation)
            .filter(Escalation.resolved.is_(False))
            .all()
        )
    return sorted({row.flag_name for row in rows})


def _new_pipeline_outcomes(flag_name: str) -> dict[str, str]:
    """Return the latest known new-pipeline outcome for each device.

    A device may have several historical rows for a flag. Ordering by id and
    assigning into a dictionary means a later row replaces an earlier one. Rows
    whose outcome is still unknown are ignored because they cannot contribute to
    a success/failure comparison yet.
    """

    with get_session() as session:
        rows = (
            session.query(RoutingEvents)
            .filter(
                RoutingEvents.flag_name == flag_name,
                RoutingEvents.decision == "new",
            )
            .order_by(RoutingEvents.id.asc())
            .all()
        )

    outcomes: dict[str, str] = {}
    for row in rows:
        if row.outcome in VALID_OUTCOMES:
            outcomes[row.device_id] = row.outcome
    return outcomes


def _combined_outcome(outcome_a: str, outcome_b: str) -> str:
    """Combine the two rows that describe one overlap device."""

    if "failure" in (outcome_a, outcome_b):
        return "failure"
    return "success"


def _calculate_pair_statistics(
    devices_a: dict[str, str], devices_b: dict[str, str]
) -> PairStatistics | None:
    """Calculate overlap-vs-comparison statistics without touching the DB."""

    ids_a = set(devices_a)
    ids_b = set(devices_b)
    overlap_ids = ids_a & ids_b
    comparison_ids = ids_a ^ ids_b

    if len(overlap_ids) < MIN_OVERLAP_SIZE:
        return None
    if len(comparison_ids) < MIN_COMPARISON_SIZE:
        return None

    overlap_failures = sum(
        _combined_outcome(devices_a[device_id], devices_b[device_id]) == "failure"
        for device_id in overlap_ids
    )
    comparison_failures = sum(
        (devices_a.get(device_id) or devices_b[device_id]) == "failure"
        for device_id in comparison_ids
    )

    overlap_successes = len(overlap_ids) - overlap_failures
    comparison_successes = len(comparison_ids) - comparison_failures
    table = [
        [overlap_failures, overlap_successes],
        [comparison_failures, comparison_successes],
    ]

    try:
        _, p_value, _, _ = chi2_contingency(table)
    except ValueError:
        # SciPy raises when an expected cell is zero. In that shape there is not
        # enough variation to make a trustworthy interaction claim.
        return None

    return PairStatistics(
        overlap_sample_size=len(overlap_ids),
        comparison_sample_size=len(comparison_ids),
        overlap_failures=overlap_failures,
        comparison_failures=comparison_failures,
        overlap_failure_rate=overlap_failures / len(overlap_ids),
        comparison_failure_rate=comparison_failures / len(comparison_ids),
        p_value=float(p_value),
    )


def _mark_resolved(flag_names: list[str]) -> None:
    """Mark Agent 1's outstanding escalations as handled by Agent 2."""

    with get_session() as session:
        (
            session.query(Escalation)
            .filter(
                Escalation.flag_name.in_(flag_names),
                Escalation.resolved.is_(False),
            )
            .update({Escalation.resolved: True}, synchronize_session=False)
        )
        session.commit()


def _record_finding(
    flag_a: str,
    flag_b: str,
    stats: PairStatistics,
    likely_cause: str,
    reason: str,
) -> None:
    """Persist the evidence and Gemini's recommendation."""

    with get_session() as session:
        session.add(
            InteractionFinding(
                flag_a=flag_a,
                flag_b=flag_b,
                overlap_sample_size=stats.overlap_sample_size,
                overlap_failure_rate=stats.overlap_failure_rate,
                baseline_failure_rate=stats.comparison_failure_rate,
                p_value=stats.p_value,
                likely_cause=likely_cause,
                reason=reason,
            )
        )
        session.commit()


def _parse_pair_verdict(gemini_response: str, flag_a: str, flag_b: str) -> tuple[str, str]:
    """Parse a constrained LLM response, defaulting safely to UNCLEAR."""

    if not gemini_response or not gemini_response.strip():
        return "UNCLEAR", "Gemini returned an empty response"

    lines = [line.strip() for line in gemini_response.splitlines() if line.strip()]
    if not lines:
        return "UNCLEAR", "Gemini returned no usable content"

    first_line = lines[0]
    for noise in ("*", "`", "#", '"', "'", ":"):
        first_line = first_line.replace(noise, " ")
    words = first_line.split()
    words = [word for word in words if word.upper() not in {"VERDICT", "DECISION"}]
    verdict = " ".join(words)
    reason = " ".join(lines[1:]) if len(lines) > 1 else "No explanation given"

    if verdict == flag_a:
        return flag_a, reason
    if verdict == flag_b:
        return flag_b, reason
    if verdict.upper() == "BOTH":
        return "BOTH", reason
    if verdict.upper() == "UNCLEAR":
        return "UNCLEAR", reason
    return "UNCLEAR", f"Could not parse Gemini's verdict: {gemini_response!r}"

def evaluate_flag_pair(flag_a: str, flag_b: str) -> bool:
    devices_a = _new_pipeline_outcomes(flag_a)
    devices_b = _new_pipeline_outcomes(flag_b)

    stats = _calculate_pair_statistics(devices_a, devices_b)

    if stats is None:
        print(
            f"[{flag_a} + {flag_b}] not enough usable overlap "
            "or comparison data"
        )
        return False

    if stats.p_value >= SIGNIFICANCE_THRESHOLD:
        print(
            f"[{flag_a} + {flag_b}] no statistically significant "
            "interaction found"
        )
        return False

    if stats.overlap_failure_rate <= stats.comparison_failure_rate:
        print(
            f"[{flag_a} + {flag_b}] overlap is not worse than "
            "the comparison group"
        )
        return False

    prompt = f"""You are analyzing a possible interaction effect between two feature flags that are both currently running, and were each individually escalated because neither one's own data fully explained a problem on its own.

DEFINITIONS:
"Overlap devices" are devices simultaneously in flag {flag_a}'s new pipeline AND flag {flag_b}'s new pipeline at the same time.
"Other devices" are devices in exactly one of the two flags' new pipelines, never both.

DATA:
Overlap devices: {stats.overlap_sample_size}
Overlap failure rate: {stats.overlap_failure_rate:.1%}
Other devices: {stats.comparison_sample_size}
Other-device failure rate: {stats.comparison_failure_rate:.1%}
Chi-square p-value: {stats.p_value:.6f}

This difference is already confirmed statistically significant. Your task is to
judge which flag is more likely the actual cause and recommend a next step.

Choose exactly one verdict.

Respond with "{flag_a}" if flag {flag_a} looks more likely to be the cause.
Respond with "{flag_b}" if flag {flag_b} looks more likely to be the cause.
Respond with BOTH if the evidence genuinely implicates both equally.
Respond with UNCLEAR if there is not enough information to distinguish them.

The pair-level data cannot by itself prove which individual flag is responsible.
Choosing UNCLEAR is appropriate unless the evidence identifies one flag.

OUTPUT FORMAT:
Line 1: exactly one of: {flag_a}, {flag_b}, BOTH, UNCLEAR.
Line 2: one or two sentences of reasoning and a recommended next step.

Do not use markdown, backticks, bullet points, headings, or quotation marks.
Do not write anything before line 1 or after line 2.
"""

    try:
        gemini_response = ask_gemini(prompt)
    except Exception as error:
        print(f"[{flag_a} + {flag_b}] Gemini call failed: {error}")
        return False

    likely_cause, reason = _parse_pair_verdict(
        gemini_response,
        flag_a,
        flag_b,
    )

    _record_finding(
        flag_a,
        flag_b,
        stats,
        likely_cause,
        reason,
    )

    _mark_resolved([flag_a, flag_b])

    print(
        f"[{flag_a} + {flag_b}] interaction recorded; "
        f"likely cause: {likely_cause}"
    )

    return True


def evaluate_all_escalations():
    flags = _unresolved_escalated_flags()
    if len(flags) < 2:
        return "less flags"

    for flag_a, flag_b in combinations(flags, 2):
        print(f"evaluating flags: {flag_a} and {flag_b}")
        evaluate_flag_pair(flag_a, flag_b)
