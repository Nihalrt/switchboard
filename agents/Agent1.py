from scipy.stats import chi2_contingency
from db import get_session
from models import RoutingEvents, Escalation
from manager_client import rollback_flag
from llm import ask_gemini

MIN_SAMPLE_SIZE = 30

SIGNIFICANCE_THRESHOLD = 0.05

def _failure_count(events: list[RoutingEvents]):
    return sum(1 for e in events if e.outcome == "failure")

def _record_escalation(flag_name: str, reason: str):
    with get_session() as session:
        session.add(Escalation(flag_name=flag_name, reason=reason))
        session.commit()
    print(f"{flag_name} escalating:")

def _parse_decision(gemini_response: str) -> tuple[str, str]:
 
    if not gemini_response or not gemini_response.strip():
        return "ESCALATE", "Gemini returned an empty response"
 
    lines = [line.strip() for line in gemini_response.strip().splitlines() if line.strip()]
    if not lines:
        return "ESCALATE", "Gemini returned no usable content"
 
    first_line = lines[0].upper()
    for noise in ("*", "`", "#", '"', "'", ":", "-", "."):
        first_line = first_line.replace(noise, " ")
    words = first_line.split()
    words = [w for w in words if w not in ("VERDICT", "DECISION", "ANSWER", "LINE", "1")]
 
    reason = lines[1].strip() if len(lines) > 1 else "no explanation given"
    says_rollback = words == ["ROLLBACK"]
    says_escalate = words == ["ESCALATE"]
 
    if says_rollback and not says_escalate:
        return "ROLLBACK", reason
    if says_escalate and not says_rollback:
        return "ESCALATE", reason

    return "ESCALATE", f"could not clearly parse Gemini's response: {gemini_response!r}"

def evaluate_flag(flag_name: str) -> None:
    with get_session() as session:
        new_events = (
            session.query(RoutingEvents).filter(RoutingEvents.flag_name == flag_name,
            RoutingEvents.decision == "new").all()
        )
        legacy_events = (
            session.query(RoutingEvents).filter(RoutingEvents.flag_name == flag_name,
            RoutingEvents.decision == "legacy").all()
        )
    
    if len(new_events) < MIN_SAMPLE_SIZE or len(legacy_events) < MIN_SAMPLE_SIZE:
        print(f"{flag_name} not in enough data to analyze")
        return
    
    new_events_failures = _failure_count(new_events)
    new_events_success = len(new_events) - new_events_failures
    legacy_events_failures = _failure_count(legacy_events)
    legacy_events_success = len(legacy_events) - legacy_events_failures

    contingency_table = [
        [new_events_failures, new_events_success],
        [legacy_events_failures, legacy_events_success]
    ]
    _, p_value, _,_ = chi2_contingency(contingency_table)

    if p_value >= SIGNIFICANCE_THRESHOLD:
        print(f"{flag_name} healthy, no meaningful data")
        return

    new_failure_rate = new_events_failures / len(new_events)
    legacy_failure_rate = legacy_events_failures / len(legacy_events)

    prompt = f"""You are analyzing one feature flag rollout and deciding whether it should be rolled back.
    
    DEFINITIONS:
    The legacy pipeline is the existing, already-trusted code path. It is the control
    group and represents normal, expected behaviour.
    The new pipeline is the untested code being rolled out gradually.
    Devices are assigned to one pipeline or the other by a deterministic hash, so the
    two groups are comparable.
    
    DATA:
    Flag name: {flag_name}
    New pipeline: {new_events_failures} failures out of {len(new_events)} devices ({new_failure_rate:.1%} failure rate)
    Legacy pipeline: {legacy_events_failures} failures out of {len(legacy_events)} devices ({legacy_failure_rate:.1%} failure rate)
    Chi-square test p-value: {p_value:.4f}
    
    The difference between the two groups is already confirmed to be statistically
    significant. Do not re-evaluate whether it is significant. Decide only what should
    be done about it.
    
    YOUR TASK:
    Choose exactly one verdict.
    
    Choose ROLLBACK when the new pipeline's failure rate is clearly and substantially
    worse than the legacy pipeline's, and the size of that gap is fully explained by a
    fault in this flag's own new code path.
    
    Choose ESCALATE when any of the following is true:
    - The new pipeline is worse than legacy, but only marginally, so rolling back may
    be an overreaction.
    - The new pipeline's failure rate is BETTER than the legacy pipeline's. This is
    never a reason to roll back, but it is unusual enough to deserve a closer look.
    - The failure pattern looks strange in a way this flag's own numbers do not fully
    explain, and would be better understood by comparing against other flags running
    at the same time.
    
    If you are uncertain between the two verdicts, choose ESCALATE. Escalating is
    reversible and cheap. Rolling back the wrong flag disables working functionality
    for real devices.
    
    OUTPUT FORMAT:
    Line 1: exactly one word, either ROLLBACK or ESCALATE. Nothing else on this line.
    Line 2: one or two sentences of plain-text reasoning, referring to the actual
    numbers above.
    
    Do not use markdown, backticks, asterisks, bullet points, headings, labels such as
    "Verdict:", or quotation marks. Do not write anything before line 1 or after line 2.
    
    EXAMPLE OF A VALID RESPONSE:
    ROLLBACK
    The new pipeline fails at 31.2% against a 2.1% legacy baseline, a large regression
    fully consistent with a fault in the new code path itself.
    """
    try:
        gemini_response = ask_gemini(prompt)
    except Exception as e:
        _record_escalation(flag_name, f"{e}")
        return
    
    decision, reason = _parse_decision(gemini_response)

    if decision == "ROLLBACK":
        try:
            rollback_flag(flag_name)
            print(f"{flag_name} was successfully disabled.")
        except Exception as e:
            _record_escalation(flag_name, f"flag_name was not pushed because of {reason}")
        
    else:
        _record_escalation(flag_name, reason)
