@echo off
title TechTaru DocIQ - Frontend
cd /d "%~dp0frontend"
if not exist node_modules (
  echo Installing npm dependencies...
  call npm install
)
echo Starting frontend on http://localhost:5173 ...
call npm run dev
