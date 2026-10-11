# Unit tests for core/gcp/billing.py
# Validates querying BigQuery Billing Export via REST API and defensive 404 traps.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest

from core.gcp.billing import fetch_month_to_date_spend


def test_fetch_month_to_date_spend_success() -> None:
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

        billing = asyncio.run(
            fetch_month_to_date_spend(
                project_id="test-proj",
                billing_table="test-proj.dataset.table",
                access_token="test-token",
            )
        )

        assert billing.cost_usd == 0.1425
        assert billing.currency == "USD"
        assert billing.status == "synced"


def test_fetch_month_to_date_spend_empty_table() -> None:
    """Verifies that an empty query result defaults to 0.0 with synced status."""
    mock_payload = {"rows": []}

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_payload

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        billing = asyncio.run(
            fetch_month_to_date_spend(
                project_id="test-proj",
                billing_table="test-proj.dataset.table",
                access_token="test-token",
            )
        )

        assert billing.cost_usd == 0.0
        assert billing.currency == "USD"
        assert billing.status == "synced"


def test_fetch_month_to_date_spend_404_pending_export() -> None:
    """Verifies that a 404 response (table not created yet by Google) returns pending_first_export."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        billing = asyncio.run(
            fetch_month_to_date_spend(
                project_id="test-proj",
                billing_table="test-proj.dataset.table",
                access_token="test-token",
            )
        )

        assert billing.cost_usd == 0.0
        assert billing.status == "pending_first_export"


def test_fetch_month_to_date_spend_403_does_not_exist() -> None:
    """Verifies that a 403 response with 'does not exist' returns pending_first_export."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 403
    mock_response.text = "Access Denied: Table proj:ds.tbl: User does not have permission, or perhaps it does not exist."

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        billing = asyncio.run(
            fetch_month_to_date_spend(
                project_id="test-proj",
                billing_table="test-proj.dataset.table",
                access_token="test-token",
            )
        )

        assert billing.cost_usd == 0.0
        assert billing.status == "pending_first_export"


def test_fetch_month_to_date_spend_unconfigured() -> None:
    """Verifies that an empty or missing table string returns unconfigured status immediately."""
    billing = asyncio.run(
        fetch_month_to_date_spend(
            project_id="test-proj",
            billing_table="",
            access_token="test-token",
        )
    )
    assert billing.cost_usd == 0.0
    assert billing.status == "unconfigured"


def test_fetch_month_to_date_spend_placeholder() -> None:
    """Verifies that template placeholders from .env.example return unconfigured status."""
    billing = asyncio.run(
        fetch_month_to_date_spend(
            project_id="test-proj",
            billing_table="your-project-id.billing_data.gcp_billing_export_v1_XXXXXX_XXXXXX_XXXXXX",
            access_token="test-token",
        )
    )
    assert billing.cost_usd == 0.0
    assert billing.status == "unconfigured"


def test_fetch_month_to_date_spend_unqualified_table() -> None:
    """Verifies that a table name without a dataset prefix returns unconfigured status."""
    billing = asyncio.run(
        fetch_month_to_date_spend(
            project_id="test-proj",
            billing_table="gcp_billing_export_v1_0187FF_3AA227_BC08ED",
            access_token="test-token",
        )
    )
    assert billing.cost_usd == 0.0
    assert billing.status == "unconfigured"
