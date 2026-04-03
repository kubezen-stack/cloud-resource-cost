import uuid
import pytest
import httpx
import os

BASE_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1"
TIMEOUT = 10

_uid = str(uuid.uuid4())[:8]
TEST_EMAIL = f"smoke_{_uid}@test.com"
TEST_PASSWORD = "smokepassword123"

@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as c:
        yield c

@pytest.fixture(scope="module")
def auth_token(client):
    # register
    r = client.post(f"{API}/auth/register", json={
        "email": TEST_EMAIL,
        "full_name": "Smoke Test User",
        "password": TEST_PASSWORD,
    })
    assert r.status_code == 201, f"Register failed: {r.text}"

    # login
    r = client.post(f"{API}/auth/login", data={
        "username": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def aws_account_id(client, auth_headers):
    r = client.post(f"{API}/aws_accounts/", headers=auth_headers, json={
        "aws_account_name": "Smoke Test Account",
        "aws_account_id": "123456789012",
        "role_arn": f"arn:aws:iam::123456789012:role/SmokeRole-{_uid}",
    })
    assert r.status_code == 201, f"Create AWS account failed: {r.text}"
    return r.json()["id"]


# ---------------------------------------------------------------------------
# 1. Health
# ---------------------------------------------------------------------------

def test_health_returns_200(client):
    r = client.get(f"{API}/health/health")
    assert r.status_code == 200


def test_health_status_is_healthy(client):
    r = client.get(f"{API}/health/health")
    assert r.json()["status"] == "healthy"


def test_health_has_environment(client):
    r = client.get(f"{API}/health/health")
    assert "environment" in r.json()


def test_health_database_is_healthy(client):
    r = client.get(f"{API}/health/health")
    assert r.json()["database"] == "healthy"


def test_readiness_returns_200(client):
    r = client.get(f"{API}/health/ready")
    assert r.status_code == 200


def test_readiness_status_is_ready(client):
    r = client.get(f"{API}/health/ready")
    assert r.json()["status"] == "ready"


def test_readiness_database_check(client):
    r = client.get(f"{API}/health/ready")
    assert r.json()["checks"]["database"] == "ready"


# ---------------------------------------------------------------------------
# 2. OpenAPI
# ---------------------------------------------------------------------------

def test_openapi_json_available(client):
    r = client.get(f"{API}/openapi.json")
    assert r.status_code == 200


def test_openapi_has_paths(client):
    r = client.get(f"{API}/openapi.json")
    assert "paths" in r.json()


def test_openapi_has_required_routes(client):
    paths = client.get(f"{API}/openapi.json").json()["paths"]
    required = [
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/users/me",
        "/api/v1/aws_accounts/",
        "/api/v1/health/health",
        "/api/v1/health/ready",
    ]
    for route in required:
        assert route in paths, f"Route {route} відсутній в OpenAPI spec"


# ---------------------------------------------------------------------------
# 3. Auth
# ---------------------------------------------------------------------------

def test_register_endpoint_exists(client):
    r = client.post(f"{API}/auth/register", json={})
    assert r.status_code in (400, 422)


def test_login_endpoint_exists(client):
    r = client.post(f"{API}/auth/login", data={})
    assert r.status_code in (400, 422)


def test_register_with_valid_data(client):
    unique = str(uuid.uuid4())[:8]
    r = client.post(f"{API}/auth/register", json={
        "email": f"smoke_check_{unique}@test.com",
        "full_name": "Check User",
        "password": "checkpassword123",
    })
    assert r.status_code == 201
    data = r.json()
    assert "id" in data
    assert "email" in data
    assert "password" not in data
    assert "hashed_password" not in data


def test_login_returns_token(auth_token):
    assert auth_token is not None
    assert len(auth_token) > 0


def test_login_wrong_password_returns_401(client):
    r = client.post(f"{API}/auth/login", data={
        "username": TEST_EMAIL,
        "password": "wrongpassword",
    })
    assert r.status_code == 401


def test_login_unknown_user_returns_401(client):
    r = client.post(f"{API}/auth/login", data={
        "username": "nobody@test.com",
        "password": "password123",
    })
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 4. Auth middleware
# ---------------------------------------------------------------------------

def test_users_me_requires_auth(client):
    r = client.get(f"{API}/users/me")
    assert r.status_code == 401


def test_aws_accounts_requires_auth(client):
    r = client.get(f"{API}/aws_accounts/")
    assert r.status_code == 401


def test_costs_requires_auth(client):
    r = client.get(f"{API}/costs/{uuid.uuid4()}/costs")
    assert r.status_code == 401


def test_invalid_token_returns_403(client):
    r = client.get(
        f"{API}/users/me",
        headers={"Authorization": "Bearer invalidtoken"}
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 5. Users
# ---------------------------------------------------------------------------

def test_get_current_user(client, auth_headers):
    r = client.get(f"{API}/users/me", headers=auth_headers)
    assert r.status_code == 200


def test_current_user_has_correct_email(client, auth_headers):
    r = client.get(f"{API}/users/me", headers=auth_headers)
    assert r.json()["email"] == TEST_EMAIL


def test_current_user_response_shape(client, auth_headers):
    r = client.get(f"{API}/users/me", headers=auth_headers)
    data = r.json()
    for field in ["id", "email", "is_active", "created_at"]:
        assert field in data, f"Поле {field} відсутнє у відповіді /users/me"


def test_update_user_full_name(client, auth_headers):
    r = client.put(f"{API}/users/me", headers=auth_headers, json={
        "full_name": "Updated Smoke Name"
    })
    assert r.status_code == 200
    assert r.json()["full_name"] == "Updated Smoke Name"


# ---------------------------------------------------------------------------
# 6. AWS Accounts
# ---------------------------------------------------------------------------

def test_get_accounts_returns_list(client, auth_headers):
    r = client.get(f"{API}/aws_accounts/", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_created_account_in_list(client, auth_headers, aws_account_id):
    r = client.get(f"{API}/aws_accounts/", headers=auth_headers)
    ids = [acc["id"] for acc in r.json()]
    assert aws_account_id in ids


def test_get_account_by_id(client, auth_headers, aws_account_id):
    r = client.get(f"{API}/aws_accounts/{aws_account_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == aws_account_id


def test_account_response_shape(client, auth_headers, aws_account_id):
    r = client.get(f"{API}/aws_accounts/{aws_account_id}", headers=auth_headers)
    data = r.json()
    for field in ["id", "user_id", "aws_account_name", "aws_account_id",
                  "role_arn", "external_id", "is_active", "created_at"]:
        assert field in data, f"Поле {field} відсутнє у відповіді aws_accounts"


def test_get_nonexistent_account_returns_404(client, auth_headers):
    r = client.get(f"{API}/aws_accounts/{uuid.uuid4()}", headers=auth_headers)
    assert r.status_code == 404


def test_duplicate_role_arn_returns_400(client, auth_headers):
    r = client.post(f"{API}/aws_accounts/", headers=auth_headers, json={
        "aws_account_name": "Duplicate",
        "aws_account_id": "123456789012",
        "role_arn": f"arn:aws:iam::123456789012:role/SmokeRole-{_uid}",
    })
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 7. Costs — check availability of endpoints and basic auth, without validating actual cost data
# ---------------------------------------------------------------------------

def test_costs_endpoint_exists(client, auth_headers, aws_account_id):
    r = client.get(f"{API}/costs/{aws_account_id}/costs", headers=auth_headers)
    assert r.status_code != 404
    assert r.status_code != 401


def test_forecast_endpoint_exists(client, auth_headers, aws_account_id):
    r = client.get(f"{API}/costs/{aws_account_id}/forecast", headers=auth_headers)
    assert r.status_code != 404
    assert r.status_code != 401


def test_breakdown_endpoint_exists(client, auth_headers, aws_account_id):
    r = client.get(f"{API}/costs/{aws_account_id}/breakdown", headers=auth_headers)
    assert r.status_code != 404
    assert r.status_code != 401


def test_costs_unknown_account_returns_404(client, auth_headers):
    r = client.get(f"{API}/costs/{uuid.uuid4()}/costs", headers=auth_headers)
    assert r.status_code == 404


def test_forecast_unknown_account_returns_404(client, auth_headers):
    r = client.get(f"{API}/costs/{uuid.uuid4()}/forecast", headers=auth_headers)
    assert r.status_code == 404


def test_breakdown_unknown_account_returns_404(client, auth_headers):
    r = client.get(f"{API}/costs/{uuid.uuid4()}/breakdown", headers=auth_headers)
    assert r.status_code == 404