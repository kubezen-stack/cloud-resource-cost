"""AWS Price List access and parsing. Prices always come from AWS, never from the language model."""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Protocol, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

REGION_LOCATIONS = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "ca-central-1": "Canada (Central)",
    "sa-east-1": "South America (Sao Paulo)",
    "eu-west-1": "EU (Ireland)",
    "eu-west-2": "EU (London)",
    "eu-west-3": "EU (Paris)",
    "eu-central-1": "EU (Frankfurt)",
    "eu-north-1": "EU (Stockholm)",
    "ap-south-1": "Asia Pacific (Mumbai)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
}

PRICING_API_REGION = "us-east-1"
CACHE_TTL_SECONDS = 24 * 3600
MAX_PRODUCTS = 200


class PricingError(Exception):
    pass


class UnsupportedRegion(PricingError):
    pass


class PricingUnavailable(PricingError):
    """The Price List API could not be reached or refused the request."""


def location_for(region: str) -> str:
    try:
        return REGION_LOCATIONS[region]
    except KeyError:
        raise UnsupportedRegion(f"Pricing is not configured for region '{region}'")


@dataclass(frozen=True)
class Price:
    amount: Decimal  # per unit (hour, GB-month, ...) as given by `unit`
    unit: str
    upfront: Decimal
    sku: str


@dataclass(frozen=True)
class Product:
    """One entry of the Price List: attributes plus its on-demand and reserved terms."""
    sku: str
    attributes: Dict[str, str]
    terms: Dict[str, Any]
    published: str

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "Product":
        product = raw.get("product", {})
        return cls(
            sku=product.get("sku", ""),
            attributes=product.get("attributes", {}),
            terms=raw.get("terms", {}),
            published=raw.get("publicationDate", ""),
        )

    @staticmethod
    def _price(sku: str, term: Dict[str, Any]) -> Optional[Price]:
        recurring: Optional[Tuple[Decimal, str]] = None
        upfront = Decimal(0)
        for dimension in term.get("priceDimensions", {}).values():
            amount = Decimal(dimension.get("pricePerUnit", {}).get("USD", "0"))
            if dimension.get("unit") == "Quantity":  # "Upfront Fee"
                upfront = amount
            else:
                recurring = (amount, dimension.get("unit", ""))
        if recurring is None:
            return None
        return Price(amount=recurring[0], unit=recurring[1], upfront=upfront, sku=sku)

    def on_demand(self) -> Optional[Price]:
        for term in self.terms.get("OnDemand", {}).values():
            price = self._price(self.sku, term)
            if price:
                return price
        return None

    def reserved(self, years: int = 1, offering_class: str = "standard", purchase: str = "No Upfront") -> Optional[Price]:
        for term in self.terms.get("Reserved", {}).values():
            attributes = term.get("termAttributes", {})
            if (
                attributes.get("LeaseContractLength") == f"{years}yr"
                and attributes.get("OfferingClass") == offering_class
                and attributes.get("PurchaseOption") == purchase
            ):
                return self._price(self.sku, term)
        return None


class PriceSource(Protocol):
    async def get_products(self, service_code: str, filters: Dict[str, str]) -> List[Product]: ...


class AWSPriceSource:
    """Reads the Price List API (pricing:GetProducts) and keeps answers in memory for a day."""

    def __init__(self, ttl_seconds: int = CACHE_TTL_SECONDS, client: Any = None):
        self._ttl = ttl_seconds
        self._client = client
        self._cache: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], Tuple[float, List[Product]]] = {}

    def _boto_client(self):
        if self._client is None:
            self._client = boto3.client(
                "pricing",
                region_name=PRICING_API_REGION,
                config=Config(retries={"max_attempts": 3}, connect_timeout=5, read_timeout=20),
            )
        return self._client

    def _fetch(self, service_code: str, filters: Dict[str, str]) -> List[Product]:
        try:
            paginator = self._boto_client().get_paginator("get_products")
            pages = paginator.paginate(
                ServiceCode=service_code,
                Filters=[{"Type": "TERM_MATCH", "Field": k, "Value": v} for k, v in filters.items()],
                PaginationConfig={"MaxItems": MAX_PRODUCTS},
            )
            return [Product.from_raw(json.loads(item)) for page in pages for item in page.get("PriceList", [])]
        except (ClientError, BotoCoreError, ValueError) as exc:
            raise PricingUnavailable(f"AWS Price List request failed: {type(exc).__name__}") from exc

    async def get_products(self, service_code: str, filters: Dict[str, str]) -> List[Product]:
        key = (service_code, tuple(sorted(filters.items())))
        cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < self._ttl:
            return cached[1]
        products = await asyncio.to_thread(self._fetch, service_code, filters)
        self._cache[key] = (time.monotonic(), products)
        return products


