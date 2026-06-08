"""Telegram bot entrypoint and message handlers."""

from __future__ import annotations

import truststore

truststore.inject_into_ssl()

import logging
import os
from datetime import datetime

import certifi
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

import agent
import config
import languages
import transcriber

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

ERROR_MESSAGES = {
    "en": "Something went wrong on my end. Please try again in a moment.",
    "ru": "Что-то пошло не так. Попробуйте ещё раз через минуту.",
    "uz": "Nimadir xato bo'ldi. Birozdan keyin qayta urinib ko'ring.",
}


def _error_message(chat_id: int) -> str:
    """Return localized error message."""
    return ERROR_MESSAGES.get(languages.get_language(chat_id) or "en", ERROR_MESSAGES["en"])


def _language_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for language selection."""
    buttons = [
        InlineKeyboardButton(languages.BUTTON_LABELS[code], callback_data=f"lang_{code}")
        for code in languages.SUPPORTED
    ]
    return InlineKeyboardMarkup([buttons])


async def _ask_language(update: Update) -> None:
    """Send language selection prompt with buttons."""
    chat_id = update.effective_chat.id
    languages.start_language_selection(chat_id)
    await update.message.reply_text(
        languages.t(chat_id, "choose_language", lang="en"),
        reply_markup=_language_keyboard(),
    )


async def _confirm_language(chat_id: int, language: str, message) -> None:
    """Save language and send welcome message."""
    languages.set_language(chat_id, language)
    await message.reply_text(languages.t(chat_id, "language_set", lang=language))
    await message.reply_text(languages.t(chat_id, "welcome", lang=language))


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset session and ask user to choose language."""
    try:
        chat_id = update.effective_chat.id
        agent.clear_history(chat_id)
        languages.clear_language(chat_id)
        await _ask_language(update)
    except Exception:
        logger.exception("handle_start failed at %s", datetime.now().isoformat())
        await update.message.reply_text(_error_message(update.effective_chat.id))


async def handle_language_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle inline language button press."""
    try:
        query = update.callback_query
        await query.answer()
        chat_id = query.message.chat_id
        language = query.data.removeprefix("lang_")
        if language not in languages.SUPPORTED:
            return
        agent.clear_history(chat_id)
        await _confirm_language(chat_id, language, query.message)
    except Exception:
        logger.exception("handle_language_callback failed at %s", datetime.now().isoformat())
        if update.callback_query:
            await update.callback_query.message.reply_text(
                _error_message(update.callback_query.message.chat_id)
            )


async def handle_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset conversation history for this chat."""
    try:
        chat_id = update.effective_chat.id
        agent.clear_history(chat_id)
        await update.message.reply_text(languages.t(chat_id, "reset"))
    except Exception:
        logger.exception("handle_reset failed at %s", datetime.now().isoformat())
        await update.message.reply_text(_error_message(update.effective_chat.id))


async def _handle_language_text(chat_id: int, text: str, message) -> bool:
    """
    Handle text reply while awaiting language selection.

    Returns True if handled.
    """
    if not languages.is_awaiting_language(chat_id):
        return False

    language = languages.parse_language_choice(text)
    if language is None:
        await message.reply_text(
            languages.t(chat_id, "invalid_language", lang="en"),
            reply_markup=_language_keyboard(),
        )
        return True

    await _confirm_language(chat_id, language, message)
    return True


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    try:
        chat_id = update.effective_chat.id
        text = update.message.text

        if await _handle_language_text(chat_id, text, update.message):
            return

        if languages.is_awaiting_language(chat_id):
            await _ask_language(update)
            return

        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        reply = agent.process_message(chat_id, text)
        await update.message.reply_text(reply)
    except Exception:
        logger.exception("handle_text failed at %s", datetime.now().isoformat())
        await update.message.reply_text(_error_message(update.effective_chat.id))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice messages: transcribe then process."""
    ogg_path = ""
    try:
        chat_id = update.effective_chat.id

        if languages.is_awaiting_language(chat_id):
            lang = "en"
            await update.message.reply_text(
                languages.t(chat_id, "invalid_language", lang=lang),
                reply_markup=_language_keyboard(),
            )
            return

        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)

        ogg_path = os.path.join(config.AUDIO_TMP_DIR, f"voice_{voice.file_id}.ogg")
        await file.download_to_drive(ogg_path)

        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        transcribed = transcriber.transcribe_audio(ogg_path)
        ogg_path = ""

        await update.message.reply_text(
            f'🎙 _"{transcribed}"_',
            parse_mode=ParseMode.MARKDOWN,
        )

        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        reply = agent.process_message(chat_id, transcribed)
        await update.message.reply_text(reply)
    except RuntimeError as exc:
        logger.exception("handle_voice transcription error at %s", datetime.now().isoformat())
        await update.message.reply_text(str(exc))
    except Exception:
        logger.exception("handle_voice failed at %s", datetime.now().isoformat())
        await update.message.reply_text(_error_message(update.effective_chat.id))
    finally:
        if ogg_path and os.path.exists(ogg_path):
            try:
                os.remove(ogg_path)
            except OSError:
                pass


def main() -> None:
    """Start the Telegram bot."""
    if not config.BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN is not set. Copy .env.example to .env and add your token."
        )

    http_request = HTTPXRequest(httpx_kwargs={"verify": certifi.where()})
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .request(http_request)
        .get_updates_request(http_request)
        .build()
    )
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("reset", handle_reset))
    app.add_handler(CallbackQueryHandler(handle_language_callback, pattern=r"^lang_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("Salary Agent bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
