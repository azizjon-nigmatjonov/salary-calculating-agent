# Salary Agent — Claude Code Build Prompt (Conversational)

> Paste this entire prompt into Claude Code (terminal or VS Code extension) to scaffold the full project.

---

## Project overview

Build a local Python Telegram bot that acts as a **conversational AI assistant** for managing worker salaries.

The bot must:
- Hold a **real back-and-forth conversation** with the user via Telegram (text and voice)
- Receive voice notes → transcribe with Whisper (offline) → respond naturally via Ollama
- Understand salary commands buried in natural speech: add, subtract, get balance, list workers, show history
- Reply in the **same language the user spoke** (auto-detected by Whisper — supports Uzbek, Russian, English)
- Remember the **last 10 messages** of the conversation per user (in-memory, per chat_id) so context carries across messages
- Execute salary operations against a local JSON database and weave the result into its natural reply
- Never reply with raw JSON or robotic templates — always reply as a friendly assistant would

Everything runs on the local machine. No external AI APIs — only the Telegram Bot API for messaging.

---

## Folder structure to create

```
salary-agent/
├── bot.py              # Telegram bot entrypoint + handlers
├── transcriber.py      # Whisper audio-to-text
├── agent.py            # Conversational AI core (Ollama, memory, tool routing)
├── tools.py            # Salary tool functions called by the agent
├── data.py             # JSON salary storage layer
├── config.py           # BOT_TOKEN, model names, paths
├── salaries.json       # Auto-created on first run
├── requirements.txt    # All pip dependencies
├── run.sh              # One-command startup script
└── README.md           # Setup + usage instructions
```

---

## Implementation instructions

---

### 1. `config.py`

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"   # user fills this in
OLLAMA_MODEL = "llama3.2"           # or any model the user has pulled
WHISPER_MODEL = "small"             # base | small | medium
DB_FILE = "salaries.json"
AUDIO_TMP_DIR = "/tmp"
CONVERSATION_HISTORY_LIMIT = 10     # messages to keep per user
```

---

### 2. `data.py` — salary storage

Pure module, no Telegram or AI imports.

Implement these functions backed by `salaries.json`:

- `load_db() -> dict`
- `save_db(db: dict)`
- `add_salary(worker: str, amount: float) -> dict` — add to balance, append timestamped history entry, return worker record
- `subtract_salary(worker: str, amount: float) -> dict` — subtract, append history, return worker record
- `get_salary(worker: str) -> dict | None`
- `list_all_workers() -> dict` — returns full db
- `get_history(worker: str, limit: int = 10) -> list` — return last N history entries for worker

Worker record shape:
```json
{
  "balance": 0,
  "history": [
    { "action": "add", "amount": 500000, "timestamp": "2024-01-01T12:00:00" }
  ]
}
```

Always lowercase worker names. Always timestamp history entries in ISO format.

---

### 3. `transcriber.py` — Whisper STT

- Load Whisper model once at module level using `config.WHISPER_MODEL`
- `transcribe_audio(ogg_path: str) -> str`:
  1. Convert `.ogg` → `.wav` via ffmpeg subprocess
  2. Transcribe with `model.transcribe(wav_path)` — no `language=` param (auto-detect)
  3. Delete both temp files
  4. Return `result["text"].strip()`
- Raise a clear RuntimeError if ffmpeg is missing

---

### 4. `tools.py` — salary tool functions

This module exposes clean tool functions that the agent calls after deciding what to do.

Each function takes already-parsed arguments and returns a **plain English result string** (not JSON) that the agent will weave into its reply.

```python
def tool_add(worker: str, amount: float) -> str:
    """Add amount to worker salary. Returns human-readable result."""

def tool_subtract(worker: str, amount: float) -> str:
    """Subtract amount from worker salary. Returns human-readable result."""

def tool_get(worker: str) -> str:
    """Get current balance for a worker. Returns human-readable result."""

