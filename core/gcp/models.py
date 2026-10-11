# Domain data models for Google Cloud Platform telemetry.
# Designed for clean serialization to JSON dictionaries for Telegram Mini Apps.
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GCPQuotaInfo:
    """Represents an official server-side quota limit from the Cloud Quotas API."""
    metric_name: str
    limit: float
    unit: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializes quota limit info into a dictionary for JSON output."""
        return {
            "metric_name": self.metric_name,
            "limit": self.limit,
            "unit": self.unit,
        }


@dataclass
class GCPUsageMetrics:
    """Represents actual server-side usage from the Cloud Monitoring API."""
    current_rate_usage: float
    quota_metric: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializes real-time usage metrics into a dictionary for JSON output."""
        return {
            "current_rate_usage": self.current_rate_usage,
            "quota_metric": self.quota_metric,
        }


@dataclass
class GCPBillingInfo:
    """Represents invoiced cost data queried from BigQuery Billing Export."""
    cost_usd: float
    currency: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializes financial billing data into a dictionary for JSON output."""
        return {
            "cost_usd": self.cost_usd,
            "currency": self.currency,
            "status": self.status,
        }


@dataclass
class GCPTelemetryReport:
    """Consolidated telemetry report containing quotas, live usage, and spend."""
    is_available: bool
    quotas: List[GCPQuotaInfo] = field(default_factory=list)
    usage: Optional[GCPUsageMetrics] = None
    billing: Optional[GCPBillingInfo] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the complete report, including nested objects, into a dictionary."""
        return {
            "is_available": self.is_available,
            "quotas": [q.to_dict() for q in self.quotas],
            "usage": self.usage.to_dict() if self.usage else None,
            "billing": self.billing.to_dict() if self.billing else None,
            "error_message": self.error_message,
        }
