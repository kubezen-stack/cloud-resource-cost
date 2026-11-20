from datetime import date, timedelta

import pytest

from app.services.anomaly_advice import advise
from app.services.anomaly_explain import explain_spike, parse_usage_costs
from app.services.anomaly_service import detect_anomalies
from app.services.demo_data import BILL, SPIKE_SERVICE, SPIKE_USAGE_TYPE, DemoAdviceClient, DemoCostExplorer

SPIKE_DAY = date(2026, 11, 18)
TODAY = SPIKE_DAY + timedelta(days=2)
CE = DemoCostExplorer(SPIKE_DAY)


def _daily(**extra):
    return CE.get_cost_and_usage(
        TimePeriod={"Start": str(TODAY - timedelta(days=90)), "End": str(TODAY)},
        Granularity="DAILY", Metrics=["UnblendedCost"], **extra)["ResultsByTime"]


def _amount(group_or_total) -> float:
    return float(group_or_total["UnblendedCost"]["Amount"])


def test_monthly_total_is_the_sum_of_the_days():
    period = {"Start": "2026-11-01", "End": str(TODAY)}
    month = CE.get_cost_and_usage(TimePeriod=period, Granularity="MONTHLY", Metrics=["UnblendedCost"])
    daily = CE.get_cost_and_usage(TimePeriod=period, Granularity="DAILY", Metrics=["UnblendedCost"])
    assert len(month["ResultsByTime"]) == 1
    assert _amount(month["ResultsByTime"][0]["Total"]) == pytest.approx(
        sum(_amount(p["Total"]) for p in daily["ResultsByTime"]))


def test_grouped_costs_add_up_to_the_total():
    period = {"Start": "2026-11-01", "End": str(TODAY)}
    total = CE.get_cost_and_usage(TimePeriod=period, Granularity="MONTHLY", Metrics=["UnblendedCost"])
    by_service = CE.get_cost_and_usage(TimePeriod=period, Granularity="MONTHLY", Metrics=["UnblendedCost"],
                                       GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}])
    groups = by_service["ResultsByTime"][0]["Groups"]
    assert {g["Keys"][0] for g in groups} == set(BILL)
    assert sum(_amount(g["Metrics"]) for g in groups) == pytest.approx(_amount(total["ResultsByTime"][0]["Total"]))


def test_a_service_filter_keeps_only_that_service():
    usage = CE.get_cost_and_usage(
        TimePeriod={"Start": "2026-11-01", "End": "2026-11-05"}, Granularity="DAILY", Metrics=["UnblendedCost"],
        Filter={"Dimensions": {"Key": "SERVICE", "Values": [SPIKE_SERVICE]}},
        GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}, {"Type": "DIMENSION", "Key": "REGION"}])
    types = {g["Keys"][0] for p in usage["ResultsByTime"] for g in p["Groups"]}
    assert types == set(BILL[SPIKE_SERVICE])


def test_the_same_day_always_costs_the_same():
    assert DemoCostExplorer(SPIKE_DAY).cost(SPIKE_SERVICE, SPIKE_USAGE_TYPE, date(2026, 10, 1)) == \
        DemoCostExplorer(SPIKE_DAY).cost(SPIKE_SERVICE, SPIKE_USAGE_TYPE, date(2026, 10, 1))


def test_the_detector_flags_the_spike_day():
    flagged = {(a.service, a.day) for a in detect_anomalies(_daily(GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}]))}
    assert (SPIKE_SERVICE, SPIKE_DAY) in flagged


def test_the_breakdown_names_the_spiking_usage_type():
    usage = CE.get_cost_and_usage(
        TimePeriod={"Start": str(SPIKE_DAY - timedelta(days=14)), "End": str(SPIKE_DAY + timedelta(days=1))},
        Granularity="DAILY", Metrics=["UnblendedCost"],
        Filter={"Dimensions": {"Key": "SERVICE", "Values": [SPIKE_SERVICE]}},
        GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}, {"Type": "DIMENSION", "Key": "REGION"}])
    drivers = explain_spike(parse_usage_costs(usage["ResultsByTime"]), SPIKE_DAY)
    assert drivers[0].usage_type == SPIKE_USAGE_TYPE
    assert drivers[0].share > 0.9


@pytest.mark.asyncio
async def test_demo_advice_passes_the_same_checks_as_a_model_answer():
    anomaly = next(a for a in detect_anomalies(_daily(GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}]))
                   if a.service == SPIKE_SERVICE and a.day == SPIKE_DAY)
    usage = CE.get_cost_and_usage(
        TimePeriod={"Start": str(SPIKE_DAY - timedelta(days=14)), "End": str(SPIKE_DAY + timedelta(days=1))},
        Granularity="DAILY", Metrics=["UnblendedCost"],
        Filter={"Dimensions": {"Key": "SERVICE", "Values": [SPIKE_SERVICE]}},
        GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}, {"Type": "DIMENSION", "Key": "REGION"}])
    drivers = explain_spike(parse_usage_costs(usage["ResultsByTime"]), SPIKE_DAY)
    advice = await advise(DemoAdviceClient(anomaly, drivers), anomaly, drivers)
    assert advice.hypotheses[0].evidence == [SPIKE_USAGE_TYPE]
    assert advice.actions[0].source == "Data processed by a NAT Gateway"
