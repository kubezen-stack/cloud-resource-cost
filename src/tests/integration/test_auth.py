import pytest

@pytest.mark.asyncio
async def test_register_user(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "testuser@example.com",
        "username": "testuser",
        "password": "testpassword"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "testuser@example.com"

@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {
        "email": "duplicate@example.com",
        "username": "user1",
        "password": "password123"
    }

    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_register_invalid_email(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "invalid-email",
        "username": "testuser2",
        "password": "testpassword"
    })
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_register_short_password(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "test2@example.com",
        "username": "Test",
        "password": "123"
    })
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_register_missing_fields(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "test2@example.com",
        "username": "Test"
    })
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_register_empty_fields(client):
    response = await client.post("/api/v1/auth/register", json={
        "email": "",
        "username": "",
        "password": ""
    })
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_login_user(client):
    email = "login_test@example.com"
    password = "testpassword"

    await client.post("/api/v1/auth/register", json={
        "email": email,
        "username": "login_test",
        "password": password
    })
    
    response = await client.post("/api/v1/auth/login", data={
        "username": email, 
        "password": password
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    email = "wrong_pass@example.com"
    await client.post("/api/v1/auth/register", json={
        "email": email,
        "username": "wrong_pass",
        "password": "correct_password"
    })
    
    response = await client.post("/api/v1/auth/login", data={
        "username": email,
        "password": "incorrect_password"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    response = await client.post("/api/v1/auth/login", data={
        "username": "no-one@example.com",
        "password": "password123"
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_login_inactive_user(client, inactive_user):
    response = await client.post("/api/v1/auth/login", data={
        "username": "inactive@example.com",
        "password": "password123"
    })
    assert response.status_code == 400