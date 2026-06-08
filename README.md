# Salary Calculating Agent

A local Telegram assistant that helps managers register workers, track bonuses and advances, calculate net salary, and record payouts — all through natural conversation in text or voice.

The bot runs entirely on your machine using Ollama for AI and Whisper for voice transcription. No external AI APIs are required beyond Telegram messaging.

## Salary formula

**Net payable** = `fixed_salary + bonuses − advances − payouts`

When you specify a month (e.g. `2025-03`), bonuses, advances, and payouts are filtered to that calendar month. Fixed salary is always the full monthly base (not prorated in v1).

## Prerequisites

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) on your PATH
- [Ollama](https://ollama.com/download/windows) installed and running (Windows: run `OllamaSetup.exe`, then use **PowerShell** or **CMD** — Git Bash may not find `ollama` until PATH is updated)
- Telegram bot token from [@BotFather](https://t.me/BotFather)

### Windows ffmpeg

Download from [ffmpeg.org](https://ffmpeg.org/download.html), extract, and add the `bin` folder to your system PATH.

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure secrets — copy the example env file and add your token:

```bash
cp .env.example .env    # Linux/macOS
copy .env.example .env  # Windows
```

Edit `.env` and set `BOT_TOKEN` (from [@BotFather](https://t.me/BotFather)). Other settings are optional.

> **Important:** Never commit `.env` — it is listed in `.gitignore`.

3. Pull the Ollama model:

```bash
ollama pull llama3.2
```

4. Start the bot:

```bash
./run.sh        # Linux/macOS
run.bat         # Windows
```

Or manually:

```bash
ollama serve
python bot.py
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and reset conversation memory |
| `/reset` | Clear conversation history |

## What you can say

- Register a worker with full name, job start date, birthdate, and fixed salary
- Add bonuses or advances
- Calculate net salary (all time or for a specific month)
- Record a payout
- List all workers or view transaction history

Voice messages are transcribed automatically. The bot replies in the same language you use (Uzbek, Russian, or English).

## Example conversations

### English

**You:** Register Ali Karimov, started 2024-03-01, born 1990-05-15, salary 5 million  
**Bot:** Ali is registered with a fixed salary of 5,000,000.

**You:** Add a 500,000 bonus for Ali  
**Bot:** Done — bonus added. His net payable is now 5,500,000.

**You:** Record a 4,500,000 payout for March 2025  
**Bot:** Payout recorded for March 2025. Net payable is now 1,000,000.

### Russian

**You:** Зарегистрируй Бобура, начал 2024-01-15, родился 1988-06-20, зарплата 3 миллиона  
**Bot:** Бобур зарегистрирован с фиксированной зарплатой 3,000,000.

**You:** Добавь аванс 500000 Бобуру  
**Bot:** Аванс записан. К выплате осталось 2,500,000.

### Uzbek

**You:** Kamolni ro'yxatdan o'tkaz, ish boshlagan 2024-05-01, tug'ilgan 1992-03-10, maosh 4 million  
**Bot:** Kamol ro'yxatga olindi, oylik maoshi 4,000,000.

**You:** Kamolga 300 ming avans qo'sh  
**Bot:** Avans qo'shildi. To'lanishi kerak: 3,700,000.

## Worker data stored

Each worker record includes:

- Full name
- Job started date
- Birthdate
- Fixed salary
- Bonuses (with notes and timestamps)
- Advances (with notes and timestamps)
- Payouts (with optional period)
- Full audit history

Data is stored in `salaries.json` in the project folder.

## Manual verification checklist

After starting the bot, test these flows in Telegram:

1. `/start` — confirm welcome message
2. Register a worker via text
3. `Show all workers` — confirm the new worker appears
4. Add a bonus and ask for salary calculation
5. Send a voice message in your language — confirm transcription echo and reply
6. `/reset` — confirm memory reset, then ask a follow-up that requires prior context (should not remember)

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ffmpeg is not installed` | Install ffmpeg and ensure it is on PATH |
| `ollama: command not found` | Install from [ollama.com/download/windows](https://ollama.com/download/windows), then open a **new** PowerShell/CMD window |
| `Connection refused` to Ollama | Start the Ollama app from the Start menu, or run `ollama serve` in PowerShell |
| Invalid bot token | Double-check `BOT_TOKEN` in `.env` from @BotFather |
| `BOT_TOKEN is not set` | Copy `.env.example` to `.env` and fill in your token |
| Slow voice processing | Set `WHISPER_MODEL=base` in environment for a lighter model |
| Whisper first run slow | First transcription downloads the model — wait for it to finish |

## Running tests

```bash
python -m unittest discover -s tests -v
```

## Project structure

```
salary-calculating-agent/
├── bot.py           # Telegram handlers
├── agent.py         # Ollama conversational AI
├── tools.py         # Salary operations
├── data.py          # JSON storage + payroll math
├── transcriber.py   # Whisper STT
├── config.py        # Settings
├── salaries.json    # Worker database
├── tests/           # Unit tests
├── run.sh / run.bat # Startup scripts
└── requirements.txt
```
