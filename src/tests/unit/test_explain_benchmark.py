from app.services.explain_benchmark import (
    DAY,
    METHODS,
    NEW_TYPE,
    SCENARIOS,
    build_trials,
    evaluate,
    format_report,
    largest_cost,
)


def test_trials_are_deterministic_and_differ_between_seeds():
    first = build_trials("one type gets +$50", 3)
    assert [t.series for t in first] == [t.series for t in build_trials("one type gets +$50", 3)]
    assert [t.series for t in first] != [t.series for t in build_trials("one type gets +$50", 3, seed=1)]


def test_every_trial_has_a_cause_present_in_its_series():
    for scenario in SCENARIOS:
        for trial in build_trials(scenario, 5):
            assert DAY in trial.series[(trial.cause, "eu-central-1")]


def test_a_new_type_scenario_adds_a_type_with_no_history():
    trial = build_trials("a new usage type (+$50)", 1)[0]
    assert trial.cause == NEW_TYPE and list(trial.series[(NEW_TYPE, "eu-central-1")]) == [DAY]


def test_the_biggest_line_is_a_poor_attribution_and_the_production_method_is_not():
    result = evaluate(60)
    production = result["biggest increase over the median (production)"]
    assert result["biggest line of the bill"]["one type gets +$50"] < 0.4
    assert production["one type gets +$50"] > 0.9 and production["two types, +$80 and +$30"] > 0.9


def test_scores_are_shares_for_every_method_and_scenario():
    result = evaluate(10)
    assert set(result) == set(METHODS)
    assert all(0.0 <= v <= 1.0 for scores in result.values() for v in scores.values())


def test_report_has_a_row_per_method():
    report = format_report(evaluate(5), 5)
    assert all(name in report for name in METHODS) and "Average" in report


def test_largest_cost_takes_the_biggest_line():
    series = {("big", "r"): {DAY: 10.0}, ("small", "r"): {DAY: 1.0}}
    assert largest_cost(series) == "big"
