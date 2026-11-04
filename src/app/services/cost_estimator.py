"""Monthly cost of an advisor plan, computed from AWS list prices.

The language model only names instance classes and counts; every price, multiplication and
percentage here comes from the Price List and from this code.
"""
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Tuple

from app.schemas.advisor import AdvisorPlan, Component
from app.schemas.cost import Alternative, CostEstimate, CostLine, UsageItem
from app.services.pricing import PriceBook, PriceSource, Price, Product

HOURS_PER_MONTH = Decimal(730)

GRAVITON_FAMILIES = {
    "m5": "m6g", "m6i": "m6g", "m7i": "m7g",
    "c5": "c6g", "c6i": "c6g", "c7i": "c7g",
    "r5": "r6g", "r6i": "r6g", "r7i": "r7g",
    "t3": "t4g",
}

USAGE_ONLY = [
    ("cloudfront", "CloudFront", "Data transferred to viewers and number of requests"),
    ("s3", "S3 storage and requests", "Stored GB-months and number of requests"),
    ("sqs", "SQS", "Number of requests"),
    ("sns", "SNS", "Number of publishes and deliveries"),
    ("cloudwatch", "CloudWatch", "Custom metrics, alarms and log volume"),
    ("waf", "AWS WAF", "Web ACLs, rules and requests"),
    ("kms", "KMS", "Keys and requests"),
    ("route 53", "Route 53", "Hosted zones and queries"),
    ("lambda", "Lambda", "Requests and execution time"),
]


def money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def rate(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP))


@dataclass
class Priced:
    """A priced line together with the product it came from, so alternatives can reprice it."""
    kind: str  # ec2 | rds | cache | storage | alb | nat
    component: str
    item: str
    quantity: Decimal
    unit: str
    product: Product
    price: Price
    hours: bool = True  # monthly = quantity x price x 730 when billed per hour, else quantity x price
    assumed: bool = False
    note: Optional[str] = None
    instance_type: Optional[str] = None

    @property
    def monthly(self) -> Decimal:
        factor = HOURS_PER_MONTH if self.hours else Decimal(1)
        return self.quantity * self.price.amount * factor

    def to_line(self) -> CostLine:
        return CostLine(
            component=self.component, item=self.item, quantity=float(self.quantity), unit=self.unit,
            unit_price_usd=rate(self.price.amount), monthly_usd=money(self.monthly),
            sku=self.price.sku, assumed=self.assumed, note=self.note,
        )


@dataclass
class Collected:
    priced: List[Priced] = field(default_factory=list)
    usage: List[UsageItem] = field(default_factory=list)
    unpriced: List[str] = field(default_factory=list)
    extra_peak: Decimal = Decimal(0)  # compute above the steady count, if it ran all month
    published: List[str] = field(default_factory=list)


def _text(component: Component) -> str:
    return f"{component.name} {component.aws_service} {component.sizing}".lower()


def _db_engine(text: str) -> Optional[str]:
    if "aurora" in text:
        return None
    for keyword, engine in (("postgres", "PostgreSQL"), ("mysql", "MySQL"), ("mariadb", "MariaDB")):
        if keyword in text:
            return engine
    return None


def _cache_engine(text: str) -> str:
    if "valkey" in text:
        return "Valkey"
    if "memcached" in text:
        return "Memcached"
    return "Redis"


