import json
from pathlib import Path
from typing import Any, Dict, List

EVAL_CASES_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "eval_cases.json"


def load_cases(path: Path = EVAL_CASES_PATH) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def plan_text(plan: Dict[str, Any]) -> str:
    return json.dumps(plan, ensure_ascii=False).lower()


def score_plan(case: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    """Return which topic groups the plan covers and which forbidden terms appear."""
    text = plan_text(plan)
    covered = {
        topic: any(keyword in text for keyword in keywords)
        for topic, keywords in case.get("must_cover", {}).items()
    }
    forbidden = [term for term in case.get("must_not", []) if term in text]
    open_questions = len(plan.get("open_questions", []))
    min_questions = case.get("min_open_questions", 0)
    missing = [topic for topic, ok in covered.items() if not ok]
    total = len(covered)
    return {
        "name": case["name"],
        "coverage": (total - len(missing)) / total if total else 1.0,
        "missing": missing,
        "forbidden": forbidden,
        "open_questions": open_questions,
        "open_questions_ok": open_questions >= min_questions,
        "passed": not missing and not forbidden and open_questions >= min_questions,
    }
