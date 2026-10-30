import pytest
import pytest_asyncio
import uuid
from unittest.mock import patch
from app.models.aws_account import AWSaccount


VALID_ACCOUNT = {
    "aws_account_name": "My AWS Account",
    "aws_account_id": "123456789012",
    "role_arn": "arn:aws:iam::123456789012:role/MyRole"
}


@pytest_asyncio.fixture
async def external_id(client, auth_headers):
    response = await client.get("/api/v1/aws_accounts/external-id", headers=auth_headers)
    assert response.status_code == 200
    return response.json()["external_id"]


@pytest.fixture
def role_is_valid():
    with patch("app.api.v1.aws_accounts.validate_aws_role", return_value=(True, None)) as mocked:
        yield mocked


@pytest.mark.asyncio
async def test_create_aws_account(client, auth_headers, external_id, role_is_valid):
    response = await client.post("/api/v1/aws_accounts/", headers=auth_headers, json=VALID_ACCOUNT)
    assert response.status_code == 201
    data = response.json()
    assert data["aws_account_name"] == "My AWS Account"
    assert data["aws_account_id"] == "123456789012"
    assert data["external_id"] == external_id
    assert "id" in data
    role_is_valid.assert_called_once_with(VALID_ACCOUNT["role_arn"], external_id)


@pytest.mark.asyncio
async def test_create_aws_account_requires_external_id(client, auth_headers, role_is_valid):
    response = await client.post("/api/v1/aws_accounts/", headers=auth_headers, json=VALID_ACCOUNT)
    assert response.status_code == 400
    assert "external-id" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_aws_account_role_cannot_be_assumed(client, auth_headers, external_id):
    with patch("app.api.v1.aws_accounts.validate_aws_role", return_value=(False, "AccessDenied")):
        response = await client.post("/api/v1/aws_accounts/", headers=auth_headers, json=VALID_ACCOUNT)
    assert response.status_code == 400
    assert "Cannot assume role" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_aws_account_unauthorized(client):
    response = await client.post("/api/v1/aws_accounts/", json=VALID_ACCOUNT)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_duplicate_role_arn(client, auth_headers, external_id, role_is_valid):
    first = await client.post("/api/v1/aws_accounts/", headers=auth_headers, json=VALID_ACCOUNT)
    assert first.status_code == 201
    response = await client.post("/api/v1/aws_accounts/", headers=auth_headers, json=VALID_ACCOUNT)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_aws_accounts_empty(client, auth_headers):
    response = await client.get("/api/v1/aws_accounts/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_aws_accounts(client, auth_headers, test_user, db_session):
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

    response = await client.get("/api/v1/aws_accounts/", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_aws_account_by_id(client, auth_headers, test_user, db_session):
    account_id = uuid.uuid4()
    account = AWSaccount(
        id=account_id,
        user_id=test_user.id,
        aws_account_name="Test Account",
        aws_account_id="123456789012",
        role_arn="arn:aws:iam::123456789012:role/TestRole",
        external_id="ext-123"
    )
    db_session.add(account)
    await db_session.commit()

    response = await client.get(f"/api/v1/aws_accounts/{account_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(account_id)


@pytest.mark.asyncio
async def test_get_aws_account_not_found(client, auth_headers):
    response = await client.get(f"/api/v1/aws_accounts/{uuid.uuid4()}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_other_user_account(client, auth_headers, db_session):
    other_user_id = uuid.uuid4()
    account = AWSaccount(
        id=uuid.uuid4(),
        user_id=other_user_id,
        aws_account_name="Other Account",
        aws_account_id="999999999999",
        role_arn="arn:aws:iam::999999999999:role/OtherRole",
        external_id="ext-999"
    )
    db_session.add(account)
    await db_session.commit()

    response = await client.get(f"/api/v1/aws_accounts/{account.id}", headers=auth_headers)
    assert response.status_code == 404