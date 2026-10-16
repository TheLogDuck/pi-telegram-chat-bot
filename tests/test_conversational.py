# Unit tests for modules/conversational.py.
# Validates tag-only group enforcement, mention stripping, and offline LLM calls.
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Chat, Message, Update, User
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.ext import Application
from modules.conversational import (
    EMPTY_TAG_PROMPT,
    _dispatch_intent,
    clean_bot_mention,
    conversational_chat_handler,
    is_bot_mentioned,
    register_conversational,
)


def make_chat_update(
    chat_type: ChatType,
    text: str,
    reply_from_user_id: int = None,
) -> MagicMock:
    """Creates a mock Update with specified chat type, text, and reply structure."""
    update = MagicMock(spec=Update)
    chat = MagicMock(spec=Chat)
    chat.type = chat_type
    chat.id = 123456

    message = MagicMock(spec=Message)
    message.text = text
    message.reply_text = AsyncMock()

    if reply_from_user_id is not None:
        reply_user = MagicMock(spec=User)
        reply_user.id = reply_from_user_id
        reply_msg = MagicMock(spec=Message)
        reply_msg.from_user = reply_user
        message.reply_to_message = reply_msg
    else:
        message.reply_to_message = None

    update.effective_chat = chat
    update.effective_message = message
    return update


def test_is_bot_mentioned_private_chat() -> None:
    """Verifies that private direct messages are always considered addressed to the bot."""
    update = make_chat_update(ChatType.PRIVATE, "Привіт!")
    assert is_bot_mentioned(update, "my_bot", 999) is True


def test_is_bot_mentioned_group_untagged() -> None:
    """Verifies that untagged group messages are ignored."""
    update = make_chat_update(ChatType.GROUP, "Хтось знає відповідь?")
    assert is_bot_mentioned(update, "my_bot", 999) is False


def test_is_bot_mentioned_group_tagged_single_at() -> None:
    """Verifies tag recognition with standard @mention."""
    update = make_chat_update(ChatType.GROUP, "@my_bot розкажи жарт")
    assert is_bot_mentioned(update, "my_bot", 999) is True


def test_is_bot_mentioned_group_tagged_double_at() -> None:
    """Verifies tag recognition with double @@mention typo."""
    update = make_chat_update(ChatType.GROUP, "@@my_bot привіт")
    assert is_bot_mentioned(update, "my_bot", 999) is True


def test_is_bot_mentioned_group_reply_to_bot() -> None:
    """Verifies recognition when replying to a message previously sent by the bot."""
    bot_id = 999
    update = make_chat_update(ChatType.GROUP, "Дякую!", reply_from_user_id=bot_id)
    assert is_bot_mentioned(update, "my_bot", bot_id) is True


def test_clean_bot_mention() -> None:
    """Verifies that @bot and @@bot are cleanly stripped from prompt strings."""
    assert clean_bot_mention("@my_bot розкажи анекдот", "my_bot") == "розкажи анекдот"
    assert clean_bot_mention("@@my_bot що таке AI?", "my_bot") == "що таке AI?"
    assert clean_bot_mention("@my_bot", "my_bot") == ""
    assert clean_bot_mention("привіт @my_bot як ти?", "my_bot") == "привіт  як ти?"


def test_conversational_handler_ignores_untagged_group() -> None:
    """Verifies that the handler stays silent when a group message is not tagged."""
    update = make_chat_update(ChatType.GROUP, "Звичайне повідомлення")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    update.effective_message.reply_text.assert_not_called()
    context.bot.send_chat_action.assert_not_called()


def test_conversational_handler_empty_tag_greeting() -> None:
    """Verifies that tagging the bot with no query returns the greeting prompt."""
    update = make_chat_update(ChatType.GROUP, "@my_bot")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    update.effective_message.reply_text.assert_awaited_once_with(
        EMPTY_TAG_PROMPT,
        parse_mode=ParseMode.HTML,
    )


@patch("modules.conversational.generate_response", new_callable=AsyncMock)
def test_conversational_handler_tagged_generates_ai_response(mock_generate: AsyncMock) -> None:
    """Verifies typing action and Gemini generation with model attribution."""
    mock_generate.return_value = ("Це чудове запитання про науку.", "gemini-3.8-flash")
    update = make_chat_update(ChatType.GROUP, "@my_bot розкажи про зорі")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999
    context.bot.send_chat_action = AsyncMock()

    asyncio.run(conversational_chat_handler(update, context))

    context.bot.send_chat_action.assert_awaited_once_with(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )
    assert mock_generate.await_args.args[0] == "розкажи про зорі"
    assert mock_generate.await_args.kwargs.get("persona_key") == "standard"
    update.effective_message.reply_text.assert_awaited_once_with(
        "Це чудове запитання про науку.\n\ngemini-3.8-flash",
        parse_mode=ParseMode.HTML,
    )


def test_conversational_handler_dispatches_ping_intent() -> None:
    """Verifies that tagging the bot with 'пінг' or 'пинг' routes to ping_command."""
    from modules.commands import PING_TEXT

    update = make_chat_update(ChatType.GROUP, "@my_bot пінг")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    update.effective_message.reply_text.assert_awaited_once_with(
        PING_TEXT,
        parse_mode=ParseMode.HTML,
    )


