# Unit tests for core/gcp/billing.py
# Validates querying BigQuery Billing Export via REST API and defensive 404 traps.
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from core.gcp.billing import fetch_month_to_date_spend


@pytest.mark.asyncio
async def test_fetch_month_to_date_spend_success() -> None:
    """Verifies that a valid BigQuery query response is parsed into a GCPBillingInfo object."""
    mock_payload = {
        "rows": [
            {
                "f": [
                    {"v": "0.1425"},
                    {"v": "USD"},
                ]
            }
        ]
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_payload

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        billing = await fetch_month_to_date_spend(
            project_id="test-proj",
            billing_table="test-proj.dataset.table",
            access_token="test-token",
        )

        assert billing.cost_usd == 0.1425
        assert billing.currency == "USD"
        assert billing.status == "synced"


@pytest.mark.asyncio
async def test_fetch_month_to_date_spend_empty_table() -> None:
    """Verifies that an empty query result defaults to 0.0 with synced status."""
    mock_payload = {"rows": []}

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_payload

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        billing = await fetch_month_to_date_spend(
            project_id="test-proj",
            billing_table="test-proj.dataset.table",
            access_token="test-token",
        )

        assert billing.cost_usd == 0.0
        assert billing.currency == "USD"
        assert billing.status == "synced"


@pytest.mark.asyncio
async def test_fetch_month_to_date_spend_404_pending_export() -> None:
    """Verifies that a 404 response (table not created yet by Google) returns pending_first_export."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 404

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        billing = await fetch_month_to_date_spend(
            project_id="test-proj",
            billing_table="test-proj.dataset.table",
            access_token="test-token",
        )

        assert billing.cost_usd == 0.0
        assert billing.status == "pending_first_export"


@pytest.mark.asyncio
async def test_fetch_month_to_date_spend_unconfigured() -> None:
    """Verifies that an empty or missing table string returns unconfigured status immediately."""
    billing = await fetch_month_to_date_spend(
        project_id="test-proj",
        billing_table="",
        access_token="test-token",
    )
    assert billing.cost_usd == 0.0
    assert billing.status == "unconfigured"
