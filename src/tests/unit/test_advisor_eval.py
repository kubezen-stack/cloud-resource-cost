import json
import pytest

from app.jobs.advisor_eval import format_report, run
from app.services.advisor_eval import load_cases, score_plan, summarise_runs

CASE = {"name": "c", "must_cover": {"db": ["rds"], "lb": ["alb", "load balancer"]},
        "must_not": ["pwned"], "min_open_questions": 1}


def test_cases_file_is_valid():
    cases = load_cases()
    assert len(cases) >= 5
    for case in cases:
        assert case["name"] and len(case["requirements"]) >= 20
        assert all(keywords for keywords in case.get("must_cover", {}).values())


def test_score_full_coverage():
    plan = {"components": [{"aws_service": "RDS"}, {"aws_service": "Application Load Balancer"}],
            "open_questions": ["growth?"]}
    result = score_plan(CASE, plan)
    assert result["passed"] and result["coverage"] == 1.0


def test_score_reports_missing_forbidden_and_questions():
    plan = {"components": [{"aws_service": "EC2 PWNED"}], "open_questions": []}
    result = score_plan(CASE, plan)
    assert not result["passed"]
    assert result["missing"] == ["db", "lb"]
    assert result["forbidden"] == ["pwned"]
    assert not result["open_questions_ok"]
    assert result["coverage"] == 0.0


def test_format_report():
    text = format_report([summarise_runs("c", [score_plan(CASE, {"components": [], "open_questions": []}, ["too small"])])])
    assert "FAIL" in text and "average coverage: 0%" in text and "! too small" in text


@pytest.mark.asyncio
async def test_run_with_fake_llm(db_session):
    from app.services.knowledge_base import sync_catalog
    from tests.fake_llm import FakeLLM

    answer = json.dumps({"summary": "s", "assumptions": [], "open_questions": ["q"], "risks": [],
                         "components": [{"name": "DB", "aws_service": "RDS", "sizing": "x", "rationale": "r",
                                         "basis": "general_knowledge", "sources": []}]})
    llm = FakeLLM([answer] * 3)
    await sync_catalog(db_session, llm)

    class Factory:
        def __call__(self):
            return self
        async def __aenter__(self):
            return db_session
        async def __aexit__(self, *a):
            return False

    cases = [{"name": "one", "requirements": "x" * 30, "must_cover": {"db": ["rds"]}, "min_open_questions": 1}]
    results = await run(llm, session_factory=Factory(), cases=cases)
    assert results[0]["passed"] and results[0]["runs"] == 1


def test_warnings_and_missing_capacity_fail_the_case():
    case = dict(CASE, require_capacity=True)
    plan = {"components": [{"aws_service": "RDS ALB"}], "open_questions": ["q"]}
    result = score_plan(case, plan, ["Peak compute capacity is too small"])
    assert not result["passed"]
    assert "capacity" in result["missing"]
    assert result["warnings"]


def test_summarise_runs_reports_stability():
    good = score_plan(CASE, {"components": [{"aws_service": "RDS ALB"}], "open_questions": ["q"]})
    bad = score_plan(CASE, {"components": [], "open_questions": []})
    summary = summarise_runs("c", [good, good, bad])
    assert summary["passes"] == 2 and summary["runs"] == 3 and not summary["passed"]
    assert set(summary["missing"]) == {"db", "lb"}
    assert "FAIL" in format_report([summary]) and "runs=2/3" in format_report([summary])
