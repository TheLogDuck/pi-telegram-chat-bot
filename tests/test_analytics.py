# Unit tests for modules/analytics.py.
# Verifies owner authorization, stats formatting, and command handling.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram import Update, User
from modules.analytics import format_stats_report, is_owner, stats_command


def test_is_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that is_owner validates against ADMIN_CHAT_ID."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "987654")

    # Matching owner user
    update_owner = MagicMock(spec=Update)
    user_owner = MagicMock(spec=User)
    user_owner.id = 987654
    update_owner.effective_user = user_owner
    assert is_owner(update_owner) is True

    # Non-owner user
    update_other = MagicMock(spec=Update)
    user_other = MagicMock(spec=User)
    user_other.id = 111111
    update_other.effective_user = user_other
    assert is_owner(update_other) is False

    # Missing ADMIN_CHAT_ID
    monkeypatch.delenv("ADMIN_CHAT_ID", raising=False)
    assert is_owner(update_owner) is False


def test_format_stats_report() -> None:
    """Verifies that format_stats_report structures the summary cleanly."""
    mock_stats = {
        "today": {
            "calls": 5,
            "prompt_tokens": 1200,
            "completion_tokens": 800,
            "total_tokens": 2000,
            "cost_usd": 0.00044,
        },
        "total": {
            "calls": 15,
            "prompt_tokens": 5000,
            "completion_tokens": 3000,
            "total_tokens": 8000,
            "cost_usd": 0.0017,
        },
        "by_feature": {
            "chat": {"calls": 10, "tokens": 5000, "cost_usd": 0.001},
            "news": {"calls": 5, "tokens": 3000, "cost_usd": 0.0007},
        },
    }

    report = format_stats_report(mock_stats)

    assert "Сьогодні (UTC):" in report
    assert "2,000" in report
    assert "$0.0004" in report
    assert "Діалоги (Chat): 10 запитів" in report
    assert "Новини (News): 5 запитів" in report
    assert "Ліміти Tier 1" in report


def test_format_stats_report_with_gcp_telemetry() -> None:
    """Verifies that format_stats_report formats official GCP metrics when available."""
    from core.gcp import (
        GCPBillingInfo,
        GCPQuotaInfo,
        GCPTelemetryReport,
        GCPUsageMetrics,
    )

    mock_stats = {
        "today": {"calls": 1, "total_tokens": 100, "prompt_tokens": 80, "completion_tokens": 20, "cost_usd": 0.0001},
        "total": {"calls": 1, "total_tokens": 100, "cost_usd": 0.0001},
        "by_feature": {},
    }

    gcp_report = GCPTelemetryReport(
        is_available=True,
        quotas=[GCPQuotaInfo(metric_name="RPM", limit=1000.0, unit="1/min")],
        usage=GCPUsageMetrics(current_rate_usage=3.5, quota_metric="reqs"),
        billing=GCPBillingInfo(cost_usd=0.15, currency="USD", status="synced"),
    )

    report = format_stats_report(mock_stats, gcp_report)

    assert "Офіційні дані Google Cloud (GCP):" in report
    assert "$0.1500 USD" in report
    assert "RPM: 1,000 1/min" in report
    assert "3.50 req/min" in report


def test_stats_command_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that stats_command queries both SQLite and GCP telemetry when invoked by owner."""
    monkeypatch.setenv("ADMIN_CHAT_ID", "12345")

    update = MagicMock(spec=Update)
    user = MagicMock(spec=User)
    user.id = 12345
    update.effective_user = user
    message = AsyncMock()
    update.effective_message = message

    context = MagicMock()

    with patch("modules.analytics.async_get_token_usage_stats", new_callable=AsyncMock) as m_stats:
        with patch("modules.analytics.get_gcp_telemetry", new_callable=AsyncMock) as m_gcp:
            from core.gcp import GCPTelemetryReport

            m_stats.return_value = {
                "today": {"calls": 0, "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0},
                "total": {"calls": 0, "total_tokens": 0, "cost_usd": 0.0},
                "by_feature": {},
            }
            m_gcp.return_value = GCPTelemetryReport(is_available=False)

            asyncio.run(stats_command(update, context))

            assert m_stats.call_count == 1
            assert m_gcp.call_count == 1
            assert message.reply_text.call_count == 1

