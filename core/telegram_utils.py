import html
import re
from typing import Optional
from telegram import Message, Update
from telegram.constants import ChatType, ParseMode
from core.logger import setup_logger

logger = setup_logger("telegram_utils")


def is_bot_mentioned(
    update: Update,
    bot_username: Optional[str],
    bot_id: Optional[int],
) -> bool:
    """Checks whether the incoming message is directed at this bot.

    In private 1-on-1 chats, all messages are inherently directed to the bot.
    In group chats, the bot speaks ONLY if:
    1. The message text contains @bot_username or @@bot_username.
    2. The message is a direct reply to a previous message sent by the bot.
    """
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return False

    # In 1-on-1 private messages, user is always talking directly to the bot
    if chat.type == ChatType.PRIVATE:
        return True

    # Check if the message is a reply to one of the bot's messages
    if message.reply_to_message and message.reply_to_message.from_user:
        if bot_id is not None and message.reply_to_message.from_user.id == bot_id:
            return True

    # Check for text mentions of the bot's username (case-insensitive)
    if message.text and bot_username:
        normalized_name = bot_username.lstrip("@").lower()
        # Regex matches @username or @@username as a distinct token
        pattern = rf"@+{normalized_name}\b"
        if re.search(pattern, message.text, re.IGNORECASE):
            return True

    return False


def clean_bot_mention(text: str, bot_username: Optional[str]) -> str:
    """Removes bot mention tags (@username or @@username) from message text."""
    if not text:
        return ""

    if not bot_username:
        return text.strip()

    normalized_name = bot_username.lstrip("@")
    # Strip any occurrences of @username or @@username
    pattern = rf"@+{normalized_name}\b"
    cleaned = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return cleaned.strip()


def markdown_to_telegram_html(text: str) -> str:
    """Converts standard Markdown text into Telegram-supported HTML.

    Handles code blocks, inline code, bold, italics, strikethrough,
    headers, bullet lists, blockquotes, and links safely.
    """
    if not text:
        return ""

    # 1. Stash multiline code blocks so markdown symbols inside code are preserved
    code_blocks = []

    def stash_code_block(match: re.Match) -> str:
        code_blocks.append((match.group(1), match.group(2)))
        return f"TOKENBLOCK{len(code_blocks) - 1}ENDTOKEN"

    text = re.sub(r"```([a-zA-Z0-9_-]*)\n?(.*?)```", stash_code_block, text, flags=re.DOTALL)

    # 2. Stash inline code `...` and pre-existing <code>...</code> tags
    inline_codes = []

    def stash_inline_code(match: re.Match) -> str:
        inline_codes.append(match.group(1))
        return f"TOKENINLINE{len(inline_codes) - 1}ENDTOKEN"

    # Match pre-existing <code>...</code> first so raw HTML tags are not double-escaped
    text = re.sub(r"<code>(.*?)</code>", stash_inline_code, text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"`([^`\n]+)`", stash_inline_code, text)

    # 3. HTML-escape raw text (&, <, >) to prevent malformed HTML entities
    text = html.escape(text, quote=False)

    # 4. Convert Markdown headers (#, ##, ###) into bold text
    text = re.sub(r"(?m)^#{1,6}\s+(.+)$", r"<b>\1</b>", text)

    # 5. Convert blockquotes (> quote)
    text = re.sub(r"(?m)^>\s+(.+)$", r"<blockquote>\1</blockquote>", text)

    # 6. Convert bullet points (* item or - item) into clean bullet character
    text = re.sub(r"(?m)^[\*\-]\s+", "• ", text)

    # 7. Convert **bold** and __bold__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text, flags=re.DOTALL)

    # 8. Convert *italic* and _italic_ (boundary checks avoid mid-word snake_case)
    text = re.sub(r"(?<!\w)\*([^\*\n]+?)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"<i>\1</i>", text)

    # 9. Convert ~~strikethrough~~
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    # 10. Convert [text](url) links
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r'<a href="\2">\1</a>', text)

    # 11. Restore inline code with proper escaping
    for i, code in enumerate(inline_codes):
        escaped_code = html.escape(code, quote=False)
        text = text.replace(f"TOKENINLINE{i}ENDTOKEN", f"<code>{escaped_code}</code>")

    # 12. Restore code blocks with proper escaping
    for i, (lang, block_content) in enumerate(code_blocks):
        escaped_content = html.escape(block_content.strip("\n"), quote=False)
        if lang:
            escaped_lang = html.escape(lang.strip(), quote=False)
            block_html = f'<pre><code class="language-{escaped_lang}">{escaped_content}</code></pre>'
        else:
            block_html = f"<pre><code>{escaped_content}</code></pre>"
        text = text.replace(f"TOKENBLOCK{i}ENDTOKEN", block_html)

    return text.strip()


async def send_formatted_reply(
    message: Message,
    text: str,
    **kwargs,
) -> Message:
    """Delivers a reply formatted as Telegram HTML, falling back to plain text if needed."""
    html_text = markdown_to_telegram_html(text)
    try:
        return await message.reply_text(html_text, parse_mode=ParseMode.HTML, **kwargs)
    except Exception as exc:
        logger.warning(f"Telegram HTML rendering failed ({exc}); falling back to plain text.")
        return await message.reply_text(text, **kwargs)


def format_reply_with_model(text: str, model_name: Optional[str]) -> str:
    """Appends model attribution to the reply text if a model is specified.

    Separates the attribution by two newlines so Telegram renders it as a distinct footer.
    """
    if not model_name:
        return text
    return f"{text}\n\nМодель: {model_name}"

