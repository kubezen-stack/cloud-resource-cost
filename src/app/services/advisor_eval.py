"""Scoring of advisor answers against the expectations in eval_cases.json."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

EVAL_CASES_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "eval_cases.json"


def load_cases(path: Path = EVAL_CASES_PATH) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def plan_text(plan: Dict[str, Any]) -> str:
    return json.dumps(plan, ensure_ascii=False).lower()


def score_plan(case: Dict[str, Any], plan: Dict[str, Any], warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    """Return which topics the plan covers, forbidden terms and the result of the automatic checks."""
    text = plan_text(plan)
    covered = {
        topic: any(keyword in text for keyword in keywords)
        for topic, keywords in case.get("must_cover", {}).items()
    }
    forbidden = [term for term in case.get("must_not", []) if term in text]
    open_questions = len(plan.get("open_questions", []))
    min_questions = case.get("min_open_questions", 0)
    missing = [topic for topic, ok in covered.items() if not ok]
    if case.get("require_capacity") and not plan.get("capacity"):
        missing.append("capacity")
    total = len(covered) + (1 if case.get("require_capacity") else 0)
    warnings = list(warnings or [])
    return {
        "name": case["name"],
        "coverage": (total - len(missing)) / total if total else 1.0,
        "missing": missing,
        "forbidden": forbidden,
        "warnings": warnings,
        "open_questions": open_questions,
        "open_questions_ok": open_questions >= min_questions,
        "passed": not missing and not forbidden and not warnings and open_questions >= min_questions,
    }


def summarise_runs(name: str, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine several runs of one case: pass rate shows how stable the answers are."""
    passed = sum(r["passed"] for r in runs)
    return {
        "name": name,
        "runs": len(runs),
        "passes": passed,
        "passed": passed == len(runs),
        "coverage": sum(r["coverage"] for r in runs) / len(runs) if runs else 0.0,
        "missing": sorted({m for r in runs for m in r["missing"]}),
        "forbidden": sorted({f for r in runs for f in r["forbidden"]}),
        "warnings": sorted({w for r in runs for w in r["warnings"]}),
        "open_questions_ok": all(r["open_questions_ok"] for r in runs),
    }
