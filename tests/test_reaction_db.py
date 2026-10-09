# Unit tests for database reaction settings and history retrieval.
# Runs fully offline with temporary SQLite database instances.
import asyncio
import pytest

from core.db import (
    async_get_recent_chat_messages,
    async_is_reaction_enabled,
    async_set_reaction_enabled,
    async_toggle_reaction_enabled,
    get_effective_persona,
    get_chat_messages,
    get_recent_chat_messages,
    init_db,

    is_reaction_enabled,
    save_message,
    set_reaction_enabled,
    set_user_persona,
    toggle_reaction_enabled,
)


def test_reaction_settings_default_and_set(tmp_path) -> None:
    """Verifies that reactions are disabled by default and can be toggled on/off."""
    db_file = str(tmp_path / "test_reaction_settings.db")
    init_db(db_file)

    # By default, a chat that has not been configured must have reactions disabled
    assert is_reaction_enabled(-1001, db_path=db_file) is False

    # Explicitly enable reactions for chat -1001
    set_reaction_enabled(-1001, True, db_path=db_file)
    assert is_reaction_enabled(-1001, db_path=db_file) is True

    # Other chats must remain disabled independently
    assert is_reaction_enabled(-1002, db_path=db_file) is False

    # Explicitly disable reactions for chat -1001
    set_reaction_enabled(-1001, False, db_path=db_file)
    assert is_reaction_enabled(-1001, db_path=db_file) is False


def test_toggle_reaction_enabled(tmp_path) -> None:
    """Verifies that toggle_reaction_enabled flips boolean state and returns new value."""
    db_file = str(tmp_path / "test_toggle.db")
    init_db(db_file)

    # First toggle: disabled (default) -> enabled
    new_state = toggle_reaction_enabled(-2001, db_path=db_file)
    assert new_state is True
    assert is_reaction_enabled(-2001, db_path=db_file) is True

    # Second toggle: enabled -> disabled
    new_state = toggle_reaction_enabled(-2001, db_path=db_file)
    assert new_state is False
    assert is_reaction_enabled(-2001, db_path=db_file) is False


def test_async_reaction_settings(tmp_path) -> None:
    """Verifies non-blocking async wrappers for reaction settings."""
    db_file = str(tmp_path / "test_async_reactions.db")
    init_db(db_file)

    async def run_async() -> None:
        assert await async_is_reaction_enabled(-3001, db_path=db_file) is False
        await async_set_reaction_enabled(-3001, True, db_path=db_file)
        assert await async_is_reaction_enabled(-3001, db_path=db_file) is True
        toggled = await async_toggle_reaction_enabled(-3001, db_path=db_file)
        assert toggled is False
        assert await async_is_reaction_enabled(-3001, db_path=db_file) is False

    asyncio.run(run_async())


def test_get_recent_chat_messages_limit_and_order(tmp_path) -> None:
    """Verifies retrieving up to 5 messages in chronological order across all users."""
    db_file = str(tmp_path / "test_history.db")
    init_db(db_file)

    chat_id = -4001
    # Insert 7 sequential messages from different users
    for i in range(1, 8):
        save_message(
            chat_id=chat_id,
            user_id=100 + i,
            username=f"user_{i}",
            text=f"Message number {i}",
            db_path=db_file,
        )

    # Query last 5 messages
    recent = get_recent_chat_messages(chat_id, limit=5, db_path=db_file)
    assert len(recent) == 5

    # Chronological check: oldest of the 5 first (number 3), newest last (number 7)
    assert recent[0]["text"] == "Message number 3"
    assert recent[0]["username"] == "user_3"
    assert recent[-1]["text"] == "Message number 7"
    assert recent[-1]["username"] == "user_7"


def test_get_recent_chat_messages_excludes_commands(tmp_path) -> None:
    """Verifies that slash commands are excluded from conversation history."""
    db_file = str(tmp_path / "test_filter_commands.db")
    init_db(db_file)

    chat_id = -5001
    save_message(chat_id, 101, "alex", "Hello everyone", db_path=db_file)
    save_message(chat_id, 102, "dmitry", "/help", db_path=db_file)
    save_message(chat_id, 101, "alex", "/roast @dmitry", db_path=db_file)
    save_message(chat_id, 103, "olga", "Good afternoon!", db_path=db_file)

    recent = get_recent_chat_messages(chat_id, limit=5, db_path=db_file)
    texts = [msg["text"] for msg in recent]
    assert "/help" not in texts
    assert "/roast @dmitry" not in texts
    assert texts == ["Hello everyone", "Good afternoon!"]


def test_get_recent_chat_messages_with_before_id(tmp_path) -> None:
    """Verifies that passing before_id excludes the current message and only takes earlier ones."""
    db_file = str(tmp_path / "test_before_id.db")
    init_db(db_file)

    chat_id = -6001
    id1 = save_message(chat_id, 101, "u1", "First message", db_path=db_file)
    id2 = save_message(chat_id, 102, "u2", "Second message", db_path=db_file)
    id3 = save_message(chat_id, 103, "u3", "Third message (current)", db_path=db_file)

    # Query messages before the current one (id3)
    recent = get_recent_chat_messages(chat_id, limit=5, before_id=id3, db_path=db_file)
    texts = [msg["text"] for msg in recent]
    assert texts == ["First message", "Second message"]
    assert "Third message (current)" not in texts


def test_async_get_recent_chat_messages(tmp_path) -> None:
    """Verifies async wrapper for get_recent_chat_messages."""
    db_file = str(tmp_path / "test_async_history.db")
    init_db(db_file)

    save_message(-7001, 101, "alex", "Chat content", db_path=db_file)

    async def run_async() -> None:
        messages = await async_get_recent_chat_messages(-7001, limit=5, db_path=db_file)
        assert len(messages) == 1
        assert messages[0]["text"] == "Chat content"

    asyncio.run(run_async())


def test_get_effective_persona_resolution(tmp_path) -> None:
    """Verifies persona resolution order: chat persona -> user persona -> standard."""
    db_file = str(tmp_path / "test_effective_persona.db")
    init_db(db_file)

    chat_id = -8001
    user_id = 9001

    # Default fallback when neither has a persona configured
    assert get_effective_persona(chat_id, user_id, db_path=db_file) == "standard"

    # Configure user persona: effective persona becomes cynic
    set_user_persona(user_id, "cynic", db_path=db_file)
    assert get_effective_persona(chat_id, user_id, db_path=db_file) == "cynic"

    # Configure chat persona: chat persona takes precedence over individual user persona
    set_user_persona(chat_id, "meme_lord", db_path=db_file)
    assert get_effective_persona(chat_id, user_id, db_path=db_file) == "meme_lord"


def test_get_chat_messages_unified(tmp_path) -> None:
    """Verifies that unified get_chat_messages works for both user-filtered and chat-wide queries."""
    db_file = str(tmp_path / "test_unified.db")
    init_db(db_file)

    save_message(-9001, 1, "alice", "Alice message 1", db_path=db_file)
    save_message(-9001, 2, "bob", "Bob message 1", db_path=db_file)
    save_message(-9001, 1, "alice", "Alice message 2", db_path=db_file)

    # Chat-wide query: gets all messages
    all_msgs = get_chat_messages(-9001, limit=10, db_path=db_file)
    assert len(all_msgs) == 3

    # User-filtered query: gets only Alice's messages
    alice_msgs = get_chat_messages(-9001, user_id=1, limit=10, db_path=db_file)
    assert len(alice_msgs) == 2
    assert all(m["username"] == "alice" for m in alice_msgs)

