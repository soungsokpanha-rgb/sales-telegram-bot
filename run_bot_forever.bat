@echo off
title Concept Stores Sales Bot - Auto Restart
cd /d "%~dp0"

set "PY_EXE=C:\Users\ROG\AppData\Local\Python\bin\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

echo ===================================================
echo   Concept Store Daily Sales Bot - AUTO RESTART
echo   Bot will restart automatically if it stops.
echo   Press Ctrl+C to fully stop.
echo ===================================================

:LOOP
echo.
echo [%DATE% %TIME%] Starting bot...
"%PY_EXE%" bot.py
echo.
echo [%DATE% %TIME%] Bot stopped. Restarting in 10 seconds...
timeout /t 10 /nobreak
goto LOOP
