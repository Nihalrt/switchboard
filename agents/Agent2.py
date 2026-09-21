from itertools import combinations
from scipy.stats import ch2_continigency
from db import get_session
from models import RoutingEvents, Escalation, InteractionFinding
from llm import ask_gemini

MIN_OVERLAP_SIZE = 30
SIGNIFICANT_THRESHOLD = 0.05

def _unresolved_escalated_flags():
    with get_session() as session:
        rows = session.query(Escalation).filter(Escalation.resolved==False).all()
    
    return sorted({row.flag_name for row in rows})


def _new_pipeline_outcomes(flag_name: str) -> dict[str, str]:
    with get_session() as session:
        rows = session.query(RoutingEvents).filter(RoutingEvents.flag_name == flag_name, RoutingEvents.decision == "new").all()
    
    return {row.device_id: row.decision for row in rows}

def _mark_resolved(flag_names: list[str]):
    with get_session() as session:
        (
            session.query(Escalation).filter(Escalation.flag_name.in_(flag_names), Escalation.resolved==False).update({Escalation.resolved: True}, synchronize_session=False)
            
        )
        session.commit()

def _record_finding(flag_a: str, flag_b: str, overlap_n: int, overlap_rate: float, baseline_rate: float, p_value: float, likely_cause: str, reason: str):
    with get_session as session:
        (
            session.add(InteractionFinding(
                flag_a=flag_a,
                flag_b=flag_b,
                overlap_sample_size=overlap_n,
                overlap_failure_rate=overlap_rate,
                baseline_failure_rate=baseline_rate,
                p_value=p_value,
                likely_cause=likely_cause,
                reason=reason
            ))
        )
    session.commit()

def check_response(gemini_response: str, flag_a: str, flag_b: str):
    if not gemini_response:
        return "UNCLEAR" or "No Response"
    
    # Gemini was not able to generate a response
    lines = [line.strip() for line in gemini_response.strip().splitlines()]
    if not lines:
        return "UNCLEAR" or "No Response"
    
    first_line = lines[0]
    for noise in ("*", "`", "#", '"', "'", ":"):
        first_line = first_line.replace(noise, "")
    first_line= first_line.strip()

    reason = lines[1].strip() if len(lines[0]) > 1 else "NO EXPLANATION"

    if flag_a in first_line:
        return flag_a, reason
    elif flag_b in first_line:
        return flag_b, reason
    elif "BOTH" in first_line:
        return "BOTH", reason
    else:
        return "NO EXPLANATION" or "NOT FOUND"

    

