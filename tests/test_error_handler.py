# Unit test for global error handler logging behavior
import asyncio
from unittest.mock import MagicMock, patch
from core.error_handler import global_error_handler

def test_global_error_handler_logs_error() -> None:
    """Verifies that global_error_handler logs context errors properly."""
    mock_context = MagicMock()
    mock_context.error = ValueError("Simulated network timeout")
    mock_update = {"update_id": 12345}

    with patch("core.error_handler.logger.error") as mock_log:
        asyncio.run(global_error_handler(mock_update, mock_context))

        mock_log.assert_called_once()
        args, kwargs = mock_log.call_args
        assert "Simulated network timeout" in args[0]
        assert kwargs["exc_info"] == mock_context.error
