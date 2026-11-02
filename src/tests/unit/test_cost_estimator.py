from decimal import ROUND_HALF_UP, Decimal

import pytest

from app.schemas.advisor import AdvisorPlan, Component
from app.services.cost_estimator import estimate_cost
from tests import fake_pricing as fp
from tests.fake_pricing import FakePriceSource, default_synthetic, synthetic_product

H = Decimal(730)


def cents(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def component(name, service, role="other", sizing="x", **extra):
    return {"name": name, "aws_service": service, "sizing": sizing, "rationale": "r", "role": role, **extra}


def shop_plan(**overrides):
    data = {
        "summary": "shop",
        "capacity": {"peak_rps": 200, "cpu_ms_per_request": 20, "availability_zones": 2},
        "components": [
            component("Application Load Balancer", "Elastic Load Balancing", "network"),
            component("Web Servers", "EC2", "compute", instance_count=3, max_instances=6, vcpu_per_instance=2,
                      instance_class="m6i.large"),
            component("PostgreSQL Database", "Amazon RDS", "database", instance_class="db.m6g.large",
                      storage_gb=65, multi_az=True),
            component("Redis Cache", "ElastiCache", "cache", instance_class="cache.m6g.large", replicas=1),
            component("Static Content and CDN", "S3 and CloudFront", "storage"),
            component("Security", "VPC, Security Groups, KMS", "security", sizing="Private subnets, encryption"),
            component("Monitoring", "CloudWatch", "monitoring"),
        ],
    }
    data.update(overrides)
    return AdvisorPlan.model_validate(data)


EC2 = 3 * fp.EC2_M6I_LARGE * H
RDS = fp.RDS_M6G_LARGE_MULTI_AZ * H
STORAGE = 65 * fp.RDS_GP3_MULTI_AZ_GB
CACHE = 2 * fp.CACHE_M6G_LARGE * H
ALB = fp.ALB_HOUR * H
NAT = 2 * fp.NAT_HOUR * H
FIXED = EC2 + RDS + STORAGE + CACHE + ALB + NAT


@pytest.mark.asyncio
async def test_fixed_total_matches_hand_calculation_from_real_prices():
    estimate = await estimate_cost(shop_plan(), "eu-central-1", FakePriceSource())

    assert estimate.fixed_monthly_usd == cents(FIXED)
    assert estimate.unpriced == []
    by_item = {line.item: line for line in estimate.lines}
    assert by_item["m6i.large on-demand Linux"].monthly_usd == cents(EC2)
    assert by_item["m6i.large on-demand Linux"].quantity == 3
    assert by_item["db.m6g.large PostgreSQL Multi-AZ"].monthly_usd == cents(RDS)
    assert by_item["gp3 storage Multi-AZ"].monthly_usd == cents(STORAGE)
    assert by_item["cache.m6g.large Redis x 2 node(s)"].monthly_usd == cents(CACHE)
    assert by_item["Application Load Balancer hours"].monthly_usd == cents(ALB)
    assert estimate.prices_as_of.startswith("2026-")


@pytest.mark.asyncio
async def test_upper_bound_counts_compute_at_maximum():
    estimate = await estimate_cost(shop_plan(), "eu-central-1", FakePriceSource())
    assert estimate.upper_bound_monthly_usd == cents(FIXED + 3 * fp.EC2_M6I_LARGE * H)


@pytest.mark.asyncio
async def test_nat_is_added_as_assumption_only_with_private_subnets():
    estimate = await estimate_cost(shop_plan(), "eu-central-1", FakePriceSource())
    nat = next(line for line in estimate.lines if line.item == "NAT Gateway hours")
    assert nat.assumed and nat.quantity == 2 and nat.monthly_usd == cents(NAT) and "VPC endpoints" in nat.note

    plan = shop_plan()
    plan.components[5].sizing = "Security groups only"
    plan.components[5].rationale = "r"
    estimate = await estimate_cost(plan, "eu-central-1", FakePriceSource())
    assert all(line.item != "NAT Gateway hours" for line in estimate.lines)


@pytest.mark.asyncio
async def test_usage_based_items_are_listed_not_priced():
    estimate = await estimate_cost(shop_plan(), "eu-central-1", FakePriceSource())
    items = {u.item: u for u in estimate.usage_based}
    assert {"CloudFront", "S3 storage and requests", "KMS", "CloudWatch"} <= set(items)
    assert items["Load balancer capacity units (LCU)"].unit_price_usd == float(fp.ALB_LCU)
    assert items["NAT Gateway data processed"].unit_price_usd == float(fp.NAT_GB)
    assert items["CloudFront"].unit_price_usd is None


@pytest.mark.asyncio
async def test_reserved_alternative_reprices_instances_only():
    estimate = await estimate_cost(shop_plan(), "eu-central-1", FakePriceSource())
    alt = next(a for a in estimate.alternatives if a.key == "reserved_1y")

    reserved = 3 * fp.EC2_M6I_LARGE_RESERVED_1Y * H + fp.RDS_M6G_LARGE_RESERVED_1Y * H + 2 * fp.CACHE_M6G_LARGE_RESERVED_1Y * H
    expected = reserved + STORAGE + ALB + NAT
    assert alt.monthly_usd == cents(expected)
    assert alt.saving_usd == cents(FIXED - expected)
    assert alt.saving_pct == float(((FIXED - expected) / FIXED * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    assert any("One year commitment" in c for c in alt.caveats)


@pytest.mark.asyncio
async def test_graviton_and_combined_alternatives():
    estimate = await estimate_cost(shop_plan(), "eu-central-1", FakePriceSource())
    graviton = next(a for a in estimate.alternatives if a.key == "graviton")
    combined = next(a for a in estimate.alternatives if a.key == "reserved_1y_graviton")

    assert graviton.monthly_usd == cents(FIXED - 3 * (fp.EC2_M6I_LARGE - fp.EC2_M6G_LARGE) * H)
    assert any("m6g.large" in line.item for line in graviton.lines)
    assert any("arm64" in c for c in graviton.caveats)
    expected = (3 * fp.EC2_M6G_LARGE_RESERVED_1Y * H + fp.RDS_M6G_LARGE_RESERVED_1Y * H
                + 2 * fp.CACHE_M6G_LARGE_RESERVED_1Y * H + STORAGE + ALB + NAT)
    assert combined.monthly_usd == cents(expected)
    assert combined.saving_pct > graviton.saving_pct


@pytest.mark.asyncio
async def test_no_graviton_alternative_when_price_is_missing_or_already_arm():
    without = FakePriceSource(synthetic=[s for s in default_synthetic() if s[1].attributes.get("instanceType") != "m6g.large"])
    estimate = await estimate_cost(shop_plan(), "eu-central-1", without)
    assert [a.key for a in estimate.alternatives] == ["reserved_1y"]


@pytest.mark.asyncio
async def test_missing_prices_are_reported_not_invented():
    plan = shop_plan()
    plan.components[1].instance_class = "m6i.nonexistent"
    estimate = await estimate_cost(plan, "eu-central-1", FakePriceSource())
    assert any("m6i.nonexistent" in u for u in estimate.unpriced)
    # Without a priced server the assumed NAT gateway (needed by servers in private subnets) is not added either.
    assert estimate.fixed_monthly_usd == cents(FIXED - EC2 - NAT)


@pytest.mark.asyncio
async def test_unsupported_components_are_listed_as_unpriced():
    plan = shop_plan()
    plan.components[2].aws_service = "Amazon Aurora"
    plan.components[2].name = "Aurora Database"
    plan.components.append(Component(**component("Search", "OpenSearch Service", "other")))
    estimate = await estimate_cost(plan, "eu-central-1", FakePriceSource())
    assert any("Aurora Database" in u for u in estimate.unpriced)
    assert any("Search" in u and "not supported" in u for u in estimate.unpriced)


@pytest.mark.asyncio
async def test_unspecified_multi_az_is_assumed_from_zones():
    plan = shop_plan()
    plan.components[2].multi_az = None
    estimate = await estimate_cost(plan, "eu-central-1", FakePriceSource())
    line = next(l for l in estimate.lines if l.item.startswith("db.m6g.large"))
    assert line.assumed and "Multi-AZ" in line.item and "assumed" in line.note


@pytest.mark.asyncio
async def test_plan_without_priceable_components_returns_empty_estimate():
    plan = AdvisorPlan.model_validate({"summary": "s", "components": [component("Site", "S3", "storage")]})
    estimate = await estimate_cost(plan, "eu-central-1", FakePriceSource())
    assert estimate.fixed_monthly_usd == 0 and estimate.alternatives == [] and estimate.usage_based


@pytest.mark.asyncio
async def test_single_zone_plan_has_single_nat():
    plan = shop_plan(capacity={"peak_rps": 10, "cpu_ms_per_request": 20, "availability_zones": 1})
    estimate = await estimate_cost(plan, "eu-central-1", FakePriceSource())
    assert next(l for l in estimate.lines if l.item == "NAT Gateway hours").quantity == 1
