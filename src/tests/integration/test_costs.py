import pytest
import uuid
from unittest.mock import patch, MagicMock
from app.models.aws_account import AWSaccount
from datetime import datetime


@pytest.fixture
async def aws_account(test_user, db_session):
    account = AWSaccount(
        id=uuid.uuid4(),
        user_id=test_user.id,
        aws_account_name="Test Account",
        aws_account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/TestRole",
        external_id="ext-123"
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


MOCK_COSTS = [
    {
        "TimePeriod": {"Start": "2024-01-01", "End": "2024-01-02"},
        "Groups": [
            {"Keys": ["Amazon EC2"], "Metrics": {"UnblendedCost": {"Amount": "10.50", "Unit": "USD"}, "UsageQuantity": {"Amount": "100", "Unit": "Hrs"}}}
        ]
    }
]

MOCK_FORECAST = [
    {"TimePeriod": {"Start": "2024-02-01", "End": "2024-03-01"}, "MeanValue": "300.00"}
]


@pytest.mark.asyncio
async def test_get_costs_success(client, auth_headers, aws_account):
    with patch("app.services.cost_service.AWSCostService.get_cost_and_usage", return_value=MOCK_COSTS):
        response = await client.get(
            f"/api/v1/costs/{aws_account.id}/costs",
            headers=auth_headers
        )
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == str(aws_account.id)
    assert "results" in data


@pytest.mark.asyncio
async def test_get_costs_account_not_found(client, auth_headers):
    response = await client.get(
        f"/api/v1/costs/{uuid.uuid4()}/costs",
        headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_costs_unauthorized(client, aws_account):
    response = await client.get(f"/api/v1/costs/{aws_account.id}/costs")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_forecast_success(client, auth_headers, aws_account):
    with patch("app.services.cost_service.AWSCostService.get_cost_forecast", return_value=MOCK_FORECAST):
        response = await client.get(
            f"/api/v1/costs/{aws_account.id}/forecast",
            headers=auth_headers
        )
    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == str(aws_account.id)
    assert "forecast" in data


@pytest.mark.asyncio
async def test_get_forecast_account_not_found(client, auth_headers):
    response = await client.get(
        f"/api/v1/costs/{uuid.uuid4()}/forecast",
        headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_breakdown_success(client, auth_headers, aws_account):
    with patch("app.services.cost_service.AWSCostService.get_cost_and_usage", return_value=MOCK_COSTS):
        response = await client.get(
            f"/api/v1/costs/{aws_account.id}/breakdown",
            headers=auth_headers
        )
    assert response.status_code == 200
    data = response.json()
    assert "breakdown" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_get_breakdown_account_not_found(client, auth_headers):
    response = await client.get(
        f"/api/v1/costs/{uuid.uuid4()}/breakdown",
        headers=auth_headers
    )
    assert response.status_code == 404