# OAuth2 authentication and in-memory token caching for Google Cloud Platform.
# Generates Bearer tokens using google.oauth2.service_account and caches them until expiry.
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from core.logger import setup_logger

logger = setup_logger("gcp.auth")

# Standard Google Cloud platform scope granting access to administrative APIs
GCP_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

# In-memory token cache to prevent disk reads and re-authentication on every query
_cached_token: Optional[str] = None
_token_expiry: Optional[datetime] = None


def reset_token_cache() -> None:
    """Clears the cached OAuth2 token (used primarily in test fixtures)."""
    global _cached_token, _token_expiry
    _cached_token = None
    _token_expiry = None


def is_token_valid() -> bool:
    """Checks whether the cached token exists and has at least 5 minutes of validity remaining."""
    if not _cached_token or not _token_expiry:
        return False
    # Ensure expiration timestamp is timezone-aware in UTC
    now_utc = datetime.now(timezone.utc)
    expiry_utc = _token_expiry if _token_expiry.tzinfo else _token_expiry.replace(tzinfo=timezone.utc)
    # Refresh early if less than 5 minutes remain
    return now_utc < (expiry_utc - timedelta(minutes=5))


def get_gcp_access_token(service_account_path: Optional[str] = None) -> Optional[str]:
    """Retrieves an active OAuth2 Bearer token from the service account key.

    Returns:
        str: Active bearer token if authentication succeeds.
        None: If credentials are not configured or the key file is missing.
    """
    global _cached_token, _token_expiry

    # Fast path: return valid in-memory token without disk or network I/O
    if is_token_valid():
        return _cached_token

    key_path = service_account_path or os.getenv("GCP_SERVICE_ACCOUNT_FILE")
    if not key_path or not os.path.exists(key_path):
        logger.debug(f"GCP service account key file not found: {key_path}")
        return None

    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        # Load service account credentials from JSON key
        credentials = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=GCP_SCOPES,
        )

        # Refresh the credentials to obtain a fresh Bearer token
        credentials.refresh(Request())

        _cached_token = credentials.token
        _token_expiry = credentials.expiry

        logger.debug("Successfully refreshed GCP OAuth2 service account token.")
        return _cached_token
    except Exception as exc:
        logger.warning(f"Failed to authenticate with GCP service account: {exc}")
        return None
