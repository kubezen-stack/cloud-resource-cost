import pytest
from datetime import timedelta
from app.core.security import verify_password, get_password_hash, create_access_token
import jwt
from app.core.config import settings

def test_password_hashing():
    password = "mysecretpassword"
    hashed_password = get_password_hash(password)
    assert hashed_password != password
    assert len(hashed_password) > 0

def test_password_verification():
    password = "mysecretpassword"
    hashed_password = get_password_hash(password)
    assert verify_password(password, hashed_password) == True

def test_verify_password_wrong():
    password = "mysecretpassword"
    wrong_password = "wrongpassword"
    hashed_password = get_password_hash(password)
    assert verify_password(wrong_password, hashed_password) == False

def test_access_token_creation():
    data = {"sub": "testuser"}
    access_token = create_access_token(data=data, expires_delta=timedelta(minutes=15))
    assert access_token is not None
    decoded_token = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert decoded_token["sub"] == "testuser"

def test_access_token_expiration():
    data = {"sub": "testuser"}
    access_token = create_access_token(data=data, expires_delta=timedelta(minutes=5))
    payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "testuser"