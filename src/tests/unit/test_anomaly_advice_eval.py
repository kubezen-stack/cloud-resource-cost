import asyncio
import json

import pytest

from app.jobs.spike_advice_eval import format_report, main, run, select_cases
from app.services.anomaly_advice import SpikeAdvice, load_playbook
from app.services.anomaly_advice_eval import case_inputs, failed_run, load_cases, score_advice
from tests.fake_llm import FakeLLM


def advice(text, questions=("Was it planned?",)):
    return SpikeAdvice.model_validate({
        "summary": text, "hypotheses": [{"cause": text, "evidence": ["x"], "how_to_check": text}],
        "actions": [{"step": text, "source": None}], "expected_if": "This is expected if planned.",
        "questions": list(questions)})


def test_every_case_builds_a_consistent_anomaly_and_drivers():
    for case in load_cases():
        anomaly, drivers = case_inputs(case)
        assert drivers and abs(sum(d.share for d in drivers) - 1.0) < 1e-9
        assert anomaly.actual_cost >= sum(d.actual_cost for d in drivers) - 1e-9 or anomaly.expected_cost == 0.0
        assert all(d.usage_type for d in drivers)


def test_cases_have_unique_names_and_expectations():
    cases = load_cases()
    assert len({c["name"] for c in cases}) == len(cases)
    assert all(c["must_cover"] and c["min_questions"] >= 1 for c in cases)


def test_a_new_driver_of_a_case_is_marked_new_and_known_types_have_a_meaning():
    nat = case_inputs(next(c for c in load_cases() if c["name"] == "nat_bytes"))[1][0]
    assert nat.meaning == "data processed by a NAT Gateway" and not nat.is_new
    unknown = case_inputs(next(c for c in load_cases() if c["name"] == "unknown_usage_type"))[1][0]
    assert unknown.is_new and unknown.meaning is None


def test_scoring_finds_missing_topics_and_forbidden_phrases():
    case = next(c for c in load_cases() if c["name"] == "nat_bytes")
    good = advice("Add a gateway VPC endpoint for S3 and check the flow logs.")
    assert score_advice(case, good)["passed"]
    poor = score_advice(case, advice("Look at the bill. You should delete the database."))
    assert not poor["passed"] and "endpoint" in poor["missing"] and poor["forbidden"] == ["delete the database"]


def test_too_few_questions_fail_a_case():
    case = next(c for c in load_cases() if c["name"] == "nat_bytes")
    assert not score_advice(case, advice("endpoint s3 flow log", questions=()))["passed"]


def test_a_failed_run_does_not_pass():
    assert not failed_run({"name": "x"}, "boom")["passed"]


def answer(case):
    anomaly, drivers = case_inputs(case)
    text = " ".join(k[0] for k in case["must_cover"].values())
    return json.dumps({
        "summary": "s", "hypotheses": [{"cause": text, "evidence": [drivers[0].usage_type], "how_to_check": text}],
        "actions": [{"step": text, "source": None}], "expected_if": "This is expected if planned.",
        "questions": ["Was it planned?"]})


def test_the_run_scores_every_case_with_the_model_answers():
    cases = load_cases()[:2]
    llm = FakeLLM([answer(c) for c in cases])
    results = asyncio.run(run(llm, 1, cases))
    assert [r["name"] for r in results] == [c["name"] for c in cases] and all(r["passed"] for r in results)
    assert len(llm.calls) == 2


def test_an_unusable_model_counts_as_a_failed_case():
    cases = load_cases()[:1]
    results = asyncio.run(run(FakeLLM(["not json", "not json"]), 1, cases))
    assert not results[0]["passed"] and results[0]["missing"] == ["advice"]
    assert "FAIL" in format_report(results)


def test_the_job_needs_an_api_key(monkeypatch, capsys):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert asyncio.run(main(1)) == 1
    assert "LLM_API_KEY" in capsys.readouterr().out


def test_the_playbook_has_a_section_for_every_meaning_the_explanation_can_give():
    from app.services.anomaly_explain import CATEGORIES
    section_for = {
        "data processed by a NAT Gateway": "data processed by a nat gateway",
        "NAT Gateway hours": "nat gateway hours",
        "load balancer hours": "load balancer hours",
        "load balancer capacity units": "load balancer capacity units",
        "instance hours": "instance hours",
        "spot instance hours": "spot instance hours",
        "database instance hours": "database instance hours",
        "data transfer": "data transfer",
        "volume snapshots": "volume snapshots",
        "EBS volumes": "ebs volumes",
        "storage": "storage",
        "public IPv4 addresses": "public ipv4 addresses",
        "Elastic IP addresses": "public ipv4 addresses",
        "function compute time": "function compute time",
        "requests": "requests",
    }
    headings = {h.lower() for h in load_playbook()}
    meanings = {text for _, text in CATEGORIES}
    assert meanings == set(section_for)
    assert all(section_for[m] in headings for m in meanings)


def test_a_single_case_can_be_selected_by_name():
    assert [c["name"] for c in select_cases("nat_bytes")] == ["nat_bytes"]
    assert len(select_cases()) == len(load_cases())


def test_an_unknown_case_name_lists_the_known_ones():
    with pytest.raises(ValueError, match="nat_bytes"):
        select_cases("nope")
