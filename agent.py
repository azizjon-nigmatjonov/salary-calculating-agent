"""Conversational AI core with Ollama intent extraction and response generation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import ollama

import config
import languages
import registration
import tools
import uzbek_commands
import uzbek_commands

logger = logging.getLogger(__name__)

conversation_history: dict[int, list[dict[str, str]]] = {}

INTENT_SYSTEM_PROMPT = """You are a salary management AI assistant. Your job is to understand what the user wants and extract a structured command.

Analyze the user message and return ONLY valid JSON:
{
  "action": "register" | "update" | "add_bonus" | "add_advance" | "add_penalty" | "delete_worker" | "payout" | "calculate" | "get" | "list" | "history" | "chat",
  "worker": "name slug in lowercase or null",
  "full_name": "string or null",
  "job_started_date": "YYYY-MM-DD or null",
  "birthdate": "YYYY-MM-DD or null",
  "fixed_salary": number or null,
  "amount": number or null,
  "note": "string or null",
  "period": "YYYY-MM or null",
  "language": "en" | "ru" | "uz" | "other"
}

Use "chat" for greetings, questions, or anything not related to salary operations.
Detect the language of the user's message and put it in "language".
Infer missing worker or amount from recent conversation context when the user says things like "him", "the same", or "do that for Kamol".

Examples:
"Register Ali Karimov, started 2024-03-01, born 1990-05-15, salary 5 million" → {"action":"register","worker":null,"full_name":"Ali Karimov","job_started_date":"2024-03-01","birthdate":"1990-05-15","fixed_salary":5000000,"amount":null,"note":null,"period":null,"language":"en"}
"Add a new worker" → {"action":"register","worker":null,"full_name":null,"job_started_date":null,"birthdate":null,"fixed_salary":null,"amount":null,"note":null,"period":null,"language":"en"}
"Register new worker, Bobur, age 22, salary 5 mln" → {"action":"register","worker":null,"full_name":"Bobur","job_started_date":null,"birthdate":null,"fixed_salary":5000000,"amount":null,"note":null,"period":null,"language":"en"}
"Yangi ishchi qo'sh" → {"action":"register","worker":null,"full_name":null,"job_started_date":null,"birthdate":null,"fixed_salary":null,"amount":null,"note":null,"period":null,"language":"uz"}
"Yangi ishchi qosh" → {"action":"register","worker":null,"full_name":null,"job_started_date":null,"birthdate":null,"fixed_salary":null,"amount":null,"note":null,"period":null,"language":"uz"}
"Ishchini o'zchirib tashla" → {"action":"delete_worker","worker":null,"full_name":null,"job_started_date":null,"birthdate":null,"fixed_salary":null,"amount":null,"note":null,"period":null,"language":"uz"}
"avans berdim" → {"action":"add_advance","worker":null,"full_name":null,"job_started_date":null,"birthdate":null,"fixed_salary":null,"amount":null,"note":null,"period":null,"language":"uz"}
"Shtraf soldim" → {"action":"add_penalty","worker":null,"full_name":null,"job_started_date":null,"birthdate":null,"fixed_salary":null,"amount":null,"note":null,"period":null,"language":"uz"}
"500 ming bonus qo'sh Aliga" → {"action":"add_bonus","worker":"ali","full_name":null,"job_started_date":null,"birthdate":null,"fixed_salary":null,"amount":500000,"note":null,"period":null,"language":"uz"}
"Добавь аванс 200000 Бобуру" → {"action":"add_advance","worker":"bobur","full_name":null,"job_started_date":null,"birthdate":null,"fixed_salary":null,"amount":200000,"note":null,"period":null,"language":"ru"}
"Calculate Kamol's salary for March 2025" → {"action":"calculate","worker":"kamol","full_name":null,"job_started_date":null,"birthdate":null,"fixed_salary":null,"amount":null,"note":null,"period":"2025-03","language":"en"}
"Show all workers" → {"action":"list","worker":null,"full_name":null,"job_started_date":null,"birthdate":null,"fixed_salary":null,"amount":null,"note":null,"period":null,"language":"en"}
"Hi, how are you?" → {"action":"chat","worker":null,"full_name":null,"job_started_date":null,"birthdate":null,"fixed_salary":null,"amount":null,"note":null,"period":null,"language":"en"}
"""

DEFAULT_INTENT: dict[str, Any] = {
    "action": "chat",
    "worker": None,
    "full_name": None,
    "job_started_date": None,
    "birthdate": None,
    "fixed_salary": None,
    "amount": None,
    "note": None,
    "period": None,
    "language": "en",
}


def get_history(chat_id: int) -> list[dict[str, str]]:
    """Return conversation history for this chat, init if missing."""
    if chat_id not in conversation_history:
        conversation_history[chat_id] = []
    return conversation_history[chat_id]


def add_to_history(chat_id: int, role: str, content: str) -> None:
    """Append message to history, trim to last CONVERSATION_HISTORY_LIMIT messages."""
    history = get_history(chat_id)
    history.append({"role": role, "content": content})
    if len(history) > config.CONVERSATION_HISTORY_LIMIT:
        conversation_history[chat_id] = history[-config.CONVERSATION_HISTORY_LIMIT :]


def clear_history(chat_id: int) -> None:
    """Reset conversation for this chat."""
    conversation_history[chat_id] = []
    registration.clear_session(chat_id)
    uzbek_commands.clear_session(chat_id)


def get_chat_language(chat_id: int, user_text: str = "") -> str:
    """Return preferred language for chat, with fallbacks."""
    saved = languages.get_language(chat_id)
    if saved:
        return saved
    if user_text:
        return registration.detect_language(user_text)
    return "en"


def _extract_json(text: str) -> dict[str, Any]:
    """Parse JSON from Ollama response, with regex fallback."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return dict(DEFAULT_INTENT)