_default_source = AWSPriceSource()


def get_price_source() -> PriceSource:
    return _default_source


def _usage_product(products: List[Product], suffix: str) -> Optional[Product]:
    """Pick the regional product whose usagetype is exactly '<REGIONCODE><suffix>'.

    The result lists also Outposts, Local Zone and other variants whose usagetype has more segments.
    """
    for product in products:
        usage = product.attributes.get("usagetype", "")
        if (
            usage.endswith(suffix)
            and usage.count("-") == suffix.count("-")
            and product.attributes.get("locationType", "AWS Region") == "AWS Region"
        ):
            return product
    return None


class PriceBook:
    """Finds the products the cost estimate needs for one region."""

    def __init__(self, source: PriceSource, region: str):
        self.source = source
        self.region = region
        self.location = location_for(region)

    async def _find(self, service_code: str, filters: Dict[str, str], **must_equal: str) -> Optional[Product]:
        products = await self.source.get_products(service_code, {"location": self.location, **filters})
        for product in products:
            if all(product.attributes.get(k) == v for k, v in must_equal.items()):
                return product
        return None

    async def ec2(self, instance_type: str) -> Optional[Product]:
        return await self._find(
            "AmazonEC2",
            {"instanceType": instance_type, "operatingSystem": "Linux", "tenancy": "Shared",
             "preInstalledSw": "NA", "capacitystatus": "Used"},
            instanceType=instance_type, operatingSystem="Linux", tenancy="Shared",
        )

    async def rds_instance(self, instance_type: str, engine: str, multi_az: bool) -> Optional[Product]:
        deployment = "Multi-AZ" if multi_az else "Single-AZ"
        return await self._find(
            "AmazonRDS",
            {"instanceType": instance_type, "databaseEngine": engine, "deploymentOption": deployment},
            instanceType=instance_type, databaseEngine=engine, deploymentOption=deployment,
        )

    async def rds_storage(self, engine: str, multi_az: bool, volume_type: str = "General Purpose-GP3") -> Optional[Product]:
        deployment = "Multi-AZ" if multi_az else "Single-AZ"
        return await self._find(
            "AmazonRDS",
            {"productFamily": "Database Storage", "databaseEngine": engine,
             "deploymentOption": deployment, "volumeType": volume_type},
            volumeType=volume_type, databaseEngine=engine, deploymentOption=deployment,
        )

    async def cache_node(self, node_type: str, engine: str) -> Optional[Product]:
        return await self._find(
            "AmazonElastiCache", {"instanceType": node_type, "cacheEngine": engine},
            instanceType=node_type, cacheEngine=engine,
        )

    async def _usage(self, service_code: str, family: str, suffix: str) -> Optional[Product]:
        products = await self.source.get_products(service_code, {"location": self.location, "productFamily": family})
        return _usage_product(products, suffix)

    async def alb_hour(self) -> Optional[Product]:
        return await self._usage("AWSELB", "Load Balancer-Application", "-LoadBalancerUsage")

    async def alb_lcu(self) -> Optional[Product]:
        return await self._usage("AWSELB", "Load Balancer-Application", "-LCUUsage")

    async def nat_hour(self) -> Optional[Product]:
        return await self._usage("AmazonEC2", "NAT Gateway", "-NatGateway-Hours")

    async def nat_gb(self) -> Optional[Product]:
        return await self._usage("AmazonEC2", "NAT Gateway", "-NatGateway-Bytes")
