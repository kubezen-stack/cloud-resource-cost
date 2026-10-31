import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy import select
from app.jobs.detect_anomalies import run
from app.models.aws_account import AWSaccount
from app.models.cost_anomaly import CostAnomaly
from tests.conftest import TestSessionLocal

GET_COSTS = "app.services.cost_service.AWSCostService.get_cost_and_usage"


def _spiky_results(days=60, spike_index=50):
    rng = np.random.default_rng(0)
    ec2 = list(50 + rng.normal(0, 2, days))
    ec2[spike_index] = 170.0
    first = datetime.utcnow().date() - timedelta(days=days)
    return [
        {
            "TimePeriod": {"Start": (first + timedelta(days=i)).isoformat()},
            "Groups": [{"Keys": ["Amazon EC2"], "Metrics": {"UnblendedCost": {"Amount": str(round(ec2[i], 4))}}}],
        }
        for i in range(days)
    ]


async def _add_account(db, user, number, active=True):
    account = AWSaccount(
        id=uuid.uuid4(),
        user_id=user.id,
        aws_account_name=f"Account {number}",
        aws_account_id=number,
        role_arn=f"arn:aws:iam::{number}:role/Role",
        external_id="ext",
        is_active=active,
    )
    db.add(account)
    await db.commit()
    return account


@pytest_asyncio.fixture
async def two_active_one_inactive(test_user, db_session):
    a = await _add_account(db_session, test_user, "111111111111")
    b = await _add_account(db_session, test_user, "222222222222")
    await _add_account(db_session, test_user, "333333333333", active=False)
    return a, b


async def _stored(db):
    return (await db.execute(select(CostAnomaly))).scalars().all()


@pytest.mark.asyncio
async def test_job_processes_only_active_accounts(two_active_one_inactive, db_session):
    with patch(GET_COSTS, return_value=_spiky_results()) as aws:
        failures = await run(90, session_factory=TestSessionLocal)

    assert failures == 0
    assert aws.call_count == 2
    rows = await _stored(db_session)
    assert {r.aws_account_id for r in rows} == {a.id for a in two_active_one_inactive}
    assert all(r.service_name == "Amazon EC2" for r in rows)


@pytest.mark.asyncio
async def test_job_is_idempotent(two_active_one_inactive, db_session):
    with patch(GET_COSTS, return_value=_spiky_results()):
        await run(90, session_factory=TestSessionLocal)
        await run(90, session_factory=TestSessionLocal)

    assert len(await _stored(db_session)) == 2


@pytest.mark.asyncio
async def test_job_continues_after_a_failing_account(two_active_one_inactive, db_session):
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("Failed to authenticate with AWS: denied")
        return _spiky_results()

    with patch(GET_COSTS, side_effect=flaky):
        failures = await run(90, session_factory=TestSessionLocal)

    assert failures == 1
    assert len(await _stored(db_session)) == 1


@pytest.mark.asyncio
async def test_job_with_no_accounts_is_a_noop(db_session):
    with patch(GET_COSTS) as aws:
        failures = await run(90, session_factory=TestSessionLocal)

    assert failures == 0
    aws.assert_not_called()
