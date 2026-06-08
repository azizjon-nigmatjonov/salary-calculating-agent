#!/bin/bash
echo "Starting Salary Agent..."
ollama serve &>/dev/null &
sleep 2
python bot.py
