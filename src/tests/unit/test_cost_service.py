import pytest
from unittest.mock import MagicMock, patch
from app.services.cost_service import AWSCostService


@pytest.fixture
def cost_service():
    return AWSCostService(
        role_arn="arn:aws:iam::123456789012:role/TestRole",
        external_id="TestExternalId"
    )


class TestGetCredentials:
    def test_assumes_role_successfully(self, cost_service):
        mock_response = {
            "Credentials": {
                "AccessKeyId": "AKID",
                "SecretAccessKey": "SECRET",
                "SessionToken": "TOKEN"
            }
        }
        with patch("boto3.client") as mock_boto:
            mock_sts = MagicMock()
            mock_sts.assume_role.return_value = mock_response
            mock_boto.return_value = mock_sts

            creds = cost_service._get_credentials()
            assert creds["AccessKeyId"] == "AKID"

    def test_raises_on_failure(self, cost_service):
        with patch("boto3.client") as mock_boto:
            mock_sts = MagicMock()
            mock_sts.assume_role.side_effect = Exception("Access denied")
            mock_boto.return_value = mock_sts

            with pytest.raises(ValueError, match="Failed to authenticate with AWS"):
                cost_service._get_credentials()


class TestGetCostAndUsage:
    def test_returns_results(self, cost_service):
        mock_credentials = {
            "AccessKeyId": "AKID",
            "SecretAccessKey": "SECRET",
            "SessionToken": "TOKEN"
        }

        with patch.object(cost_service, "_get_credentials", return_value=mock_credentials):
            with patch("boto3.client") as mock_boto:
                mock_ce = MagicMock()
                mock_ce.get_cost_and_usage.side_effect = Exception("API Error")
                mock_boto.return_value = mock_ce

                with pytest.raises(ValueError, match="Failed to fetch AWS costs"):
                    cost_service.get_cost_and_usage("2024-01-01", "2024-01-31")

    def test_raises_on_api_error(self, cost_service):
        with patch("boto3.client") as mock_boto:
            mock_sts = MagicMock()
            mock_sts.assume_role.side_effect = Exception("Access denied")
            mock_boto.return_value = mock_sts

            with pytest.raises(ValueError, match="Failed to authenticate with AWS"):
                cost_service._get_credentials()


class TestGetCostForecast:
    def test_returns_forecast(self, cost_service):
        mock_credentials = {
            "AccessKeyId": "AKID",
            "SecretAccessKey": "SECRET",
            "SessionToken": "TOKEN"
        }
        mock_forecast = [{"TimePeriod": {"Start": "2024-02-01", "End": "2024-03-01"}, "MeanValue": "100.00"}]

        with patch.object(cost_service, "_get_credentials", return_value=mock_credentials):
            with patch("boto3.client") as mock_boto:
                mock_ce = MagicMock()
                mock_ce.get_cost_forecast.return_value = {"ForecastResultsByTime": mock_forecast}
                mock_boto.return_value = mock_ce

                result = cost_service.get_cost_forecast("2024-02-01", "2024-05-01")
                assert result == mock_forecast