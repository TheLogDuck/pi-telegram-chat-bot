# Unit tests verifying ApplicationBuilder rate limiter configuration and lifecycle hooks.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram.ext import AIORateLimiter, Application
from main import on_shutdown, on_startup


def test_startup_and_shutdown_flusher_lifecycle():
    """Verifies that flusher background task is spawned on startup and cancelled on shutdown."""
    async def _run_test():
        mock_app = MagicMock(spec=Application)
        mock_app.bot_data = {}

        async def dummy_loop():
            await asyncio.sleep(100)

        with patch("main.set_bot_commands", new_callable=AsyncMock):
            with patch("main.periodic_cleanup_task", side_effect=dummy_loop):
                with patch("main.message_batch_worker", side_effect=dummy_loop):
                    with patch("main.flush_message_queue", new_callable=AsyncMock) as mock_flush:
                        # Run on_startup
                        await on_startup(mock_app)
                        assert "cleanup_task" in mock_app.bot_data
                        assert "flusher_task" in mock_app.bot_data

                        # Run on_shutdown
                        await on_shutdown(mock_app)
                        assert mock_app.bot_data["flusher_task"].cancelled()
                        mock_flush.assert_awaited_once()

    asyncio.run(_run_test())


def test_main_builder_aioratelimiter_fallback():
    """Verifies that main handles missing aiolimiter dependency without crashing."""
    with patch("main.init_db"):
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "12345:dummy_token"}):
            with patch("main.Application.run_polling"):
                with patch("main.AIORateLimiter", side_effect=RuntimeError("No aiolimiter")):
                    from main import main
                    # main() should catch RuntimeError and proceed cleanly without raising
                    main()