def tool_list() -> str:
    """List all workers and their balances. Returns formatted list."""

def tool_history(worker: str) -> str:
    """Get last 10 transactions for a worker. Returns formatted history."""
```

Example return values (the agent uses these as context, not verbatim):
- `tool_add("ali", 500000)` → `"Ali's balance updated: added 500,000. New balance: 2,000,000."`
- `tool_get("bobur")` → `"Bobur's current balance is 1,500,000."`
- `tool_list()` → `"Workers: Ali (2,000,000), Bobur (1,500,000), Kamol (800,000)"`

---

### 5. `agent.py` — conversational AI core

This is the brain. It manages conversation memory and runs a **two-step Ollama pipeline**:

#### Conversation memory

```python
# In-memory store: { chat_id: [ {role, content}, ... ] }
conversation_history: dict[int, list] = {}

def get_history(chat_id: int) -> list:
    """Return conversation history for this chat, init if missing."""

def add_to_history(chat_id: int, role: str, content: str):
    """Append message to history, trim to last CONVERSATION_HISTORY_LIMIT messages."""

def clear_history(chat_id: int):
    """Reset conversation for this chat."""
```

#### Two-step pipeline: `process_message(chat_id: int, user_text: str) -> str`

**Step 1 — Intent extraction (structured JSON output)**

Call Ollama with this system prompt:

```
You are a salary management AI assistant. Your job is to understand what the user wants and extract a structured command.

Analyze the user message and return ONLY valid JSON:
{
  "action": "add" | "subtract" | "get" | "list" | "history" | "chat",
  "worker": "name in lowercase or null",
  "amount": number or null,
  "language": "en" | "ru" | "uz" | "other"
}

Use "chat" for greetings, questions, or anything not related to salary operations.
Detect the language of the user's message and put it in "language".

Examples:
"500 ming qo'sh Aliga" → {"action":"add","worker":"ali","amount":500000,"language":"uz"}
"Добавь 200000 Бобуру" → {"action":"add","worker":"bobur","amount":200000,"language":"ru"}
"What is Kamol's balance?" → {"action":"get","worker":"kamol","amount":null,"language":"en"}
"Show all workers" → {"action":"list","worker":null,"amount":null,"language":"en"}
"Hi, how are you?" → {"action":"chat","worker":null,"amount":null,"language":"en"}
```

Pass ONLY the latest user message (not full history) to this step.
Parse the JSON response. On parse failure, default to `{"action":"chat",...}`.

**Step 2 — Conversational response generation**

- If action is a salary operation: call the appropriate `tools.py` function, get the result string
- Build the messages array for Ollama: system prompt + full conversation history + tool result injected as a system note

System prompt for Step 2:
```
You are a friendly and efficient salary management assistant. You help managers track and update worker salaries.

Rules:
- Always reply in the same language the user wrote in (detected language: {language})
- Be warm, natural, and concise — like a helpful colleague, not a robot
- If a salary operation was performed, confirm it clearly and state the new balance
- If the user is just chatting, respond naturally and briefly
- Never show raw JSON, never use template-style responses
- Keep replies short — 1 to 3 sentences maximum
- You have memory of this conversation, so refer back to context naturally if relevant
```

Build messages:
```python
messages = [
    {"role": "system", "content": system_prompt},
    *conversation_history[chat_id],   # last N messages
]
# If a tool was called, inject result before generating reply:
if tool_result:
    messages.append({
        "role": "system", 
        "content": f"Tool result (use this to form your reply): {tool_result}"
    })
