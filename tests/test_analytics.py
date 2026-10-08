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
