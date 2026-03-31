import pytest

@pytest.mark.integration
async def test_health_check(client):
    response = await client.get("/api/v1/health/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "healthy"

@pytest.mark.integration
async def test_readiness_check(client):
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ready"
