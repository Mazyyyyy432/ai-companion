@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
echo [ai service] port 8000 - close this window to stop
".venv\Scripts\python.exe" backend\main.py
echo.
echo ai service exited. press any key.
pause >nul
