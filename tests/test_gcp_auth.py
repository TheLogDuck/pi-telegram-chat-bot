# Unit tests for core/gcp/auth.py
# Validates in-memory OAuth2 token caching, expiration handling, and graceful fallbacks.
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest

from core.gcp.auth import get_gcp_access_token, reset_token_cache


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensures token cache is cleared before each test."""
    reset_token_cache()
    yield
    reset_token_cache()


def test_get_gcp_access_token_no_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that missing file configuration returns None cleanly."""
    monkeypatch.delenv("GCP_SERVICE_ACCOUNT_FILE", raising=False)
    token = get_gcp_access_token(service_account_path=None)
    assert token is None


def test_get_gcp_access_token_file_not_found() -> None:
    """Verifies that non-existent service account path returns None without raising an error."""
    token = get_gcp_access_token(service_account_path="non_existent_key_12345.json")
    assert token is None


def test_get_gcp_access_token_success_and_caching(tmp_path) -> None:
    """Verifies that credentials are created, refreshed, and cached in memory."""
    fake_key_file = tmp_path / "fake_key.json"
    fake_key_file.write_text("{}", encoding="utf-8")

    # Mock the Google Credentials object
    mock_creds = MagicMock()
    mock_creds.token = "fake_oauth2_bearer_token"
    mock_creds.expiry = datetime.now(timezone.utc) + timedelta(minutes=50)

    with patch("google.oauth2.service_account.Credentials.from_service_account_file") as mock_from_file:
        mock_from_file.return_value = mock_creds

        # First call: loads from file and refreshes
        token1 = get_gcp_access_token(service_account_path=str(fake_key_file))
        assert token1 == "fake_oauth2_bearer_token"
        assert mock_from_file.call_count == 1
        assert mock_creds.refresh.call_count == 1

        # Second call: uses in-memory cache without calling from_service_account_file again
        token2 = get_gcp_access_token(service_account_path=str(fake_key_file))
        assert token2 == "fake_oauth2_bearer_token"
        assert mock_from_file.call_count == 1
        assert mock_creds.refresh.call_count == 1