def test_conversational_handler_dispatches_help_intent() -> None:
    """Verifies that tagging the bot with 'допомога' routes to help_command."""
    from modules.commands import HELP_TEXT

    update = make_chat_update(ChatType.GROUP, "@my_bot допомога")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    update.effective_message.reply_text.assert_awaited_once_with(
        HELP_TEXT,
        parse_mode=ParseMode.HTML,
    )


@patch("modules.conversational.news_command", new_callable=AsyncMock)
def test_conversational_handler_dispatches_news_intent(mock_news: AsyncMock) -> None:
    """Verifies that tagging the bot with 'новини про космос' routes to news_command with topic."""
    update = make_chat_update(ChatType.GROUP, "@my_bot новини про космос")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    mock_news.assert_awaited_once_with(update, context, topic="космос")


@patch("modules.conversational.roast_command", new_callable=AsyncMock)
def test_conversational_handler_dispatches_roast_intent(mock_roast: AsyncMock) -> None:
    """Verifies that tagging the bot with 'просмаж @alex' routes to roast_command."""
    update = make_chat_update(ChatType.GROUP, "@my_bot просмаж @alex")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    mock_roast.assert_awaited_once_with(update, context, target_user="@alex")


@patch("modules.conversational.meme_command", new_callable=AsyncMock)
def test_conversational_handler_dispatches_meme_intent(mock_meme: AsyncMock) -> None:
    """Verifies that tagging the bot with 'мем про програмування' routes to meme_command."""
    update = make_chat_update(ChatType.GROUP, "@my_bot мем про програмування")
    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    mock_meme.assert_awaited_once_with(update, context, prompt="програмування")


@patch("modules.conversational.language_command", new_callable=AsyncMock)
def test_dispatch_intent_language_and_chat_fallback(mock_language: AsyncMock) -> None:
    """Verifies that _dispatch_intent handles LANGUAGE and returns False for CHAT."""
    from modules.intent import IntentResult, IntentType

    update = make_chat_update(ChatType.PRIVATE, "/lang")
    context = MagicMock()

    # Handled intent returns True
    res_lang = IntentResult(intent=IntentType.LANGUAGE, confidence=1.0)
    handled = asyncio.run(_dispatch_intent(res_lang, update, context))
    assert handled is True
    mock_language.assert_awaited_once_with(update, context)

    # General chat intent returns False (falls through to AI conversation)
    res_chat = IntentResult(intent=IntentType.CHAT, confidence=1.0)
    handled_chat = asyncio.run(_dispatch_intent(res_chat, update, context))
    assert handled_chat is False


def test_register_conversational() -> None:
    """Verifies that register_conversational adds a message handler in group 0."""
    mock_app = MagicMock(spec=Application)
    register_conversational(mock_app)
    mock_app.add_handler.assert_called_once()
    assert mock_app.add_handler.call_args[1]["group"] == 0


@patch("modules.conversational.generate_response", new_callable=AsyncMock)
def test_conversational_handler_user_rate_limited(mock_generate: AsyncMock) -> None:
    """Verifies that subsequent prompts within cooldown window are rejected."""
    from core.languages import get_localized_string
    from core.rate_limiter import get_rate_limiter

    limiter = get_rate_limiter()
    limiter._user_last_request.clear()

    update = make_chat_update(ChatType.GROUP, "@my_bot перше запитання")
    update.effective_message.from_user = MagicMock()
    update.effective_message.from_user.id = 77777

    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999
    context.bot.send_chat_action = AsyncMock()

    # First prompt passes
    mock_generate.return_value = ("Відповідь 1", "gemini-3.8-flash")
    asyncio.run(conversational_chat_handler(update, context))
    assert mock_generate.await_count == 1

    # Immediate second prompt from same user must be blocked by cooldown
    update2 = make_chat_update(ChatType.GROUP, "@my_bot друге запитання")
    update2.effective_message.from_user = MagicMock()
    update2.effective_message.from_user.id = 77777

    asyncio.run(conversational_chat_handler(update2, context))
    # generate_response should NOT have been called a second time
    assert mock_generate.await_count == 1
    expected_notice = get_localized_string("rate_limit_user", "uk")
    update2.effective_message.reply_text.assert_awaited_once_with(expected_notice)


@patch("modules.conversational.generate_response", new_callable=AsyncMock)
def test_conversational_handler_chat_concurrency_limited(mock_generate: AsyncMock) -> None:
    """Verifies that requests exceeding chat concurrency limit are rejected."""
    from core.languages import get_localized_string
    from core.rate_limiter import get_rate_limiter

    limiter = get_rate_limiter()
    limiter._user_last_request.clear()
    limiter._chat_active_tasks.clear()

    # Manually fill chat capacity
    chat_id = 123456
    limiter._chat_active_tasks[chat_id] = limiter.max_chat_concurrency

    update = make_chat_update(ChatType.GROUP, "@my_bot запитання при зайнятому чаті")
    update.effective_message.from_user = MagicMock()
    update.effective_message.from_user.id = 88888

    context = MagicMock()
    context.bot.username = "my_bot"
    context.bot.id = 999

    asyncio.run(conversational_chat_handler(update, context))

    # Gemini must not have been called
    mock_generate.assert_not_called()
    expected_notice = get_localized_string("rate_limit_chat", "uk")
    update.effective_message.reply_text.assert_awaited_once_with(expected_notice)