messages.append({"role": "user", "content": user_text})
```

Call `ollama.chat()` and return `response["message"]["content"]`.

After getting the reply:
- Add user message to history
- Add assistant reply to history

---

### 6. `bot.py` — Telegram bot

Use `python-telegram-bot` v20+ async API.

**Handlers:**

`handle_voice(update, context)`:
1. Download voice file to `/tmp/voice_{file_id}.ogg`
2. Send typing action: `await context.bot.send_chat_action(..., ChatAction.TYPING)`
3. Transcribe with `transcribe_audio()`
4. Show what was heard: `🎙 _"{transcribed_text}"_` (italic Markdown)
5. Call `agent.process_message(chat_id, transcribed_text)`
6. Send agent reply

`handle_text(update, context)`:
1. Send typing action
2. Call `agent.process_message(chat_id, update.message.text)`
3. Send agent reply

`handle_start(update, context)`:
- Clear conversation history for this chat_id
- Send a friendly welcome message that explains what the bot can do, in a conversational tone (not a feature list)
- Example: *"Hey! I'm your salary assistant. Just tell me what you need — you can add or subtract from someone's salary, check their balance, or ask to see all workers. Voice or text, your choice!"*

`handle_reset(update, context)` — /reset command:
- Clear history for this chat
- Reply: *"Fresh start! What do you need?"*

**Error handling:** Every handler wrapped in try/except. On error send a friendly message, never crash. Log with timestamps.

---

### 7. `requirements.txt`

```
python-telegram-bot==20.7
openai-whisper
ollama
requests
```

---

### 8. `run.sh`

```bash
#!/bin/bash
echo "Starting Salary Agent..."
ollama serve &>/dev/null &
sleep 2
python bot.py
```

Make executable: `chmod +x run.sh`

---

### 9. `README.md`

Write a README with these sections:

**What this bot does** — explain it in 3 sentences as if for a non-technical manager

**Prerequisites:**
- Python 3.10+
- ffmpeg (`brew install ffmpeg` / `apt install ffmpeg`)
- Ollama (`brew install ollama` / https://ollama.com)
- Telegram bot token from @BotFather

**Setup:**
1. `pip install -r requirements.txt`
2. Edit `config.py` → paste BOT_TOKEN
3. `ollama pull llama3.2`
4. `./run.sh`

**Example conversations** — show 3 realistic multi-turn conversations in English, Russian, and Uzbek that demonstrate memory working across messages

**Commands:**
- `/start` — welcome + reset memory
- `/reset` — clear conversation history

**Troubleshooting** — ffmpeg missing, Ollama not running, wrong token

---

## Conversation memory behavior

- Memory is **per chat_id**, stored in a Python dict (in-memory, resets on bot restart)
- Keep last `CONVERSATION_HISTORY_LIMIT` messages (default 10) to avoid Ollama context overflow
- `/start` and `/reset` both clear the memory for that chat
- Memory allows the user to say things like:
  - *"Now do the same for Kamol"* (agent remembers the previous amount)
  - *"How about his history?"* (agent remembers who "his" refers to)
  - *"Undo that"* (agent understands what was last done)

---

## Language behavior

- Whisper auto-detects the spoken language — no configuration needed
- The intent extractor identifies the language and passes it to the response generator
- The response generator is instructed to reply in the same language
- This means: user speaks Uzbek → bot replies in Uzbek. User switches to Russian mid-conversation → bot switches too

---

## Code quality requirements

- All functions must have docstrings and type hints
- `data.py` and `tools.py` must be pure (no Telegram, Whisper, or Ollama imports)
- `agent.py` must not import from `bot.py`
- Each file must be independently importable and testable
- No hardcoded strings in `bot.py` — all config from `config.py`

---

## After generating all files

1. Run `pip install -r requirements.txt` — confirm no errors
2. Run `python -c "import bot; import agent; import tools; import data"` — confirm clean imports
3. Create `salaries.json` with two test workers:
```json
{
  "ali": { "balance": 1500000, "history": [{"action": "add", "amount": 1500000, "timestamp": "2024-01-01T09:00:00"}] },
  "bobur": { "balance": 2000000, "history": [{"action": "add", "amount": 2000000, "timestamp": "2024-01-01T09:00:00"}] }
}
```
4. Print a summary of all files with line counts
