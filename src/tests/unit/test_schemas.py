import pytest
import uuid
from pydantic import ValidationError
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.aws_accounts import AWSCreateAccount
from datetime import datetime

class TestUserCreate:
    def test_valid_user_create(self):
        user_data = UserCreate(
            email="test@example.com",
            full_name="Test User",
            password="strongpassword"
        )
        assert user_data.email == "test@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserCreate(
                email="invalid-email",
                full_name="Test User",
                password="strongpassword"
            )

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            UserCreate(
                email="test@example.com",
                full_name="Test User",
                password="weak"
            )
    
    def test_password_too_long(self):
        with pytest.raises(ValidationError):
            UserCreate(
                email="test@example.com",
                full_name="Test User",
                password="a" * 73
            )

    def test_whitespace_stripping(self):
        user_data = UserCreate(
            email="  test@example.com  ",
            full_name="  Test User  ",
            password="strongpassword"
        )
        assert user_data.email == "test@example.com"


class TestUserUpdate:
    def test_all_fields_optional(self):
        user_data = UserUpdate()
        assert user_data.email is None
        assert user_data.full_name is None
        assert user_data.password is None

    def test_valid_user_update(self):
        update = UserUpdate(full_name="Updated User")
        assert update.full_name == "Updated User"
        assert update.email is None

class TestAWSCreateAccount:
    def test_valid_aws_account(self):
        account_data = AWSCreateAccount(
            aws_account_name="Test Account",
            aws_account_id="123456789012",
            role_arn="arn:aws:iam::123456789012:role/TestRole"
        )
        assert account_data.aws_account_name == "Test Account"

    def test_invalid_aws_account_id(self):
        with pytest.raises(ValidationError):
            AWSCreateAccount(
                aws_account_name="Test Account",
                aws_account_id="invalid-id",
                role_arn="arn:aws:iam::123456789012:role/TestRole"
            )

    def test_invalid_role_arn(self):
        with pytest.raises(ValidationError):
            AWSCreateAccount(
                aws_account_name="Test Account",
                aws_account_id="123456789012",
                role_arn="invalid-arn"
            )

    def test_account_name_too_short(self):
        with pytest.raises(ValidationError):
            AWSCreateAccount(
                aws_account_name="ab",
                aws_account_id="123456789012",
                role_arn="arn:aws:iam::123456789012:role/TestRole"
            )