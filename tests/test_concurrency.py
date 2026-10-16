# Unit tests for core/llm/concurrency.py
# Validates bounded concurrency using asyncio.Semaphore to protect Pi CPU and Gemini quotas.
import asyncio
import pytest
from core.llm.concurrency import (
    DEFAULT_MAX_CONCURRENT_LLM_CALLS,
    get_llm_semaphore,
    reset_llm_semaphore,
)


@pytest.fixture(autouse=True)
def clean_semaphore():
    """Ensures a clean semaphore state before and after each test."""
    reset_llm_semaphore()
    yield
    reset_llm_semaphore()


def test_semaphore_singleton():
    """Verifies that get_llm_semaphore returns the same singleton instance."""
    sem1 = get_llm_semaphore()
    sem2 = get_llm_semaphore()
    assert sem1 is sem2
    assert sem1._value == DEFAULT_MAX_CONCURRENT_LLM_CALLS


def test_semaphore_limits_concurrency():
    """Verifies that at most N concurrent tasks can hold the semaphore simultaneously."""
    async def _run_test():
        max_concurrent = 2
        sem = get_llm_semaphore(limit=max_concurrent)

        current_concurrent = 0
        peak_concurrent = 0

        async def worker():
            nonlocal current_concurrent, peak_concurrent
            async with sem:
                current_concurrent += 1
                if current_concurrent > peak_concurrent:
                    peak_concurrent = current_concurrent
                # Simulate a brief asynchronous API call
                await asyncio.sleep(0.05)
                current_concurrent -= 1

        # Launch 6 concurrent workers
        tasks = [asyncio.create_task(worker()) for _ in range(6)]
        await asyncio.gather(*tasks)

        # Concurrency must never have exceeded the limit of 2
        assert peak_concurrent == max_concurrent

    asyncio.run(_run_test())
