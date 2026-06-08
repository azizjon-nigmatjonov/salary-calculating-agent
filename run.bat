@echo off
echo Starting Salary Agent...

where ollama >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Ollama;%PATH%"
    ) else (
        echo.
        echo ERROR: Ollama is not installed.
        echo.
        echo 1. Download from https://ollama.com/download/windows
        echo 2. Run OllamaSetup.exe and finish the installer
        echo 3. Open a NEW terminal and run: ollama pull llama3.2
        echo 4. Run this script again
        echo.
        pause
        exit /b 1
    )
)

REM Ollama Windows app usually runs in the background; serve is a no-op if already up
start /B ollama serve >nul 2>&1
timeout /t 2 /nobreak >nul
python bot.py
