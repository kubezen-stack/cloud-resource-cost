from datetime import date, timedelta

from app.services.anomaly_explain import (
    MAX_DRIVERS,
    describe_drivers,
    explain_spike,
    meaning_of,
    parse_usage_costs,
)

DAY = date(2026, 11, 3)
REGION = "eu-central-1"


def history(level, spike=None, days=20):
    """Costs of the 20 days before DAY at a constant level, and DAY itself."""
    costs = {DAY - timedelta(days=i): level for i in range(1, days + 1)}
    costs[DAY] = level if spike is None else spike
    return costs


def test_a_nat_gateway_spike_is_named_as_the_driver():
    series = {
        ("EUC1-BoxUsage:m6i.large", REGION): history(40.0),
        ("EUC1-NatGateway-Bytes", REGION): history(2.0, spike=97.0),
        ("EUC1-NatGateway-Hours", REGION): history(3.0),
    }
    drivers = explain_spike(series, DAY)
    assert [d.usage_type for d in drivers] == ["EUC1-NatGateway-Bytes"]
    assert drivers[0].increase == 95.0 and round(drivers[0].share, 2) == 1.0
    assert drivers[0].meaning == "data processed by a NAT Gateway" and not drivers[0].is_new


def test_a_usage_type_that_never_appeared_before_is_new():
    series = {
        ("EUC1-BoxUsage:m6i.large", REGION): history(40.0),
        ("EUC1-DataTransfer-Out-Bytes", REGION): {DAY: 30.0},
    }
    (driver,) = explain_spike(series, DAY)
    assert driver.is_new and driver.expected_cost == 0.0 and driver.actual_cost == 30.0


def test_several_drivers_are_listed_largest_first_until_most_of_the_increase_is_covered():
    series = {
        ("A", REGION): history(10.0, spike=70.0),   # +60
        ("B", REGION): history(10.0, spike=40.0),   # +30
        ("C", REGION): history(10.0, spike=15.0),   # +5, not needed: A and B cover 90%
    }
    assert [d.usage_type for d in explain_spike(series, DAY)] == ["A", "B"]


def test_never_more_than_the_maximum_number_of_drivers():
    series = {(f"T{i}", REGION): history(10.0, spike=10.0 + 10 + i) for i in range(10)}
    assert len(explain_spike(series, DAY)) == MAX_DRIVERS


def test_nothing_is_reported_when_no_usage_type_increased():
    series = {("A", REGION): history(10.0), ("B", REGION): history(5.0, spike=1.0)}
    assert explain_spike(series, DAY) == []


def test_a_short_history_still_gives_an_answer():
    series = {("A", REGION): {DAY - timedelta(days=1): 5.0, DAY: 50.0}}
    (driver,) = explain_spike(series, DAY)
    assert driver.actual_cost == 50.0 and not driver.is_new


def test_the_median_ignores_one_earlier_spike():
    costs = history(10.0, spike=40.0)
    costs[DAY - timedelta(days=3)] = 500.0
    (driver,) = explain_spike({("A", REGION): costs}, DAY)
    assert driver.expected_cost == 10.0


def test_meaning_of_known_and_unknown_usage_types():
    assert meaning_of("EUC1-BoxUsage:m6i.large") == "instance hours"
    assert meaning_of("EUC1-DataTransfer-Out-Bytes") == "data transfer"
    assert meaning_of("EBS:SnapshotUsage") == "volume snapshots"
    assert meaning_of("EBS:VolumeUsage.gp3") == "EBS volumes"
    assert meaning_of("SomethingNew") is None


def test_parse_groups_by_usage_type_and_region_and_skips_bad_rows():
    results = [
        {"TimePeriod": {"Start": "2026-11-03", "End": "2026-11-04"}, "Groups": [
            {"Keys": ["EUC1-NatGateway-Bytes", REGION], "Metrics": {"UnblendedCost": {"Amount": "1.5"}}},
            {"Keys": ["EUC1-NatGateway-Bytes", REGION], "Metrics": {"UnblendedCost": {"Amount": "0.5"}}},
            {"Keys": ["only-one-key"], "Metrics": {"UnblendedCost": {"Amount": "9"}}},
            {"Keys": ["bad", REGION], "Metrics": {"UnblendedCost": {"Amount": "n/a"}}},
        ]},
        {"Groups": []},
    ]
    assert parse_usage_costs(results) == {("EUC1-NatGateway-Bytes", REGION): {DAY: 2.0}}


def test_description_is_one_line_with_the_numbers():
    series = {
        ("EUC1-BoxUsage:m6i.large", REGION): history(40.0),
        ("EUC1-NatGateway-Bytes", REGION): history(2.0, spike=97.0),
    }
    text = describe_drivers(explain_spike(series, DAY))
    assert text == ("main driver: `EUC1-NatGateway-Bytes` (eu-central-1, data processed by a NAT Gateway) "
                    "+$95.00 (100% of the increase)")
    assert "\n" not in text
    assert describe_drivers([]) is None


def test_description_marks_new_and_unknown_types():
    text = describe_drivers(explain_spike({("Mystery", REGION): {DAY: 12.0}}, DAY))
    assert text == "main driver: `Mystery` (eu-central-1) +$12.00 (100% of the increase), new"
