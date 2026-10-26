@echo off
title Concept Stores Daily Sales Follow-up Bot
cd /d "%~dp0"

echo ===================================================
echo   Concept Store Daily Sales Follow-up Bot
echo   Stores: WWEG, WW271, WWAE
echo ===================================================
echo.

set "PY_EXE=C:\Users\ROG\AppData\Local\Python\bin\python.exe"

if exist "%PY_EXE%" (
    "%PY_EXE%" bot.py
) else (
    python bot.py
)

if errorlevel 1 (
    echo.
    echo Bot stopped with an error. Check the messages above.
    pause
)
