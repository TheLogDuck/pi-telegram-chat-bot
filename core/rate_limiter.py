# In-memory rate limiting and concurrency management module.
# Protects against user spam, chat flooding, and excessive memory growth on Raspberry Pi 3B+.
from contextlib import contextmanager
import time
from typing import Generator, Optional
from core.logger import setup_logger

logger = setup_logger("rate_limiter")

# Default cooldown in seconds required between prompts from the same user
DEFAULT_USER_COOLDOWN_SECONDS = 5.0

# Maximum simultaneous AI generations permitted in a single group chat
DEFAULT_MAX_CHAT_CONCURRENCY = 3

# Pruning threshold to evict inactive user entries and keep RAM footprint < 100 KB
DEFAULT_STALE_AGE_SECONDS = 300.0


class RateLimiter:
    """Manages per-user invocation cooldowns and per-chat concurrent task limits."""

    def __init__(
        self,
        user_cooldown_seconds: float = DEFAULT_USER_COOLDOWN_SECONDS,
        max_chat_concurrency: int = DEFAULT_MAX_CHAT_CONCURRENCY,
    ) -> None:
        self.user_cooldown_seconds = user_cooldown_seconds
        self.max_chat_concurrency = max_chat_concurrency

        # Stores timestamp of last request: user_id -> monotonic_timestamp
        self._user_last_request: dict[int, float] = {}

        # Tracks active AI tasks running in each chat: chat_id -> active_count
        self._chat_active_tasks: dict[int, int] = {}

        # Counter for lazy periodic cleanup
        self._check_counter: int = 0

    def check_user_cooldown(self, user_id: int) -> tuple[bool, float]:
        """Evaluates whether a user is allowed to issue an AI prompt.

        Returns a tuple (allowed, seconds_remaining).
        Uses time.monotonic() to be immune to system clock shifts.
        """
        now = time.monotonic()
        self._check_counter += 1

        # Periodically prune stale entries every 50 checks to bound memory usage
        if self._check_counter % 50 == 0:
            self.cleanup_stale_entries()

        last_time = self._user_last_request.get(user_id)
        if last_time is not None:
            elapsed = now - last_time
            if elapsed < self.user_cooldown_seconds:
                remaining = self.user_cooldown_seconds - elapsed
                return False, round(remaining, 1)

        # Record this invocation timestamp
        self._user_last_request[user_id] = now
        return True, 0.0

    def acquire_chat_slot(self, chat_id: int) -> bool:
        """Attempts to claim a concurrent AI processing slot for the specified chat.

        Returns True if a slot was successfully acquired, False if the chat is at capacity.
        """
        current_active = self._chat_active_tasks.get(chat_id, 0)
        if current_active >= self.max_chat_concurrency:
            logger.warning(
                f"Chat {chat_id} reached concurrency limit ({current_active}/{self.max_chat_concurrency})."
            )
            return False

        self._chat_active_tasks[chat_id] = current_active + 1
        return True

    def release_chat_slot(self, chat_id: int) -> None:
        """Releases a claimed AI processing slot when task completes."""
        current_active = self._chat_active_tasks.get(chat_id, 0)
        if current_active <= 1:
            # Delete key if zero to keep dictionary size minimal
            self._chat_active_tasks.pop(chat_id, None)
        else:
            self._chat_active_tasks[chat_id] = current_active - 1

    def get_active_chat_tasks(self, chat_id: int) -> int:
        """Returns the number of currently executing AI tasks in the chat."""
        return self._chat_active_tasks.get(chat_id, 0)

    @contextmanager
    def chat_slot(self, chat_id: int) -> Generator[bool, None, None]:
        """Context manager to safely acquire and release a chat concurrency slot."""
        acquired = self.acquire_chat_slot(chat_id)
        try:
            yield acquired
        finally:
            if acquired:
                self.release_chat_slot(chat_id)

    def cleanup_stale_entries(self, max_age_seconds: float = DEFAULT_STALE_AGE_SECONDS) -> int:
        """Evicts user entries older than max_age_seconds to prevent memory growth."""
        now = time.monotonic()
        stale_user_ids = [
            uid
            for uid, last_time in self._user_last_request.items()
            if now - last_time > max_age_seconds
        ]
        for uid in stale_user_ids:
            del self._user_last_request[uid]
        return len(stale_user_ids)


# Application-wide default RateLimiter singleton instance
_GLOBAL_RATE_LIMITER: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Returns the application-wide singleton RateLimiter instance."""
    global _GLOBAL_RATE_LIMITER
    if _GLOBAL_RATE_LIMITER is None:
        _GLOBAL_RATE_LIMITER = RateLimiter()
    return _GLOBAL_RATE_LIMITER
