@echo off
title TechTaru DocIQ - Backend API
cd /d "%~dp0backend"

if not exist .env (
  echo Creating .env from template...
  copy .env.example .env >nul
  echo   NOTE: no OPENAI_API_KEY configured - running the rules-based demo engine.
  echo         Paste your key into backend\.env to enable AI extraction.
)

if not exist .venv (
  echo Creating virtual environment and installing dependencies...
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
)

echo Starting backend on http://localhost:8000 ...
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
