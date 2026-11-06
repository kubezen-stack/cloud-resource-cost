"""Scoring of spike advice against the expectations in spike_advice_cases.json."""
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.services.advisor_eval import plan_text
from app.services.anomaly_advice import SpikeAdvice
from app.services.anomaly_explain import Driver, meaning_of
from app.services.anomaly_service import Anomaly

CASES_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "spike_advice_cases.json"


def load_cases(path: Path = CASES_PATH) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def case_inputs(case: Dict[str, Any]) -> Tuple[Anomaly, List[Driver]]:
    """The anomaly and its drivers of a case, built the way the notification job builds them."""
    a = case["anomaly"]
    increase = a["actual_cost"] - a["expected_cost"]
    pct = increase / a["expected_cost"] * 100 if a["expected_cost"] else None
    anomaly = Anomaly(a["service"], date.fromisoformat(a["day"]), a["actual_cost"], a["expected_cost"], pct, 1.0)
    total = sum(d["actual_cost"] - d["expected_cost"] for d in case["drivers"])
    drivers = [
        Driver(d["usage_type"], d["region"], meaning_of(d["usage_type"]), d["actual_cost"], d["expected_cost"],
               (d["actual_cost"] - d["expected_cost"]) / total, d["is_new"])
        for d in case["drivers"]
    ]
    return anomaly, drivers


def score_advice(case: Dict[str, Any], advice: SpikeAdvice) -> Dict[str, Any]:
    """Which topics the advice covers and which forbidden phrases it contains."""
    text = plan_text(advice.model_dump())
    covered = {topic: any(k in text for k in keywords) for topic, keywords in case.get("must_cover", {}).items()}
    forbidden = [term for term in case.get("must_not", []) if term in text]
    missing = [topic for topic, ok in covered.items() if not ok]
    questions_ok = len(advice.questions) >= case.get("min_questions", 0)
    return {
        "name": case["name"],
        "coverage": (len(covered) - len(missing)) / len(covered) if covered else 1.0,
        "missing": missing,
        "forbidden": forbidden,
        "warnings": [],
        "open_questions": len(advice.questions),
        "open_questions_ok": questions_ok,
        "passed": not missing and not forbidden and questions_ok,
        "adjusted": False,
        "services": [],
    }


def failed_run(case: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """A run that produced no valid advice (provider error, or the checks rejected the answers twice)."""
    return {"name": case["name"], "coverage": 0.0, "missing": ["advice"], "forbidden": [], "warnings": [reason],
            "open_questions": 0, "open_questions_ok": False, "passed": False, "adjusted": False, "services": []}
