import json
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from app.services.pricing import (
    AWSPriceSource, PriceBook, PricingUnavailable, Product, UnsupportedRegion, location_for,
)
from tests import fake_pricing as fp
from tests.fake_pricing import FIXTURES, FakePriceSource


def first_product(name):
    raw = json.loads(json.loads((FIXTURES / name).read_text())["PriceList"][0])
    return Product.from_raw(raw)


def test_on_demand_price_is_parsed_from_real_sample():
    product = first_product("ec2.json")
    price = product.on_demand()
    assert product.attributes["instanceType"] == "m6i.large"
    assert price.amount == fp.EC2_M6I_LARGE and price.unit == "Hrs" and price.upfront == 0


def test_reserved_terms_are_selected_by_attributes():
    product = first_product("ec2.json")
    no_upfront = product.reserved(1, "standard", "No Upfront")
    assert no_upfront.amount == fp.EC2_M6I_LARGE_RESERVED_1Y and no_upfront.upfront == 0
    partial = product.reserved(1, "standard", "Partial Upfront")
    assert partial.amount == Decimal("0.03623") and partial.upfront == Decimal("317")
    assert product.reserved(5, "standard", "No Upfront") is None


def test_location_mapping_and_unknown_region():
    assert location_for("eu-central-1") == "EU (Frankfurt)"
    with pytest.raises(UnsupportedRegion):
        location_for("mars-north-1")


@pytest.mark.asyncio
async def test_price_book_finds_every_kind_in_real_samples():
    book = PriceBook(FakePriceSource(), "eu-central-1")
    assert (await book.ec2("m6i.large")).on_demand().amount == fp.EC2_M6I_LARGE
    assert (await book.rds_instance("db.m6g.large", "PostgreSQL", True)).on_demand().amount == fp.RDS_M6G_LARGE_MULTI_AZ
    assert (await book.rds_storage("PostgreSQL", True)).on_demand().amount == fp.RDS_GP3_MULTI_AZ_GB
    assert (await book.cache_node("cache.m6g.large", "Redis")).on_demand().amount == fp.CACHE_M6G_LARGE
    assert await book.ec2("m6i.nonexistent") is None
    assert await book.rds_instance("db.m6g.large", "PostgreSQL", False) is None  # Single-AZ not in the samples


@pytest.mark.asyncio
async def test_alb_ignores_trust_store_and_outposts_variants():
    book = PriceBook(FakePriceSource(), "eu-central-1")
    assert (await book.alb_hour()).on_demand().amount == fp.ALB_HOUR  # not the 0.006 trust store item
    assert (await book.alb_lcu()).on_demand().amount == fp.ALB_LCU


@pytest.mark.asyncio
async def test_classic_nat_is_not_confused_with_regional_nat():
    book = PriceBook(FakePriceSource(), "eu-central-1")
    hour = await book.nat_hour()
    assert hour.attributes["usagetype"] == "EUC1-NatGateway-Hours" and hour.on_demand().amount == fp.NAT_HOUR
    assert await book.nat_gb() is not None  # Regional NAT per-GB items must not be picked up as classic


@pytest.mark.asyncio
async def test_regional_nat_samples_alone_do_not_match_classic_nat():
    source = FakePriceSource(synthetic=[])
    source.products = [(c, p) for c, p in source.products if "NatGateway-Hours" not in p.attributes.get("usagetype", "")]
    assert await PriceBook(source, "eu-central-1").nat_hour() is None


class FakeBoto:
    def __init__(self, pages=None, error=None):
        self.pages, self.error, self.calls = pages or [], error, []

    def get_paginator(self, name):
        assert name == "get_products"
        outer = self

        class Paginator:
            def paginate(self, **kwargs):
                outer.calls.append(kwargs)
                if outer.error:
                    raise outer.error
                return iter(outer.pages)
        return Paginator()


def ec2_pages():
    return [json.loads((FIXTURES / "ec2.json").read_text())]


@pytest.mark.asyncio
async def test_source_converts_filters_parses_json_and_caches():
    client = FakeBoto(pages=ec2_pages())
    source = AWSPriceSource(client=client)

    first = await source.get_products("AmazonEC2", {"location": "EU (Frankfurt)", "instanceType": "m6i.large"})
    second = await source.get_products("AmazonEC2", {"instanceType": "m6i.large", "location": "EU (Frankfurt)"})

    assert first is second and len(client.calls) == 1
    kwargs = client.calls[0]
    assert kwargs["ServiceCode"] == "AmazonEC2"
    assert {"Type": "TERM_MATCH", "Field": "instanceType", "Value": "m6i.large"} in kwargs["Filters"]
    assert first[0].on_demand().amount == fp.EC2_M6I_LARGE


@pytest.mark.asyncio
async def test_source_cache_expires():
    client = FakeBoto(pages=ec2_pages())
    source = AWSPriceSource(ttl_seconds=0, client=client)
    await source.get_products("AmazonEC2", {"a": "b"})
    await source.get_products("AmazonEC2", {"a": "b"})
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_api_errors_become_pricing_unavailable():
    error = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "GetProducts")
    source = AWSPriceSource(client=FakeBoto(error=error))
    with pytest.raises(PricingUnavailable):
        await source.get_products("AmazonEC2", {"a": "b"})
