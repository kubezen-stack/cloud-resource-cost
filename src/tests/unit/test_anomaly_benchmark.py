from datetime import timedelta

from app.services.anomaly_benchmark import (
    CLEAN_ONLY,
    INJECTIONS,
    SCENARIOS,
    START,
    Counts,
    build_cases,
    evaluate,
    format_report,
    mad_detector,
    zscore_detector,
)


def test_cases_cover_every_scenario_and_injection():
    cases = build_cases(2)
    injectable = len(SCENARIOS) - len(CLEAN_ONLY)
    assert len(cases) == len(SCENARIOS) * 2 + injectable * len(INJECTIONS) * 2
    assert all(len(c.series) == 90 for c in cases)


def test_cases_are_deterministic():
    first, second = build_cases(2), build_cases(2)
    assert [c.series for c in first] == [c.series for c in second]
    assert build_cases(2, seed=1)[0].series != first[0].series


def test_injected_days_are_the_ones_that_changed():
    for case in build_cases(1):
        if case.injection is None:
            assert case.anomaly_days == frozenset()
        else:
            assert len(case.anomaly_days) == case.injection.width
            assert min(case.anomaly_days) >= START + timedelta(days=21)


def test_counts_metrics():
    counts = Counts(tp=3, fp=1, fn=1)
    assert counts.precision == 0.75 and counts.recall == 0.75 and counts.f1 == 0.75
    assert Counts().precision == 1.0 and Counts().recall == 1.0
    assert Counts(fp=2).f1 == 0.0


def test_simple_detectors_find_an_obvious_spike():
    series = {START + timedelta(days=i): 50.0 + (i % 3) for i in range(40)}
    spike_day = START + timedelta(days=30)
    series[spike_day] = 500.0
    assert zscore_detector(series) == {spike_day}
    assert mad_detector(series) == {spike_day}


def test_evaluate_counts_hits_and_false_alarms():
    cases = build_cases(1)
    everything = lambda series: set(series)
    nothing = lambda series: set()
    result = evaluate(cases, {"all": everything, "none": nothing})
    assert result["all"]["overall"].recall == 1.0 and result["all"]["overall"].precision < 0.1
    assert result["none"]["overall"].recall == 0.0
    assert result["none"]["false_alarms_per_series"]["flat"] == 0.0


def test_report_lists_every_detector():
    result = evaluate(build_cases(1), {"zscore": zscore_detector})
    report = format_report(result, 1)
    assert "| zscore |" in report and "spike x2" in report and "weekly" in report
