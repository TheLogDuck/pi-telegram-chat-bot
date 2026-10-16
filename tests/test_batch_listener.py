# Unit tests for batch message logging and asynchronous flusher worker.
# Verifies micro-batching into SQLite to minimize MicroSD card wear and write lock contention.
import asyncio
from unittest.mock import MagicMock
import pytest
from core.database.connection import get_connection, init_db
from core.database.messages import async_save_messages_batch, save_messages_batch
from modules.listener import (
    _MESSAGE_QUEUE,
    flush_message_queue,
    message_batch_worker,
    passive_message_listener,
)


@pytest.fixture(autouse=True)
def clean_queue():
    """Drains the in-memory message queue before and after each test."""
    while not _MESSAGE_QUEUE.empty():
        _MESSAGE_QUEUE.get_nowait()
    yield
    while not _MESSAGE_QUEUE.empty():
        _MESSAGE_QUEUE.get_nowait()


def test_save_messages_batch(tmp_path):
    """Verifies that save_messages_batch writes multiple records in a single transaction."""
    test_db = str(tmp_path / "test_batch.db")
    init_db(test_db)

    batch = [
        (100, 1, "alice", "Перше повідомлення", "2026-10-15T12:00:00Z"),
        (100, 2, "bob", "Друге повідомлення", "2026-10-15T12:00:01Z"),
        (100, 3, "charlie", "Третє повідомлення", "2026-10-15T12:00:02Z"),
    ]

    count = save_messages_batch(batch, db_path=test_db)
    assert count == 3

    # Verify rows in database
    with get_connection(test_db) as conn:
        rows = conn.execute("SELECT * FROM messages ORDER BY id ASC").fetchall()
        assert len(rows) == 3
        assert rows[0]["username"] == "alice"
        assert rows[1]["username"] == "bob"
        assert rows[2]["username"] == "charlie"


def test_passive_listener_enqueues_and_flushes(tmp_path):
    """Verifies that listener puts messages into the queue and flush_message_queue writes to DB."""
    async def _run_test():
        test_db = str(tmp_path / "test_listener.db")
        init_db(test_db)

        # Build a mock Telegram update
        update = MagicMock()
        update.effective_message.text = "Тестове повідомлення"
        update.effective_message.date.isoformat.return_value = "2026-10-15T12:05:00Z"
        update.effective_chat.id = 555
        update.effective_user.id = 777
        update.effective_user.username = "test_user"

        context = MagicMock()

        # Call passive listener
        await passive_message_listener(update, context)

        # Message must be queued, not immediately in DB
        assert _MESSAGE_QUEUE.qsize() == 1

        # Flush the queue
        flushed = await flush_message_queue(db_path=test_db)
        assert flushed == 1
        assert _MESSAGE_QUEUE.empty()

        # Verify record in DB
        with get_connection(test_db) as conn:
            rows = conn.execute("SELECT * FROM messages WHERE chat_id = 555").fetchall()
            assert len(rows) == 1
            assert rows[0]["text"] == "Тестове повідомлення"
            assert rows[0]["username"] == "test_user"

    asyncio.run(_run_test())


def test_batch_worker_flushes_on_cancel(tmp_path):
    """Verifies that the background worker flushes any pending messages when cancelled."""
    async def _run_test():
        test_db = str(tmp_path / "test_worker.db")
        init_db(test_db)

        # Queue two messages directly
        _MESSAGE_QUEUE.put_nowait((888, 1, "u1", "msg1", "2026-10-15T12:10:00Z"))
        _MESSAGE_QUEUE.put_nowait((888, 2, "u2", "msg2", "2026-10-15T12:10:01Z"))
        assert _MESSAGE_QUEUE.qsize() == 2

        # Start the worker with a long interval and then immediately cancel it
        worker_task = asyncio.create_task(message_batch_worker(interval=60.0, db_path=test_db))
        await asyncio.sleep(0.01)
        worker_task.cancel()
        await worker_task

        # Queue must be drained and DB must contain 2 rows
        assert _MESSAGE_QUEUE.empty()
        with get_connection(test_db) as conn:
            rows = conn.execute("SELECT * FROM messages WHERE chat_id = 888").fetchall()
            assert len(rows) == 2

    asyncio.run(_run_test())
