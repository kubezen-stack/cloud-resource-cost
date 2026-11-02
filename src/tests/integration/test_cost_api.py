import pytest

from app.api.v1 import advisor as advisor_api
from app.main import app
from app.services.pricing import PricingUnavailable
from tests.fake_pricing import FakePriceSource
from tests.unit.test_cost_estimator import shop_plan

URL = "/api/v1/advisor/cost"


@pytest.fixture(autouse=True)
def reset_override():
    yield
    app.dependency_overrides.pop(advisor_api.get_price_source, None)


def use_source(source):
    app.dependency_overrides[advisor_api.get_price_source] = lambda: source


def body(**extra):
    return {"plan": shop_plan().model_dump(), **extra}


@pytest.mark.asyncio
async def test_cost_endpoint_returns_estimate(client, auth_headers):
    use_source(FakePriceSource())
    response = await client.post(URL, json=body(), headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["region"] == "eu-central-1" and data["hours_per_month"] == 730
    assert data["fixed_monthly_usd"] > 0 and data["lines"] and data["usage_based"]
    assert {a["key"] for a in data["alternatives"]} == {"reserved_1y", "graviton", "reserved_1y_graviton"}


@pytest.mark.asyncio
async def test_cost_endpoint_requires_authentication(client):
    response = await client.post(URL, json=body())
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_invalid_region_format_is_rejected(client, auth_headers):
    use_source(FakePriceSource())
    response = await client.post(URL, json=body(region="Frankfurt"), headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unknown_region_is_a_client_error(client, auth_headers):
    use_source(FakePriceSource())
    response = await client.post(URL, json=body(region="xx-nowhere-9"), headers=auth_headers)
    assert response.status_code == 400 and "xx-nowhere-9" in response.json()["detail"]


@pytest.mark.asyncio
async def test_price_list_outage_is_bad_gateway(client, auth_headers):
    class Broken:
        async def get_products(self, service_code, filters):
            raise PricingUnavailable("down")

    use_source(Broken())
    response = await client.post(URL, json=body(), headers=auth_headers)
    assert response.status_code == 502 and "unavailable" in response.json()["detail"]
