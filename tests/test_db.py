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
        assert rows[0]["username"] == "alice"
        assert rows[0]["text"] == "Hello Raspberry Pi"
        assert rows[1]["username"] == "bob"
        assert rows[1]["text"] == "Async message logging test"


def test_get_user_messages_filtering_and_order(tmp_path):
    """Verifies that get_user_messages retrieves recent non-command messages."""
    from core.db import async_get_user_messages, get_user_messages

    test_db = str(tmp_path / "test_memory.db")
    init_db(test_db)

    # Insert several messages from alice, including a slash command
    save_message(100, 1, "alice", "Перше повідомлення", db_path=test_db)
    save_message(100, 1, "alice", "/help", db_path=test_db)  # command to ignore
    save_message(100, 1, "Alice", "Друге повідомлення", db_path=test_db)
    save_message(100, 2, "bob", "Повідомлення від Боба", db_path=test_db)
    save_message(100, 1, "alice", "Третє повідомлення", db_path=test_db)

    # Fetch by username with @ symbol
    messages = get_user_messages(chat_id=100, username="@Alice", limit=5, db_path=test_db)
    assert len(messages) == 3
    assert messages == ["Перше повідомлення", "Друге повідомлення", "Третє повідомлення"]

    # Test async wrapper and limit=2
    async_messages = asyncio.run(
        async_get_user_messages(chat_id=100, username="alice", limit=2, db_path=test_db)
    )
    assert len(async_messages) == 2
    assert async_messages == ["Друге повідомлення", "Третє повідомлення"]

    # Test query by user_id
    id_messages = get_user_messages(chat_id=100, user_id=2, limit=5, db_path=test_db)
    assert id_messages == ["Повідомлення від Боба"]


def test_save_and_get_token_usage_stats(tmp_path):
    """Verifies that token usage records are saved and aggregated accurately."""
    from core.db import async_save_token_usage, get_token_usage_stats, save_token_usage

    test_db = str(tmp_path / "test_memory.db")
    init_db(test_db)

    # Insert initial chat usage record
    save_token_usage(
        model="gemini-3.8-flash",
        feature="chat",
        prompt_tokens=100,
        completion_tokens=200,
        total_tokens=300,
        cost_usd=0.00009,
        chat_id=123,
        user_id=456,
        db_path=test_db,
    )

    # Insert another record asynchronously
    asyncio.run(
        async_save_token_usage(
            model="gemini-3.8-flash",
            feature="news",
            prompt_tokens=150,
            completion_tokens=350,
            total_tokens=500,
            cost_usd=0.000155,
            chat_id=123,
            user_id=456,
            db_path=test_db,
        )
    )

    stats = get_token_usage_stats(db_path=test_db)

    # Verify aggregated totals
    assert stats["today"]["calls"] == 2
    assert stats["today"]["total_tokens"] == 800
    assert stats["today"]["prompt_tokens"] == 250
    assert stats["today"]["completion_tokens"] == 550
    assert stats["total"]["calls"] == 2

    # Verify feature breakdown
    assert "chat" in stats["by_feature"]
    assert stats["by_feature"]["chat"]["tokens"] == 300
    assert "news" in stats["by_feature"]
    assert stats["by_feature"]["news"]["tokens"] == 500


def test_cleanup_old_messages(tmp_path):
    """Verifies that cleanup_old_messages deletes rows older than retention_days."""
    from datetime import datetime, timedelta, timezone
    from core.db import cleanup_old_messages, get_connection, init_db, save_message

    test_db = str(tmp_path / "test_memory.db")
    init_db(test_db)

    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=35)).isoformat()
    recent_ts = (now - timedelta(days=5)).isoformat()

    # Save 1 old message and 1 recent message
    save_message(1, 1, "alice", "Дуже старе повідомлення", timestamp=old_ts, db_path=test_db)
    save_message(1, 1, "alice", "Свіже повідомлення", timestamp=recent_ts, db_path=test_db)

    # Prune with 30 days retention
    deleted = cleanup_old_messages(retention_days=30, db_path=test_db)
    assert deleted == 1

    # Verify only the recent message remains
    with get_connection(test_db) as conn:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT text FROM messages").fetchall()
        assert len(rows) == 1
        assert rows[0]["text"] == "Свіже повідомлення"


def test_async_cleanup_old_messages(tmp_path):
    """Verifies non-blocking async wrapper executes cleanup cleanly."""
    from datetime import datetime, timedelta, timezone
    from core.db import async_cleanup_old_messages, init_db, save_message

    test_db = str(tmp_path / "test_memory.db")
    init_db(test_db)

    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=40)).isoformat()

    save_message(1, 1, "bob", "Старе повідомлення", timestamp=old_ts, db_path=test_db)

    deleted = asyncio.run(async_cleanup_old_messages(retention_days=30, db_path=test_db))
    assert deleted == 1