async def _price_component(book: PriceBook, component: Component, plan: AdvisorPlan, out: Collected) -> bool:
    """Price the component if it is one of the supported instance based or load balancer kinds."""
    text = _text(component)
    zones = plan.capacity.availability_zones if plan.capacity else 1

    if component.role == "compute" and component.instance_count and component.instance_class:
        product = await book.ec2(component.instance_class)
        price = product.on_demand() if product else None
        if not price:
            out.unpriced.append(f"{component.name}: no on-demand price found for {component.instance_class}")
            return True
        out.priced.append(Priced("ec2", component.name, f"{component.instance_class} on-demand Linux",
                                 Decimal(component.instance_count), "instance-hours", product, price,
                                 instance_type=component.instance_class))
        if component.max_instances and component.max_instances > component.instance_count:
            out.extra_peak += (component.max_instances - component.instance_count) * price.amount * HOURS_PER_MONTH
        return True

    if component.role == "database":
        engine = _db_engine(text)
        if not engine or not component.instance_class:
            out.unpriced.append(f"{component.name}: database engine or instance class not supported for pricing")
            return True
        assumed_az = component.multi_az is None
        multi_az = component.multi_az if component.multi_az is not None else zones >= 2
        note = "Multi-AZ was not stated, assumed from the number of zones" if assumed_az else None
        deployment = "Multi-AZ" if multi_az else "Single-AZ"
        instance = await book.rds_instance(component.instance_class, engine, multi_az)
        price = instance.on_demand() if instance else None
        if not price:
            out.unpriced.append(f"{component.name}: no RDS price for {component.instance_class} {engine} {deployment}")
            return True
        out.priced.append(Priced("rds", component.name, f"{component.instance_class} {engine} {deployment}",
                                 Decimal(1), "instance-hours", instance, price, assumed=assumed_az, note=note,
                                 instance_type=component.instance_class))
        if component.storage_gb:
            storage = await book.rds_storage(engine, multi_az)
            storage_price = storage.on_demand() if storage else None
            if storage_price:
                out.priced.append(Priced("storage", component.name, f"gp3 storage {deployment}",
                                         Decimal(component.storage_gb), "GB-months", storage, storage_price, hours=False))
            else:
                out.unpriced.append(f"{component.name}: no gp3 storage price found")
        return True

    if component.role == "cache" and component.instance_class:
        engine = _cache_engine(text)
        product = await book.cache_node(component.instance_class, engine)
        price = product.on_demand() if product else None
        if not price:
            out.unpriced.append(f"{component.name}: no ElastiCache price for {component.instance_class} {engine}")
            return True
        nodes = 1 + (component.replicas or 0)
        out.priced.append(Priced("cache", component.name, f"{component.instance_class} {engine} x {nodes} node(s)",
                                 Decimal(nodes), "node-hours", product, price, instance_type=component.instance_class))
        return True

    if "load balancer" in text or " alb" in f" {text}":
        if "network load balancer" in text or " nlb" in f" {text}":
            out.unpriced.append(f"{component.name}: Network Load Balancer pricing is not supported yet")
            return True
        hour, lcu = await book.alb_hour(), await book.alb_lcu()
        price = hour.on_demand() if hour else None
        if not price:
            out.unpriced.append(f"{component.name}: no Application Load Balancer price found")
            return True
        out.priced.append(Priced("alb", component.name, "Application Load Balancer hours", Decimal(1),
                                 "load-balancer-hours", hour, price))
        lcu_price = lcu.on_demand() if lcu else None
        out.usage.append(UsageItem(
            component=component.name, item="Load balancer capacity units (LCU)",
            depends_on="Connections, bytes processed and rule evaluations",
            unit_price_usd=rate(lcu_price.amount) if lcu_price else None, unit="LCU-hour"))
        return True

    if "nat gateway" in text:
        await _add_nat(book, component.name, zones, out, assumed=False)
        return True
    return False


async def _add_nat(book: PriceBook, name: str, zones: int, out: Collected, assumed: bool) -> None:
    hour, per_gb = await book.nat_hour(), await book.nat_gb()
    price = hour.on_demand() if hour else None
    if not price:
        out.unpriced.append(f"{name}: no NAT Gateway price found")
        return
    note = ("Assumed: one NAT gateway per Availability Zone for outbound traffic from private subnets. "
            "Not needed if only VPC endpoints are used." if assumed else None)
    out.priced.append(Priced("nat", name, "NAT Gateway hours", Decimal(zones), "gateway-hours", hour, price,
                             assumed=assumed, note=note))
    gb_price = per_gb.on_demand() if per_gb else None
    out.usage.append(UsageItem(
        component=name, item="NAT Gateway data processed", depends_on="GB sent through the gateway",
        unit_price_usd=rate(gb_price.amount) if gb_price else None, unit="GB"))


def _usage_only(component: Component, out: Collected) -> bool:
    text = _text(component)
    found = False
    for keyword, item, depends_on in USAGE_ONLY:
        # "s3" must not match inside other words.
        if keyword == "s3":
            matched = " s3" in f" {text}".replace("(", " ").replace(",", " ")
        else:
            matched = keyword in text
        if matched:
            found = True
            if not any(u.item == item for u in out.usage):
                out.usage.append(UsageItem(component=component.name, item=item, depends_on=depends_on))
    return found


def _total(items: List[Priced]) -> Decimal:
    return sum((i.monthly for i in items), Decimal(0))


def _compare(key: str, title: str, items: List[Priced], baseline: Decimal, caveats: List[str]) -> Alternative:
    total = _total(items)
    saving = baseline - total
    pct = (saving / baseline * 100) if baseline else Decimal(0)
    return Alternative(
        key=key, title=title, monthly_usd=money(total), saving_usd=money(saving),
        saving_pct=float(pct.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)),
        caveats=caveats, lines=[i.to_line() for i in items],
    )


