# Unit tests for core/gcp/__init__.py
# Validates orchestrator execution, concurrent gathering, and graceful error handling.
import asyncio
from unittest.mock import AsyncMock, patch
import pytest

from core.gcp import (
    GCPBillingInfo,
    GCPQuotaInfo,
    GCPTelemetryReport,
    GCPUsageMetrics,
    get_gcp_telemetry,
)


def test_get_gcp_telemetry_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that missing project or credentials immediately returns unavailable report."""
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GCP_SERVICE_ACCOUNT_FILE", raising=False)

    report = asyncio.run(get_gcp_telemetry())
    assert report.is_available is False
    assert report.quotas == []
    assert report.billing is None


def test_get_gcp_telemetry_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that failed OAuth token acquisition returns unavailable report."""
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_FILE", "fake.json")

    with patch("core.gcp.auth.get_gcp_access_token", return_value=None):
        report = asyncio.run(get_gcp_telemetry())
        assert report.is_available is False
        assert "Authentication failed" in (report.error_message or "")


def test_get_gcp_telemetry_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that all three GCP data streams are gathered concurrently and aggregated."""
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project")
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_FILE", "fake.json")
    monkeypatch.setenv("GCP_BILLING_TABLE", "test-project.dataset.table")

    mock_quotas = [GCPQuotaInfo(metric_name="RPM", limit=1000.0, unit="1/min")]
    mock_usage = GCPUsageMetrics(current_rate_usage=1.5, quota_metric="reqs")
    mock_billing = GCPBillingInfo(cost_usd=0.08, currency="USD", status="synced")

    with patch("core.gcp.auth.get_gcp_access_token", return_value="valid-token"):
        with patch("core.gcp.quotas.fetch_quota_limits", new_callable=AsyncMock) as m_quotas:
            with patch("core.gcp.quotas.fetch_rate_usage", new_callable=AsyncMock) as m_usage:
                with patch("core.gcp.billing.fetch_month_to_date_spend", new_callable=AsyncMock) as m_billing:
                    m_quotas.return_value = mock_quotas
                    m_usage.return_value = mock_usage
                    m_billing.return_value = mock_billing

                    report = asyncio.run(get_gcp_telemetry())

                    assert report.is_available is True
                    assert len(report.quotas) == 1
                    assert report.usage.current_rate_usage == 1.5
                    assert report.billing.cost_usd == 0.08
                    assert report.billing.status == "synced"
