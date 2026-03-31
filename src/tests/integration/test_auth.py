import pytest

@pytest.mark.asyncio
async def test_register_user(client):
    response = await client.post("/api/v1/register", json={
        "email": "testuser@example.com",
        "username": "testuser",
        "password": "testpassword"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "testuser@example.com"
    assert "id" in data
    assert "hashed_password" not in data

@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    response = await client.post("/api/v1/register", json={
        "email": "testuser@example.com",
        "username": "anotheruser",
        "password": "testpassword"
    })
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_register_invalid_email(client):
    response = await client.post("/api/v1/register", json={
        "email": "invalid-email",
        "username": "testuser2",
        "password": "testpassword"
    })
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_register_short_password(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "test2@example.com",
        "full_name": "Test",
        "password": "short"
    })
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_register_missing_fields(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "test2@example.com",
        "full_name": "Test"
    })
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_register_empty_fields(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "",
        "full_name": "",
        "password": ""
    })
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_login_user(client):
    response = await client.post("/api/v1/auth/login", json={
        "email": "testuser@example.com",
        "password": "testpassword"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    response = await client.post("/api/v1/auth/login", json={
        "email": "testuser@example.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    response = await client.post("/api/v1/auth/login", json={
        "email": "lK2bG@example.com",
        "password": "testpassword"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_login_inactive_user(client, inactive_user):
    response = await client.post("/api/v1/auth/login", data={
        "username": "inactive@example.com",
        "password": "password123"
    })
    assert response.status_code == 400