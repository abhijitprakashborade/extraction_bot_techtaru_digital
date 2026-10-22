@echo off
title TechTaru DocIQ Launcher

echo ================================================
echo   TechTaru DocIQ - starting full stack
echo   Backend : http://localhost:8000/docs
echo   Frontend: http://localhost:5173
echo ================================================

start "TechTaru DocIQ Backend" cmd /c "%~dp0START_BACKEND.bat"
timeout /t 3 /nobreak >nul
start "TechTaru DocIQ Frontend" cmd /c "%~dp0START_FRONTEND.bat"

echo.
echo Both services are launching in their own windows.
echo Give the backend a few seconds, then open http://localhost:5173
pause
