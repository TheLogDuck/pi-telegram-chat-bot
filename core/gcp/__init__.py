# Google Cloud Platform telemetry and FinOps integration package.
# Exposes typed data models and a unified async orchestrator for bot commands and Mini Apps.
import asyncio
import os
from typing import Optional
import httpx
from core.logger import setup_logger

from . import auth, billing, quotas
from .models import (
    GCPBillingInfo,
    GCPQuotaInfo,
    GCPTelemetryReport,
    GCPUsageMetrics,
)

logger = setup_logger("gcp")

# Re-export key functions for external consumers
get_gcp_access_token = auth.get_gcp_access_token
fetch_quota_limits = quotas.fetch_quota_limits
fetch_rate_usage = quotas.fetch_rate_usage
fetch_month_to_date_spend = billing.fetch_month_to_date_spend

__all__ = [
    "GCPQuotaInfo",
    "GCPUsageMetrics",
    "GCPBillingInfo",
    "GCPTelemetryReport",
    "get_gcp_access_token",
    "fetch_quota_limits",
    "fetch_rate_usage",
    "fetch_month_to_date_spend",
    "get_gcp_telemetry",
]


async def get_gcp_telemetry(
    project_id: Optional[str] = None,
    service_account_path: Optional[str] = None,
    billing_table: Optional[str] = None,
) -> GCPTelemetryReport:
    """Orchestrates concurrent fetching of Google Cloud quotas, usage, and billing data.

    Returns:
        GCPTelemetryReport: Consolidated report with server-side metrics.
    """
    proj_id = project_id or os.getenv("GCP_PROJECT_ID")
    key_path = service_account_path or os.getenv("GCP_SERVICE_ACCOUNT_FILE")
    tbl_name = billing_table or os.getenv("GCP_BILLING_TABLE", "")

    # Fast fallback if GCP integration is not configured
    if not proj_id or not key_path:
        return GCPTelemetryReport(is_available=False)

    token = auth.get_gcp_access_token(key_path)
    if not token:
        return GCPTelemetryReport(
            is_available=False,
            error_message="Authentication failed: Unable to acquire GCP OAuth2 token.",
        )

    # Use a single shared async HTTP client for all concurrent requests
    async with httpx.AsyncClient() as client:
        # Launch Quotas, Monitoring, and BigQuery calls concurrently
        quotas_task = quotas.fetch_quota_limits(proj_id, token, client)
        usage_task = quotas.fetch_rate_usage(proj_id, token, client)
        billing_task = billing.fetch_month_to_date_spend(proj_id, tbl_name, token, client)

        fetched_quotas, fetched_usage, fetched_billing = await asyncio.gather(
            quotas_task,
            usage_task,
            billing_task,
        )

    return GCPTelemetryReport(
        is_available=True,
        quotas=fetched_quotas,
        usage=fetched_usage,
        billing=fetched_billing,
    )
