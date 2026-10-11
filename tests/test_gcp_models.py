# Unit tests for core/gcp/models.py
# Validates data models and their JSON-serializable dictionary outputs for Telegram Mini Apps.
from core.gcp.models import (
    GCPQuotaInfo,
    GCPUsageMetrics,
    GCPBillingInfo,
    GCPTelemetryReport,
)


def test_gcp_quota_info_to_dict() -> None:
    """Verifies that GCPQuotaInfo serializes cleanly to a dictionary."""
    quota = GCPQuotaInfo(
        metric_name="GenerateContentRequestsPerMinute",
        limit=1000.0,
        unit="1/min",
    )
    data = quota.to_dict()
    assert data == {
        "metric_name": "GenerateContentRequestsPerMinute",
        "limit": 1000.0,
        "unit": "1/min",
    }


def test_gcp_usage_metrics_to_dict() -> None:
    """Verifies that GCPUsageMetrics serializes cleanly to a dictionary."""
    usage = GCPUsageMetrics(
        current_rate_usage=4.2,
        quota_metric="generativelanguage.googleapis.com/requests",
    )
    data = usage.to_dict()
    assert data == {
        "current_rate_usage": 4.2,
        "quota_metric": "generativelanguage.googleapis.com/requests",
    }


def test_gcp_billing_info_to_dict() -> None:
    """Verifies that GCPBillingInfo serializes cleanly to a dictionary."""
    billing = GCPBillingInfo(
        cost_usd=0.15,
        currency="USD",
        status="synced",
    )
    data = billing.to_dict()
    assert data == {
        "cost_usd": 0.15,
        "currency": "USD",
        "status": "synced",
    }


def test_gcp_telemetry_report_to_dict() -> None:
    """Verifies that the full telemetry report aggregates nested objects properly."""
    quota = GCPQuotaInfo(metric_name="RPM", limit=1000.0, unit="1/min")
    usage = GCPUsageMetrics(current_rate_usage=2.0, quota_metric="reqs")
    billing = GCPBillingInfo(cost_usd=0.05, currency="USD", status="synced")

    report = GCPTelemetryReport(
        is_available=True,
        quotas=[quota],
        usage=usage,
        billing=billing,
        error_message=None,
    )
    data = report.to_dict()

    assert data["is_available"] is True
    assert len(data["quotas"]) == 1
    assert data["quotas"][0]["metric_name"] == "RPM"
    assert data["usage"]["current_rate_usage"] == 2.0
    assert data["billing"]["cost_usd"] == 0.05
    assert data["error_message"] is None
