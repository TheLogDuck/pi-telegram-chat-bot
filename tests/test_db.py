# Unit tests for database initialization and message logging operations.
import asyncio
from core.db import async_save_message, get_connection, init_db, save_message

def test_init_db_and_save_message(tmp_path):
    """Verifies that init_db creates schema and messages are saved accurately."""
    # Use isolated test database path
    test_db = str(tmp_path / "test_memory.db")

    # Initialize tables
    init_db(test_db)

    # Save a test message synchronously
    row_id = save_message(
        chat_id=12345,
        user_id=67890,
        username="alice",
        text="Hello Raspberry Pi",
        timestamp="2026-10-06T20:00:00Z",
        db_path=test_db,
    )
    assert row_id == 1

    # Save a test message asynchronously using standard library asyncio.run
    row_id_async = asyncio.run(
        async_save_message(
            chat_id=12345,
            user_id=99999,
            username="bob",
            text="Async message logging test",
            timestamp="2026-10-06T20:01:00Z",
            db_path=test_db,
        )
    )
    assert row_id_async == 2

    # Query back messages to verify stored values
    with get_connection(test_db) as conn:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT * FROM messages ORDER BY id ASC").fetchall()
        assert len(rows) == 2
        assert rows[0]["username"] == "alice"
        assert rows[0]["text"] == "Hello Raspberry Pi"
        assert rows[1]["username"] == "bob"
        assert rows[1]["text"] == "Async message logging test"
