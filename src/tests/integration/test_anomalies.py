import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.models.aws_account import AWSaccount
from app.models.cost_anomaly import CostAnomaly
from app.models.user import User

GET_COSTS = "app.services.cost_service.AWSCostService.get_cost_and_usage"


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

def _results(per_service, days=60):
    """Cost Explorer style results for the `days` days ending yesterday."""
    first = datetime.utcnow().date() - timedelta(days=days)
    results = []
    for i in range(days):
        day = first + timedelta(days=i)
        results.append({
            "TimePeriod": {"Start": day.isoformat(), "End": (day + timedelta(days=1)).isoformat()},
            "Groups": [
                {"Keys": [name], "Metrics": {"UnblendedCost": {"Amount": str(round(values[i], 4)), "Unit": "USD"}}}
                for name, values in per_service.items()
            ],
        })
    return results, first

def _with_spike(spike_index=50, days=60, spike=170.0):
    rng = np.random.default_rng(0)
    ec2 = list(50 + rng.normal(0, 2, days))
    s3 = list(10 + rng.normal(0, 0.3, days))
    ec2[spike_index] = spike
    return _results({"Amazon EC2": ec2, "Amazon S3": s3}, days)

def _calm():
    rng = np.random.default_rng(1)
    return _results({"Amazon EC2": list(50 + rng.normal(0, 2, 60))})

