# Unit tests for core/gcp/quotas.py
# Validates parsing of Cloud Quotas API and Cloud Monitoring API responses with offline mocks.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from core.gcp.quotas import fetch_quota_limits, fetch_rate_usage


def test_fetch_quota_limits_success() -> None:
    """Verifies that quotaInfos payload is parsed into GCPQuotaInfo objects."""
    mock_payload = {
        "quotaInfos": [
            {
                "quotaId": "GenerateContentRequestsPerMinute",
                "quotaDisplayName": "Generate content requests per minute",
                "metric": "generativelanguage.googleapis.com/generate_content_requests",
                "service": "generativelanguage.googleapis.com",
                "isConcurrent": False,
                "quotaConfig": {
                    "preferredValue": "1000",
                    "grantedValue": "1000",
                },
            },
            {
                "quotaId": "GenerateContentTokensPerMinute",
                "quotaDisplayName": "Generate content tokens per minute",
                "metric": "generativelanguage.googleapis.com/generate_content_tokens",
                "quotaConfig": {
                    "grantedValue": "4000000",
                },
            },
        ]
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        quotas = asyncio.run(fetch_quota_limits(project_id="test-proj", access_token="test-token"))

        assert len(quotas) == 2
        assert quotas[0].metric_name == "Запитів/хв (RPM)"
        assert quotas[0].limit == 1000.0
        assert quotas[1].metric_name == "Токенів/хв (TPM)"
        assert quotas[1].limit == 4000000.0


def test_fetch_quota_limits_with_model_dimension() -> None:
    """Verifies that model dimensions are extracted and appended to the label."""
    mock_payload = {
        "quotaInfos": [
            {
                "quotaId": "GenerateContentRequestsPerDay",
                "dimensionsInfos": [
                    {
                        "dimensions": {"model": "models/gemini-1.5-pro"},
                        "details": {"value": "100"},
                    }
                ],
            }
        ]
    }
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        quotas = asyncio.run(fetch_quota_limits(project_id="test-proj", access_token="test-token"))
        assert len(quotas) == 1
        assert "gemini-1.5-pro" in quotas[0].metric_name
        assert quotas[0].limit == 100.0


def test_fetch_quota_limits_http_error() -> None:
    """Verifies that HTTP errors return an empty list without raising exceptions."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 403

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        quotas = asyncio.run(fetch_quota_limits(project_id="test-proj", access_token="test-token"))
        assert quotas == []


def test_fetch_rate_usage_success() -> None:
    """Verifies that Cloud Monitoring time-series payload extracts the latest rate data point."""
    mock_payload = {
        "timeSeries": [
            {
                "metric": {
                    "type": "serviceruntime.googleapis.com/quota/rate/net_usage",
                    "labels": {"quota_metric": "generativelanguage.googleapis.com/requests"},
                },
                "points": [
                    {
                        "interval": {"endTime": "2026-10-11T12:00:00Z"},
                        "value": {"doubleValue": 5.4},
                    }
                ],
            }
        ]
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_payload

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        usage = asyncio.run(fetch_rate_usage(project_id="test-proj", access_token="test-token"))

        assert usage is not None
        assert usage.current_rate_usage == 5.4
        assert usage.quota_metric == "generativelanguage.googleapis.com/requests"


def test_fetch_rate_usage_no_points() -> None:
    """Verifies that an empty timeSeries array returns None cleanly."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"timeSeries": []}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        usage = asyncio.run(fetch_rate_usage(project_id="test-proj", access_token="test-token"))
        assert usage is None
