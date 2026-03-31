import pytest
from app.models.user import User
from app.core.security import get_password_hash
import uuid

@pytest.mark.asyncio
async def test_get_current_user(client, auth_headers):
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"

@pytest.mark.asyncio
async def test_get_current_user_unauthorized(client):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_update_user_full_name(client, auth_headers):
    response = await client.put("/api/v1/users/me", headers=auth_headers, json={
        "full_name": "Updated Name"
    })
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"

@pytest.mark.asyncio
async def test_update_user_email(client, auth_headers):
    response = await client.put("/api/v1/users/me", headers=auth_headers, json={
        "email": "newemail@example.com"
    })
    assert response.status_code == 200
    assert response.json()["email"] == "newemail@example.com"

@pytest.mark.asyncio
async def test_update_user_duplicate_email(client, auth_headers, db_session):
    other_user = User(
        id=uuid.uuid4(),
        email="other@example.com",
        hashed_password=get_password_hash("password123"),
        is_active=True
    )
    db_session.add(other_user)
    await db_session.commit()

    response = await client.put("/api/v1/users/me", headers=auth_headers, json={
        "email": "other@example.com"
    })
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_update_user_password(client, auth_headers):
    response = await client.put("/api/v1/users/me", headers=auth_headers, json={
        "password": "newpassword123"
    })
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_delete_user(client, auth_headers):
    response = await client.delete("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 204

    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code in [401, 404]