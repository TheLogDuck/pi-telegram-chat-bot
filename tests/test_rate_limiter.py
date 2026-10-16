# Unit tests for core/rate_limiter.py
# Validates per-user cooldowns, per-chat concurrency limits, and memory leak prevention.
import time
import pytest
from core.rate_limiter import RateLimiter


@pytest.fixture
def limiter():
    """Provides a fresh RateLimiter instance for each test."""
    return RateLimiter(user_cooldown_seconds=2.0, max_chat_concurrency=2)


def test_user_cooldown_allow_and_block(limiter):
    """Verifies that subsequent user requests within cooldown are blocked."""
    user_id = 1001

    # First request must succeed
    allowed, remaining = limiter.check_user_cooldown(user_id)
    assert allowed is True
    assert remaining == 0.0

    # Immediate second request must be blocked
    allowed, remaining = limiter.check_user_cooldown(user_id)
    assert allowed is False
    assert remaining > 0.0


def test_user_cooldown_expires(limiter):
    """Verifies that requests are allowed after the cooldown window elapses."""
    user_id = 1002
    limiter.user_cooldown_seconds = 0.05

    # First request
    allowed, _ = limiter.check_user_cooldown(user_id)
    assert allowed is True

    # Wait for cooldown to expire
    time.sleep(0.06)

    allowed, remaining = limiter.check_user_cooldown(user_id)
    assert allowed is True
    assert remaining == 0.0


def test_chat_concurrency_slots(limiter):
    """Verifies that chat concurrency is strictly limited to max_chat_concurrency."""
    chat_id = -2001

    # First slot acquired
    assert limiter.acquire_chat_slot(chat_id) is True
    # Second slot acquired
    assert limiter.acquire_chat_slot(chat_id) is True
    # Third slot rejected (limit is 2)
    assert limiter.acquire_chat_slot(chat_id) is False

    # Release one slot
    limiter.release_chat_slot(chat_id)

    # Now an acquisition should succeed
    assert limiter.acquire_chat_slot(chat_id) is True


def test_chat_concurrency_context_manager(limiter):
    """Verifies chat slot acquisition and automatic release via context manager."""
    chat_id = -2002

    with limiter.chat_slot(chat_id) as acquired1:
        assert acquired1 is True
        with limiter.chat_slot(chat_id) as acquired2:
            assert acquired2 is True
            # Third acquisition inside the nested blocks must fail
            with limiter.chat_slot(chat_id) as acquired3:
                assert acquired3 is False

    # After exiting all context managers, slots are released
    assert limiter.get_active_chat_tasks(chat_id) == 0


def test_stale_entry_cleanup(limiter):
    """Verifies that stale user timestamps are cleaned up to prevent memory leaks."""
    # Seed old timestamps
    now = time.monotonic()
    limiter._user_last_request[999] = now - 100.0
    limiter._user_last_request[888] = now

    limiter.cleanup_stale_entries(max_age_seconds=50.0)

    assert 999 not in limiter._user_last_request
    assert 888 in limiter._user_last_request
