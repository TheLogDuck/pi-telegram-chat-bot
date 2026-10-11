# BigQuery Billing module: queries Google Cloud Billing Export tables.
# Uses direct REST API queries via httpx, keeping the process lightweight (< 2MB RAM).
from typing import Optional
import httpx
from core.logger import setup_logger
from .models import GCPBillingInfo

logger = setup_logger("gcp.billing")

BIGQUERY_QUERY_URL = "https://bigquery.googleapis.com/bigquery/v2/projects/{project_id}/queries"


async def fetch_month_to_date_spend(
    project_id: str,
    billing_table: str,
    access_token: str,
    client: Optional[httpx.AsyncClient] = None,
) -> GCPBillingInfo:
    """Queries BigQuery Billing Export for total month-to-date invoiced costs."""
    table_name = (billing_table or "").strip()
    if not table_name:
        return GCPBillingInfo(cost_usd=0.0, currency="USD", status="unconfigured")

    # Detect default placeholder configuration from .env.example
    lower_table = table_name.lower()
    if "your-project-id" in lower_table or "xxxxxx" in lower_table:
        logger.debug("Placeholder GCP_BILLING_TABLE detected; treating as unconfigured.")
        return GCPBillingInfo(cost_usd=0.0, currency="USD", status="unconfigured")

    # BigQuery requires table identifiers to be qualified with a dataset (e.g. dataset.table)
    if "." not in table_name:
        logger.warning(
            f"GCP_BILLING_TABLE '{table_name}' is missing dataset qualification. "
            "BigQuery requires 'dataset.table' (e.g., 'billing_data.gcp_billing_export_...')."
        )
        return GCPBillingInfo(cost_usd=0.0, currency="USD", status="unconfigured")

    url = BIGQUERY_QUERY_URL.format(project_id=project_id)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # Query only the current month's partition to scan minimal data (typically < 5MB)
    query_sql = (
        f"SELECT COALESCE(SUM(cost), 0.0) as cost_usd, currency "
        f"FROM `{table_name}` "
        f"WHERE _PARTITIONDATE >= DATE_TRUNC(CURRENT_DATE(), MONTH) "
        f"GROUP BY currency LIMIT 1;"
    )
    body = {"query": query_sql, "useLegacySql": False}

    async def _do_query(http_client: httpx.AsyncClient) -> GCPBillingInfo:
        try:
            resp = await http_client.post(url, headers=headers, json=body, timeout=7.0)

            # Table has not yet been exported by Google's background sync (Google returns 404 or 403 with 'does not exist')
            if resp.status_code == 404 or (
                resp.status_code == 403 and ("does not exist" in resp.text.lower() or "not found" in resp.text.lower())
            ):
                logger.info("BigQuery billing export table not yet created by Google sync. Awaiting export.")
                return GCPBillingInfo(cost_usd=0.0, currency="USD", status="pending_first_export")

            if resp.status_code != 200:
                logger.warning(f"BigQuery query failed with HTTP status {resp.status_code}: {resp.text}")
                return GCPBillingInfo(cost_usd=0.0, currency="USD", status="error")

            data = resp.json()
            rows = data.get("rows", [])
            if not rows:
                # Table exists, but no costs accrued yet this month
                return GCPBillingInfo(cost_usd=0.0, currency="USD", status="synced")

            # Parse the aggregated cost and currency from the first row
            first_row_fields = rows[0].get("f", [])
            cost_str = first_row_fields[0].get("v", "0.0") if len(first_row_fields) > 0 else "0.0"
            currency_str = first_row_fields[1].get("v", "USD") if len(first_row_fields) > 1 else "USD"

            try:
                cost_usd = float(cost_str)
            except (ValueError, TypeError):
                cost_usd = 0.0

            return GCPBillingInfo(cost_usd=cost_usd, currency=currency_str, status="synced")
        except Exception as exc:
            logger.warning(f"Error querying BigQuery billing table: {exc}")
            return GCPBillingInfo(cost_usd=0.0, currency="USD", status="error")

    if client:
        return await _do_query(client)
    async with httpx.AsyncClient() as new_client:
        return await _do_query(new_client)
