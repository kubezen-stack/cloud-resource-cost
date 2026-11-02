"""Price List stand-in built from real AWS responses saved in tests/fixtures/pricing.

Products marked SYNTHETIC are not real AWS data: they only fill gaps in the saved samples
(NAT gateway data processing price, Graviton m6g.large) so the code paths can be tested.
"""
import json
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from app.services.pricing import Product

FIXTURES = Path(__file__).parent / "fixtures" / "pricing"
FILES = ["ec2.json", "rds.json", "rds-storage.json", "cache.json", "alb.json", "nat-regional.json", "nat-classic.json"]

EC2_M6I_LARGE = Decimal("0.115")
EC2_M6I_LARGE_RESERVED_1Y = Decimal("0.07607")
RDS_M6G_LARGE_MULTI_AZ = Decimal("0.379")
RDS_M6G_LARGE_RESERVED_1Y = Decimal("0.2705")
RDS_GP3_MULTI_AZ_GB = Decimal("0.274")
CACHE_M6G_LARGE = Decimal("0.177")
CACHE_M6G_LARGE_RESERVED_1Y = Decimal("0.121")
ALB_HOUR = Decimal("0.027")
ALB_LCU = Decimal("0.008")
NAT_HOUR = Decimal("0.052")

NAT_GB = Decimal("0.052")
EC2_M6G_LARGE = Decimal("0.092")
EC2_M6G_LARGE_RESERVED_1Y = Decimal("0.0608")


def synthetic_product(service_code: str, family: str, attributes: Dict[str, str], hourly: Decimal,
                      unit: str = "Hrs", reserved_hourly: Optional[Decimal] = None) -> tuple:
    sku = "SYNTHETIC" + attributes.get("usagetype", attributes.get("instanceType", "x"))
    terms = {"OnDemand": {f"{sku}.OD": {"priceDimensions": {f"{sku}.OD.D": {
        "unit": unit, "pricePerUnit": {"USD": str(hourly)}}}}}}
    if reserved_hourly is not None:
        terms["Reserved"] = {f"{sku}.RI": {
            "priceDimensions": {f"{sku}.RI.D": {"unit": "Hrs", "pricePerUnit": {"USD": str(reserved_hourly)}}},
            "termAttributes": {"LeaseContractLength": "1yr", "OfferingClass": "standard", "PurchaseOption": "No Upfront"}}}
    attrs = {"locationType": "AWS Region", "location": "EU (Frankfurt)", **attributes}
    return service_code, Product(sku=sku, attributes={**attrs, "productFamily": family}, terms=terms,
                                 published="2026-11-01T00:00:00Z")


def default_synthetic() -> List[tuple]:
    return [
        synthetic_product("AmazonEC2", "NAT Gateway", {"usagetype": "EUC1-NatGateway-Bytes"}, NAT_GB, unit="GB"),
        synthetic_product("AmazonEC2", "Compute Instance", {
            "instanceType": "m6g.large", "operatingSystem": "Linux", "tenancy": "Shared",
            "preInstalledSw": "NA", "capacitystatus": "Used"}, EC2_M6G_LARGE, reserved_hourly=EC2_M6G_LARGE_RESERVED_1Y),
    ]


class FakePriceSource:
    def __init__(self, synthetic: Optional[List[tuple]] = None, skip: Optional[List[str]] = None):
        self.products: List[tuple] = []
        for name in FILES:
            raw_file = json.loads((FIXTURES / name).read_text())
            for item in raw_file["PriceList"]:
                raw = json.loads(item)
                product = Product.from_raw(raw)
                attributes = {**product.attributes, "productFamily": raw["product"]["productFamily"]}
                self.products.append((raw["serviceCode"], Product(product.sku, attributes, product.terms, product.published)))
        self.products += default_synthetic() if synthetic is None else synthetic
        self.skip = skip or []  # instance types to hide, to test missing prices
        self.calls: List[tuple] = []

    async def get_products(self, service_code: str, filters: Dict[str, str]) -> List[Product]:
        self.calls.append((service_code, dict(filters)))
        return [
            p for code, p in self.products
            if code == service_code
            and p.attributes.get("instanceType") not in self.skip
            and all(p.attributes.get(k) == v for k, v in filters.items())
        ]
