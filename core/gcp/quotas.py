# Quotas and Monitoring module: queries Google Cloud Quotas and Monitoring APIs.
# Fetches official server-side limits and real-time net rate quota usage.
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import httpx
from core.logger import setup_logger
from .models import GCPQuotaInfo, GCPUsageMetrics

logger = setup_logger("gcp.quotas")

CLOUD_QUOTAS_URL = (
    "https://cloudquotas.googleapis.com/v1/projects/{project_id}/locations/global"
    "/services/generativelanguage.googleapis.com/quotaInfos"
)
CLOUD_MONITORING_URL = "https://monitoring.googleapis.com/v3/projects/{project_id}/timeSeries"


def _format_quota_display_name(raw_name: str) -> str:
    """Formats technical quota identifiers into clean, user-friendly labels."""
    lower = raw_name.lower().replace("_", "")
    if "requestsperminute" in lower:
        return "Запитів/хв (RPM)"
    if "tokensperminute" in lower:
        return "Токенів/хв (TPM)"
    if "requestsperday" in lower:
        return "Запитів/день (RPD)"
    return raw_name


async def fetch_quota_limits(
    project_id: str,
    access_token: str,
    client: Optional[httpx.AsyncClient] = None,
) -> List[GCPQuotaInfo]:
    """Retrieves official configured quota limits for Gemini (generativelanguage.googleapis.com)."""
    url = CLOUD_QUOTAS_URL.format(project_id=project_id)
    headers = {"Authorization": f"Bearer {access_token}"}

    async def _do_fetch(http_client: httpx.AsyncClient) -> List[GCPQuotaInfo]:
        try:
            resp = await http_client.get(url, headers=headers, timeout=5.0)
            if resp.status_code != 200:
                logger.warning(f"Cloud Quotas API returned status {resp.status_code}")
                return []

            data = resp.json()
            results: List[GCPQuotaInfo] = []
            seen_categories = set()

            for item in data.get("quotaInfos", []):
                metric_name = item.get("quotaId") or item.get("metric", "Unknown")
                clean_key = metric_name.lower().replace("_", "")

                # Filter strictly for primary rate limits to prevent message overflow
                is_rpm = "requestsperminute" in clean_key
                is_tpm = "tokensperminute" in clean_key
                is_rpd = "requestsperday" in clean_key

                if not (is_rpm or is_tpm or is_rpd):
                    continue

                category = "rpm" if is_rpm else ("tpm" if is_tpm else "rpd")
                if category in seen_categories:
                    continue
                seen_categories.add(category)

                # Extract limit value and optional model dimension
                limit_val = 0.0
                model_name = ""
                dim_infos = item.get("dimensionsInfos", [])
                if dim_infos:
                    dim_map = dim_infos[0].get("dimensions", {})
                    raw_model = dim_map.get("model", "")
                    if raw_model:
                        model_name = raw_model.replace("models/", "")
                    details = dim_infos[0].get("details", {})
                    if "value" in details:
                        try:
                            limit_val = float(details["value"])
                        except (ValueError, TypeError):
                            limit_val = 0.0

                if limit_val == 0.0:
                    config = item.get("quotaConfig", {})
                    limit_val_str = config.get("grantedValue") or config.get("preferredValue") or "0"
                    try:
                        limit_val = float(limit_val_str)
                    except (ValueError, TypeError):
                        limit_val = 0.0

                friendly_label = _format_quota_display_name(metric_name)
                if model_name:
                    friendly_label = f"{friendly_label} [{model_name}]"
                unit = "1/min" if "minute" in clean_key else "1/day"

                results.append(
                    GCPQuotaInfo(
                        metric_name=friendly_label,
                        limit=limit_val,
                        unit=unit,
                    )
                )

                if len(results) >= 4:
                    break

            return results
        except Exception as exc:
            logger.warning(f"Failed to fetch Cloud Quota limits: {exc}")
            return []

    if client:
        return await _do_fetch(client)
    async with httpx.AsyncClient() as new_client:
        return await _do_fetch(new_client)


async def fetch_rate_usage(
    project_id: str,
    access_token: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Optional[GCPUsageMetrics]:
    """Retrieves actual net rate usage from Cloud Monitoring for the last 10 minutes."""
    url = CLOUD_MONITORING_URL.format(project_id=project_id)
    headers = {"Authorization": f"Bearer {access_token}"}

    now = datetime.now(timezone.utc)
    start_time = (now - timedelta(minutes=10)).isoformat()
    end_time = now.isoformat()

    params = {
        "filter": (
            'metric.type="serviceruntime.googleapis.com/quota/rate/net_usage" '
            'AND resource.labels.service="generativelanguage.googleapis.com"'
        ),
        "interval.startTime": start_time,
        "interval.endTime": end_time,
    }

    async def _do_fetch(http_client: httpx.AsyncClient) -> Optional[GCPUsageMetrics]:
        try:
            resp = await http_client.get(url, headers=headers, params=params, timeout=5.0)
            if resp.status_code != 200:
                logger.debug(f"Cloud Monitoring API returned status {resp.status_code}")
                return None

            data = resp.json()
            series_list = data.get("timeSeries", [])
            if not series_list:
                return None

            # Get the first matching series and its latest data point
            first_series = series_list[0]
            metric_label = (
                first_series.get("metric", {}).get("labels", {}).get("quota_metric", "gemini_requests")
            )
            points = first_series.get("points", [])
            if not points:
                return None

            latest_val = points[0].get("value", {})
            rate_number = latest_val.get("doubleValue", latest_val.get("int64Value", 0.0))

            return GCPUsageMetrics(
                current_rate_usage=float(rate_number),
                quota_metric=metric_label,
            )
        except Exception as exc:
            logger.warning(f"Failed to fetch Cloud Monitoring rate usage: {exc}")
            return None

    if client:
        return await _do_fetch(client)
    async with httpx.AsyncClient() as new_client:
        return await _do_fetch(new_client)