def _extract_intent(chat_id: int, user_text: str) -> dict[str, Any]:
    """Step 1: extract structured intent from user message."""
    context_lines: list[str] = []
    for msg in get_history(chat_id)[-4:]:
        context_lines.append(f"{msg['role']}: {msg['content']}")
    context_block = "\n".join(context_lines) if context_lines else "(no prior context)"

    prompt = (
        f"Recent conversation:\n{context_block}\n\n"
        f"Latest user message: {user_text}"
    )

    try:
        response = ollama.chat(
            model=config.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        intent = _extract_json(response["message"]["content"])
        for key, default in DEFAULT_INTENT.items():
            intent.setdefault(key, default)
        return intent
    except Exception as exc:
        logger.exception("Intent extraction failed: %s", exc)
        return dict(DEFAULT_INTENT)


def _dispatch_tool(intent: dict[str, Any]) -> str | None:
    """Run the appropriate salary tool based on extracted intent."""
    action = intent.get("action", "chat")
    if action == "chat":
        return None

    worker = intent.get("worker")
    amount = intent.get("amount")
    note = intent.get("note") or ""

    if action == "register":
        full_name = intent.get("full_name")
        job_started = intent.get("job_started_date")
        birthdate = intent.get("birthdate")
        fixed = intent.get("fixed_salary")
        if not all([full_name, job_started, birthdate, fixed]):
            return "Missing registration details: need full name, job start date, birthdate, and fixed salary."
        return tools.tool_register_worker(full_name, job_started, birthdate, float(fixed))

    if action == "update":
        if not worker:
            return "Which worker should I update?"
        fields = {
            k: intent.get(k)
            for k in ("full_name", "job_started_date", "birthdate", "fixed_salary")
            if intent.get(k) is not None
        }
        return tools.tool_update_worker(worker, **fields)

    if action == "add_bonus":
        if not worker or amount is None:
            return "Need a worker name and bonus amount."
        return tools.tool_add_bonus(worker, float(amount), note)

    if action == "add_advance":
        if not worker or amount is None:
            return "Need a worker name and advance amount."
        return tools.tool_add_advance(worker, float(amount), note)

    if action == "add_penalty":
        if not worker or amount is None:
            return "Need a worker name and penalty amount."
        return tools.tool_add_penalty(worker, float(amount), note)

    if action == "delete_worker":
        if not worker:
            return "Which worker should be removed?"
        return tools.tool_delete_worker(worker)

    if action == "payout":
        if not worker or amount is None:
            return "Need a worker name and payout amount."
        return tools.tool_record_payout(worker, float(amount), intent.get("period"))

    if action == "calculate":
        if not worker:
            return "Which worker's salary should I calculate?"
        return tools.tool_calculate_salary(worker, intent.get("period"))

    if action == "get":
        if not worker:
            return "Which worker should I look up?"
        return tools.tool_get_worker(worker)

    if action == "list":
        return tools.tool_list()

    if action == "history":
        if not worker:
            return "Which worker's history should I show?"
        return tools.tool_history(worker)

    return None


def _generate_reply(
    chat_id: int,
    user_text: str,
    language: str,
    tool_result: str | None,
) -> str:
    """Step 2: generate conversational reply via Ollama."""
    system_prompt = f"""You are a friendly and efficient salary management assistant. You help managers track and update worker salaries.

Rules:
- Always reply in the same language the user wrote in (detected language: {language})
- Be warm, natural, and concise — like a helpful colleague, not a robot
- If a salary operation was performed, confirm it clearly and state key numbers
- If the user is just chatting, respond naturally and briefly
- Never show raw JSON, never use template-style responses
- Keep replies short — 1 to 3 sentences maximum
- You have memory of this conversation, so refer back to context naturally if relevant
"""

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages.extend(get_history(chat_id))

    if tool_result:
        messages.append(
            {
                "role": "system",
                "content": f"Tool result (use this to form your reply): {tool_result}",
            }
        )
    messages.append({"role": "user", "content": user_text})

    response = ollama.chat(model=config.OLLAMA_MODEL, messages=messages)
    return response["message"]["content"].strip()


def _offline_fallback(chat_id: int, tool_result: str | None) -> str:
    """Return a helpful reply when Ollama is unavailable."""
    if tool_result:
        return tool_result
    lang = languages.get_language(chat_id) or "en"
    messages = {
        "en": "Sorry, I had trouble processing that. Please try again.",
        "ru": "Не удалось обработать запрос. Попробуйте ещё раз.",
        "uz": "So'rovni qayta ishlashda muammo bo'ldi. Qayta urinib ko'ring.",
    }
    return messages.get(lang, messages["en"])


def process_message(chat_id: int, user_text: str) -> str:
    """Process user message through two-step pipeline and return assistant reply."""
    user_text = registration.normalize_user_text(user_text)
    wizard_reply = registration.handle_message(chat_id, user_text)
    if wizard_reply is not None:
        add_to_history(chat_id, "user", user_text)
        add_to_history(chat_id, "assistant", wizard_reply)
        return wizard_reply

    uz_reply = uzbek_commands.handle_message(chat_id, user_text)
    if uz_reply is not None:
        add_to_history(chat_id, "user", user_text)
        add_to_history(chat_id, "assistant", uz_reply)
        return uz_reply

    language = (
        languages.get_language(chat_id) or registration.detect_language(user_text)
    )

    uz_start = uzbek_commands.try_start(chat_id, user_text, language)
    if uz_start:
        add_to_history(chat_id, "user", user_text)
        add_to_history(chat_id, "assistant", uz_start)
        return uz_start

    if registration.wants_to_start(user_text):
        quick_intent = dict(DEFAULT_INTENT)
        quick_intent.update({"action": "register", "language": language})
        wizard_start = registration.try_start_from_intent(
            chat_id, user_text, quick_intent
        )
        if wizard_start is not None:
            add_to_history(chat_id, "user", user_text)
            add_to_history(chat_id, "assistant", wizard_start)
            return wizard_start

    intent = _extract_intent(chat_id, user_text)
    language = languages.get_language(chat_id) or intent.get("language") or language

    wizard_start = registration.try_start_from_intent(chat_id, user_text, intent)
    if wizard_start is not None:
        add_to_history(chat_id, "user", user_text)
        add_to_history(chat_id, "assistant", wizard_start)
        return wizard_start

    tool_result = _dispatch_tool(intent)

    try:
        reply = _generate_reply(chat_id, user_text, language, tool_result)
    except Exception as exc:
        logger.exception("Reply generation failed: %s", exc)
        reply = _offline_fallback(chat_id, tool_result)

    add_to_history(chat_id, "user", user_text)
    add_to_history(chat_id, "assistant", reply)
    return reply