@pytest.mark.asyncio
async def test_detect_finds_and_returns_the_spike(client, auth_headers, aws_account):
    results, first = _with_spike()
    with patch(GET_COSTS, return_value=results):
        response = await client.post(f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["aws_account_id"] == aws_account.aws_account_id
    assert data["services_analyzed"] == 2
    assert len(data["anomalies"]) == 1
    anomaly = data["anomalies"][0]
    assert anomaly["service"] == "Amazon EC2"
    assert anomaly["date"] == (first + timedelta(days=50)).isoformat()
    assert anomaly["actual_cost"] == 170.0
    assert anomaly["deviation_pct"] > 100

@pytest.mark.asyncio
async def test_detect_persists_results_for_listing(client, auth_headers, aws_account):
    results, first = _with_spike()
    with patch(GET_COSTS, return_value=results):
        await client.post(f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect", headers=auth_headers)

    response = await client.get(f"/api/v1/costs/{aws_account.aws_account_id}/anomalies", headers=auth_headers)

    assert response.status_code == 200
    anomalies = response.json()["anomalies"]
    assert [(a["service"], a["date"]) for a in anomalies] == [("Amazon EC2", (first + timedelta(days=50)).isoformat())]
    assert anomalies[0]["detected_at"] is not None

@pytest.mark.asyncio
async def test_listing_does_not_call_aws(client, auth_headers, aws_account):
    with patch(GET_COSTS) as aws:
        response = await client.get(f"/api/v1/costs/{aws_account.aws_account_id}/anomalies", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["anomalies"] == []
    aws.assert_not_called()

@pytest.mark.asyncio
async def test_detect_is_idempotent(client, auth_headers, aws_account, db_session):
    results, _ = _with_spike()
    url = f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect"
    with patch(GET_COSTS, return_value=results):
        await client.post(url, headers=auth_headers)
        await client.post(url, headers=auth_headers)

    rows = (await db_session.execute(select(CostAnomaly))).scalars().all()
    assert len(rows) == 1

@pytest.mark.asyncio
async def test_rerun_replaces_stale_results(client, auth_headers, aws_account, db_session):
    url = f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect"
    spiky, _ = _with_spike()
    calm, _ = _calm()

    with patch(GET_COSTS, return_value=spiky):
        await client.post(url, headers=auth_headers)
    with patch(GET_COSTS, return_value=calm):
        response = await client.post(url, headers=auth_headers)

    assert response.json()["anomalies"] == []
    rows = (await db_session.execute(select(CostAnomaly))).scalars().all()
    assert rows == []

@pytest.mark.asyncio
async def test_calm_account_has_no_anomalies(client, auth_headers, aws_account):
    results, _ = _calm()
    with patch(GET_COSTS, return_value=results):
        response = await client.post(f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["anomalies"] == []
    assert response.json()["services_analyzed"] == 1

@pytest.mark.asyncio
async def test_list_can_filter_by_service(client, auth_headers, aws_account):
    results, _ = _with_spike()
    with patch(GET_COSTS, return_value=results):
        await client.post(f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect", headers=auth_headers)

    base = f"/api/v1/costs/{aws_account.aws_account_id}/anomalies"
    ec2 = await client.get(base, params={"service": "Amazon EC2"}, headers=auth_headers)
    s3 = await client.get(base, params={"service": "Amazon S3"}, headers=auth_headers)

    assert len(ec2.json()["anomalies"]) == 1
    assert s3.json()["anomalies"] == []

@pytest.mark.asyncio
async def test_list_respects_date_range(client, auth_headers, aws_account):
    results, first = _with_spike()
    with patch(GET_COSTS, return_value=results):
        await client.post(f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect", headers=auth_headers)

    base = f"/api/v1/costs/{aws_account.aws_account_id}/anomalies"
    after = (first + timedelta(days=51)).isoformat()
    on_day = (first + timedelta(days=50)).isoformat()

    assert (await client.get(base, params={"start_date": after}, headers=auth_headers)).json()["anomalies"] == []
    assert len((await client.get(base, params={"start_date": on_day, "end_date": on_day}, headers=auth_headers)).json()["anomalies"]) == 1

@pytest.mark.asyncio
async def test_list_rejects_bad_dates(client, auth_headers, aws_account):
    base = f"/api/v1/costs/{aws_account.aws_account_id}/anomalies"
    assert (await client.get(base, params={"start_date": "yesterday"}, headers=auth_headers)).status_code == 400
    assert (await client.get(base, params={"start_date": "2026-02-01", "end_date": "2026-01-01"}, headers=auth_headers)).status_code == 400

@pytest.mark.asyncio
async def test_detect_validates_days(client, auth_headers, aws_account):
    url = f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect"
    assert (await client.post(url, params={"days": 5}, headers=auth_headers)).status_code == 422
    assert (await client.post(url, params={"days": 1000}, headers=auth_headers)).status_code == 422

@pytest.mark.asyncio
async def test_detect_passes_requested_window_to_aws(client, auth_headers, aws_account):
    with patch(GET_COSTS, return_value=[]) as aws:
        response = await client.post(
            f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect", params={"days": 30}, headers=auth_headers
        )

    assert response.status_code == 200
    kwargs = aws.call_args.kwargs
    end = datetime.utcnow().date()
    assert kwargs["end_date"] == end.isoformat()
    assert kwargs["start_date"] == (end - timedelta(days=30)).isoformat()
    assert kwargs["granularity"] == "DAILY"
    assert kwargs["group_by"] == [{"Type": "DIMENSION", "Key": "SERVICE"}]

@pytest.mark.asyncio
async def test_detect_reports_aws_errors_as_400(client, auth_headers, aws_account):
    with patch(GET_COSTS, side_effect=ValueError("Failed to authenticate with AWS: denied")):
        response = await client.post(f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect", headers=auth_headers)

    assert response.status_code == 400
    assert "Failed to authenticate with AWS" in response.json()["detail"]

@pytest.mark.asyncio
async def test_unexpected_errors_do_not_leak_details(client, auth_headers, aws_account):
    with patch(GET_COSTS, side_effect=RuntimeError("secret internals")):
        response = await client.post(f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect", headers=auth_headers)

    assert response.status_code == 500
    assert "secret internals" not in response.text

@pytest.mark.asyncio
async def test_unknown_account_returns_404(client, auth_headers):
    detect = await client.post("/api/v1/costs/999999999999/anomalies/detect", headers=auth_headers)
    listing = await client.get("/api/v1/costs/999999999999/anomalies", headers=auth_headers)
    assert detect.status_code == 404
    assert listing.status_code == 404

@pytest.mark.asyncio
async def test_other_users_account_is_not_accessible(client, auth_headers, db_session):
    other = User(
        id=uuid.uuid4(), email="other@example.com", hashed_password=get_password_hash("x" * 10),
        is_active=True, is_superuser=False,
    )
    db_session.add(other)
    await db_session.commit()
    db_session.add(AWSaccount(
        id=uuid.uuid4(), user_id=other.id, aws_account_name="Other", aws_account_id="210987654321",
        role_arn="arn:aws:iam::210987654321:role/Other", external_id="ext-other",
    ))
    await db_session.commit()

    with patch(GET_COSTS, return_value=[]) as aws:
        detect = await client.post("/api/v1/costs/210987654321/anomalies/detect", headers=auth_headers)
    listing = await client.get("/api/v1/costs/210987654321/anomalies", headers=auth_headers)

    assert detect.status_code == 404
    assert listing.status_code == 404
    aws.assert_not_called()

@pytest.mark.asyncio
async def test_requires_authentication(client, aws_account):
    detect = await client.post(f"/api/v1/costs/{aws_account.aws_account_id}/anomalies/detect")
    listing = await client.get(f"/api/v1/costs/{aws_account.aws_account_id}/anomalies")
    assert detect.status_code == 401
    assert listing.status_code == 401