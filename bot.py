"""Telegram bot entrypoint and message handlers."""

from __future__ import annotations

import truststore

truststore.inject_into_ssl()

import logging
import os
from datetime import datetime

import certifi
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

import agent
import config
import transcriber

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "Hey! I'm your salary assistant. Just tell me what you need — register workers, "
    "add bonuses or advances, calculate net salary, or check everyone's status. "
    "Voice or text, your choice!"
)

ERROR_MESSAGE = "Something went wrong on my end. Please try again in a moment."


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome new users and reset conversation memory."""
    try:
        chat_id = update.effective_chat.id
        agent.clear_history(chat_id)
        await update.message.reply_text(WELCOME_MESSAGE)
    except Exception:
        logger.exception("handle_start failed at %s", datetime.now().isoformat())
        await update.message.reply_text(ERROR_MESSAGE)


async def handle_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset conversation history for this chat."""
    try:
        chat_id = update.effective_chat.id
        agent.clear_history(chat_id)
        await update.message.reply_text("Fresh start! What do you need?")
    except Exception:
        logger.exception("handle_reset failed at %s", datetime.now().isoformat())
        await update.message.reply_text(ERROR_MESSAGE)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    try:
        chat_id = update.effective_chat.id
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        reply = agent.process_message(chat_id, update.message.text)
        await update.message.reply_text(reply)
    except Exception:
        logger.exception("handle_text failed at %s", datetime.now().isoformat())
        await update.message.reply_text(ERROR_MESSAGE)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice messages: transcribe then process."""
    ogg_path = ""
    try:
        chat_id = update.effective_chat.id
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
        await update.message.reply_text(ERROR_MESSAGE)
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("Salary Agent bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
