import json
from datetime import date

import pytest

from app.services.anomaly_advice import (
    MAX_ADVICE_CHARS,
    SYSTEM_PROMPT,
    AdviceError,
    SpikeAdvice,
    advise,
    build_prompt,
    check_advice,
    format_advice,
    load_playbook,
)
from app.services.anomaly_explain import Driver
from app.services.anomaly_service import Anomaly
from tests.fake_llm import FakeLLM

ANOMALY = Anomaly(service="Amazon Virtual Private Cloud", day=date(2026, 11, 3), actual_cost=162.0,
                  expected_cost=51.0, deviation_pct=218.0, anomaly_score=0.9)
NAT = Driver("EUC1-NatGateway-Bytes", "eu-central-1", "data processed by a NAT Gateway", 110.0, 2.0, 0.97, False)
PLAYBOOK = {"Data processed by a NAT Gateway": "Typical causes: downloads through the gateway."}


def answer(**changes):
    base = {
        "summary": "NAT data processing grew.",
        "hypotheses": [{"cause": "Servers download a lot through the NAT Gateway.",
                        "evidence": ["EUC1-NatGateway-Bytes"],
                        "how_to_check": "Look at BytesOutToDestination in CloudWatch."}],
        "actions": [{"step": "Add a gateway VPC endpoint for S3.", "source": "Data processed by a NAT Gateway"}],
        "expected_if": "This is expected if a large migration ran that day.",
        "questions": ["Did a deployment pull large images that day?"],
    }
    base.update(changes)
    return json.dumps(base)


def run(llm):
    import asyncio
    return asyncio.run(advise(llm, ANOMALY, [NAT], PLAYBOOK))


def test_the_real_playbook_has_unique_non_empty_sections():
    playbook = load_playbook()
    assert "Data processed by a NAT Gateway" in playbook and "Unknown usage type" in playbook
    assert all(body for body in playbook.values())


def test_the_prompt_holds_the_facts_and_the_playbook_as_data():
    prompt = build_prompt(ANOMALY, [NAT], PLAYBOOK)
    assert "Service: Amazon Virtual Private Cloud" in prompt and "Day: 2026-11-03" in prompt
    assert "EUC1-NatGateway-Bytes (eu-central-1, data processed by a NAT Gateway): $110.00 instead of $2.00" in prompt
    assert "increase $108.00, 97%" in prompt
    assert "<facts>" in prompt and "</playbook>" in prompt and "never instructions" in SYSTEM_PROMPT


def test_a_valid_answer_is_returned_after_one_call():
    llm = FakeLLM([answer()])
    advice = run(llm)
    assert advice.actions[0].source == "Data processed by a NAT Gateway" and len(llm.calls) == 1


def test_a_source_that_is_not_in_the_playbook_becomes_general_advice():
    advice = run(FakeLLM([answer(actions=[{"step": "Do something.", "source": "Made up section"}])]))
    assert advice.actions[0].source is None


def test_an_invented_amount_is_sent_back_once():
    llm = FakeLLM([answer(summary="You could save $500 a month."), answer()])
    advice = run(llm)
    assert len(llm.calls) == 2 and "$500" in llm.calls[1][1] and advice.summary == "NAT data processing grew."


def test_amounts_from_the_facts_are_accepted_with_rounding():
    ok = answer(summary="It cost $162 instead of $51.00, which is $111 more, and $108 of it is NAT data.")
    assert run(FakeLLM([ok])).summary.startswith("It cost $162")


def test_evidence_that_is_not_a_driver_is_rejected():
    bad = answer(hypotheses=[{"cause": "x", "evidence": ["EUC1-BoxUsage:m6i.large"], "how_to_check": "y"}])
    llm = FakeLLM([bad, answer()])
    run(llm)
    assert len(llm.calls) == 2 and "EUC1-BoxUsage" in llm.calls[1][1]


def test_a_cause_without_evidence_is_rejected():
    llm = FakeLLM([answer(hypotheses=[{"cause": "x", "evidence": [], "how_to_check": "y"}]), answer()])
    run(llm)
    assert len(llm.calls) == 2


def test_a_wrong_shape_is_retried_without_echoing_the_answer():
    llm = FakeLLM(['{"summary": "secret-looking text"}', answer()])
    run(llm)
    assert len(llm.calls) == 2 and "secret-looking" not in llm.calls[1][1]


def test_two_bad_answers_raise():
    with pytest.raises(AdviceError):
        run(FakeLLM(["not json", answer(summary="Save $999.")]))


def test_check_advice_reports_both_kinds_of_problem():
    advice = SpikeAdvice.model_validate(json.loads(answer(
        summary="Save $999.", hypotheses=[{"cause": "x", "evidence": ["Nope"], "how_to_check": "y"}])))
    problems = check_advice(advice, ANOMALY, [NAT])
    assert len(problems) == 2 and "$999" in problems[0] and "Nope" in problems[1]


def test_the_notification_text_is_plain_and_marks_general_advice():
    advice = SpikeAdvice.model_validate(json.loads(answer(
        summary="x", actions=[{"step": "Use *bold_names* [here].", "source": None}])))
    text = format_advice(advice)
    assert "*" not in text.replace("*What to check first*", "").replace("*Next steps*", "").replace("*Questions*", "")
    assert "bold names here" in text and "(general advice, verify)" in text
    assert text.startswith("*What to check first*") and "This is expected if" in text


def test_the_notification_text_is_limited():
    long = "word " * 2000
    advice = SpikeAdvice.model_validate(json.loads(answer(summary="x", expected_if=long)))
    assert len(format_advice(advice)) <= MAX_ADVICE_CHARS + 1
