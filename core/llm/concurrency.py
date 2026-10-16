# Concurrency control module managing bounded execution for LLM API calls.
# Limits simultaneous network operations to safeguard Raspberry Pi 3B+ CPU and RAM.
import asyncio
from typing import Optional

# Maximum concurrent Gemini operations allowed across the application
DEFAULT_MAX_CONCURRENT_LLM_CALLS = 2

# Global singleton reference for the application's active semaphore
_LLM_SEMAPHORE: Optional[asyncio.Semaphore] = None


def get_llm_semaphore(limit: int = DEFAULT_MAX_CONCURRENT_LLM_CALLS) -> asyncio.Semaphore:
    """Returns the singleton asyncio.Semaphore instance for LLM operations.

    Lazily initializes the semaphore on the currently running event loop
    to prevent attaching to an inactive loop during startup.
    """
    global _LLM_SEMAPHORE
    if _LLM_SEMAPHORE is None:
        _LLM_SEMAPHORE = asyncio.Semaphore(limit)
    return _LLM_SEMAPHORE


def reset_llm_semaphore() -> None:
    """Resets the singleton semaphore. Useful for unit tests to isolate test cases."""
    global _LLM_SEMAPHORE
    _LLM_SEMAPHORE = None