def _reserved(item: Priced, caveats: List[str]) -> Priced:
    """The same line at the 1 year standard no-upfront reserved rate, when AWS publishes one."""
    if item.kind not in ("ec2", "rds", "cache"):
        return item
    reserved = item.product.reserved(years=1, offering_class="standard", purchase="No Upfront")
    if not reserved:
        caveats.append(f"No 1 year no-upfront reserved price is offered for {item.instance_type}: kept at on-demand")
        return item
    return replace(item, price=reserved, item=f"{item.item} (1 year reserved, no upfront)")


async def _graviton(book: PriceBook, item: Priced) -> Optional[Priced]:
    if item.kind != "ec2" or not item.instance_type or "." not in item.instance_type:
        return item
    family, size = item.instance_type.split(".", 1)
    target = GRAVITON_FAMILIES.get(family)
    if not target:
        return item
    product = await book.ec2(f"{target}.{size}")
    price = product.on_demand() if product else None
    if not price:
        return None
    return replace(item, product=product, price=price, instance_type=f"{target}.{size}",
                   item=f"{target}.{size} on-demand Linux (Graviton)")


async def estimate_cost(plan: AdvisorPlan, region: str, source: PriceSource) -> CostEstimate:
    book = PriceBook(source, region)
    out = Collected()

    for component in plan.components:
        handled = await _price_component(book, component, plan, out)
        if not handled and not _usage_only(component, out):
            if component.role in ("security", "monitoring", "network") and component.instance_count is None:
                out.unpriced.append(f"{component.name}: no fixed charge calculated for '{component.aws_service}'")
            else:
                out.unpriced.append(f"{component.name}: pricing for '{component.aws_service}' is not supported yet")

    has_compute = any(p.kind == "ec2" for p in out.priced)
    has_nat = any(p.kind == "nat" for p in out.priced)
    mentions_private = any("private subnet" in f"{c.sizing} {c.rationale} {c.name}".lower() for c in plan.components)
    if has_compute and mentions_private and not has_nat:
        zones = plan.capacity.availability_zones if plan.capacity else 1
        await _add_nat(book, "NAT Gateway (assumed)", zones, out, assumed=True)

    baseline = _total(out.priced)
    published = sorted({p.product.published for p in out.priced if p.product.published})
    notes = [
        "List prices, on-demand, 730 hours per month, before taxes and discounts. Fixed charges only.",
        "Compute is counted at the minimum instance_count. The upper bound assumes every instance runs at "
        "max_instances for the whole month.",
        "Charges that depend on usage are listed separately and are not part of the totals.",
        "Not included: EBS volumes of the servers, data transfer between zones and to the internet, backup "
        "storage beyond the database size, support plans.",
    ]
    estimate = CostEstimate(
        region=region,
        prices_as_of=published[-1] if published else "",
        hours_per_month=int(HOURS_PER_MONTH),
        lines=[p.to_line() for p in out.priced],
        fixed_monthly_usd=money(baseline),
        upper_bound_monthly_usd=money(baseline + out.extra_peak),
        usage_based=out.usage,
        unpriced=out.unpriced,
        alternatives=[],
        notes=notes,
    )
    if not out.priced:
        return estimate

    # Alternative 1: 1 year reserved capacity for the steady baseline.
    caveats = [
        "One year commitment: you pay for the term even if the servers are scaled down.",
        "Applies to the steady baseline (minimum instances), not to auto scaling above it.",
    ]
    reserved_items = [_reserved(i, caveats) for i in out.priced]
    estimate.alternatives.append(_compare(
        "reserved_1y", "1 year reserved capacity (standard, no upfront)", reserved_items, baseline, caveats))

    # Alternative 2: Graviton for servers.
    swapped: List[Priced] = []
    changed = False
    for item in out.priced:
        new = await _graviton(book, item)
        if new is None:
            new = item
        changed = changed or new is not item
        swapped.append(new)
    if changed:
        graviton_caveats = ["Requires arm64 builds of the application and its container images; test before switching."]
        estimate.alternatives.append(_compare(
            "graviton", "Graviton (arm64) servers, on-demand", swapped, baseline, graviton_caveats))
        # Alternative 3: both together.
        combined_caveats = graviton_caveats + caveats[:2]
        estimate.alternatives.append(_compare(
            "reserved_1y_graviton", "Graviton servers with 1 year reserved capacity",
            [_reserved(i, combined_caveats) for i in swapped], baseline, combined_caveats))
    return estimate
