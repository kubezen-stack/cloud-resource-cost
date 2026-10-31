import uuid
from unittest.mock import patch

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.aws_account import AWSaccount
from app.models.rightsizing_recommendation import RightsizingRecommendation
from app.services.rightsizing_service import InstanceMetrics

COLLECT = "app.services.cloudwatch_service.AWSInfraService.collect_instance_metrics"
HOURS = 24 * 14


@pytest_asyncio.fixture
async def aws_account(test_user, db_session):
    account = AWSaccount(
        id=uuid.uuid4(),
        user_id=test_user.id,
        aws_account_name="Test Account",
        aws_account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/TestRole",
        external_id="ext-123",
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


def _instance(instance_id, instance_type, avg, peak, name=None, hours=HOURS, region="us-east-1"):
    rng = np.random.default_rng(0)
    hourly_avg = list(np.clip(avg + rng.normal(0, 1, hours), 0, 100))
    hourly_max = [min(100.0, max(v, peak)) for v in hourly_avg]
    return InstanceMetrics(instance_id, name, instance_type, region, hourly_avg, hourly_max)


def _fleet():
    return [
        _instance("i-big", "m5.xlarge", avg=10, peak=25, name="oversized"),
        _instance("i-busy", "m5.xlarge", avg=45, peak=70, name="busy"),
        _instance("i-new", "m5.large", avg=10, peak=20, hours=10),
    ]


URL = "/api/v1/costs/{}/rightsizing"


@pytest.mark.asyncio
async def test_detect_returns_recommendations(client, auth_headers, aws_account):
    with patch(COLLECT, return_value=_fleet()):
        response = await client.post(URL.format(aws_account.aws_account_id) + "/detect", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["instances_analyzed"] == 3
    assert data["regions"] == ["us-east-1"]
    by_id = {r["instance_id"]: r for r in data["recommendations"]}
    assert by_id["i-big"]["action"] == "downsize"
    assert by_id["i-big"]["recommended_type"] == "m5.large"
    assert by_id["i-big"]["estimated_savings_pct"] == 50.0
    assert by_id["i-big"]["name"] == "oversized"
    assert by_id["i-busy"]["action"] == "keep"
    assert by_id["i-new"]["action"] == "insufficient_data"
    assert "CPU only" in data["note"]


@pytest.mark.asyncio
async def test_detect_passes_regions_and_days(client, auth_headers, aws_account):
    with patch(COLLECT, return_value=[]) as collect:
        response = await client.post(
            URL.format(aws_account.aws_account_id) + "/detect?regions=eu-west-1&regions=us-east-1&days=7",
            headers=auth_headers,
        )

    assert response.status_code == 200
    collect.assert_called_once_with(["eu-west-1", "us-east-1"], 7)


@pytest.mark.asyncio
async def test_results_are_persisted_and_listed(client, auth_headers, aws_account):
    with patch(COLLECT, return_value=_fleet()):
        await client.post(URL.format(aws_account.aws_account_id) + "/detect", headers=auth_headers)

    response = await client.get(URL.format(aws_account.aws_account_id), headers=auth_headers)

    assert response.status_code == 200
    items = response.json()["recommendations"]
    assert len(items) == 3
    assert items[0]["instance_id"] == "i-big"  # biggest saving first
    assert items[0]["detected_at"] is not None


@pytest.mark.asyncio
async def test_list_can_filter_by_action(client, auth_headers, aws_account):
    with patch(COLLECT, return_value=_fleet()):
        await client.post(URL.format(aws_account.aws_account_id) + "/detect", headers=auth_headers)

    response = await client.get(URL.format(aws_account.aws_account_id) + "?action=downsize", headers=auth_headers)

    assert [r["instance_id"] for r in response.json()["recommendations"]] == ["i-big"]


@pytest.mark.asyncio
async def test_list_rejects_unknown_action(client, auth_headers, aws_account):
    response = await client.get(URL.format(aws_account.aws_account_id) + "?action=explode", headers=auth_headers)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_detect_replaces_previous_snapshot(client, auth_headers, aws_account, db_session):
    with patch(COLLECT, return_value=_fleet()):
        await client.post(URL.format(aws_account.aws_account_id) + "/detect", headers=auth_headers)
    with patch(COLLECT, return_value=[_instance("i-only", "m5.xlarge", avg=10, peak=25)]):
        await client.post(URL.format(aws_account.aws_account_id) + "/detect", headers=auth_headers)

    rows = (await db_session.execute(select(RightsizingRecommendation))).scalars().all()
    assert [r.instance_id for r in rows] == ["i-only"]


@pytest.mark.asyncio
async def test_detect_unknown_account_is_404(client, auth_headers):
    with patch(COLLECT) as collect:
        response = await client.post(URL.format("999999999999") + "/detect", headers=auth_headers)

    assert response.status_code == 404
    collect.assert_not_called()


@pytest.mark.asyncio
async def test_detect_requires_authentication(client, aws_account):
    response = await client.post(URL.format(aws_account.aws_account_id) + "/detect")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_aws_error_is_returned_as_400(client, auth_headers, aws_account):
    with patch(COLLECT, side_effect=ValueError("Failed to collect instance metrics in us-east-1: denied")):
        response = await client.post(URL.format(aws_account.aws_account_id) + "/detect", headers=auth_headers)

    assert response.status_code == 400
    assert "denied" in response.json()["detail"]


@pytest.mark.asyncio
async def test_unexpected_error_hides_internals(client, auth_headers, aws_account):
    with patch(COLLECT, side_effect=RuntimeError("secret internals")):
        response = await client.post(URL.format(aws_account.aws_account_id) + "/detect", headers=auth_headers)

    assert response.status_code == 500
    assert "secret" not in response.text
