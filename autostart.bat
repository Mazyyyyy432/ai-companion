@echo off
set PYTHONUTF8=1
cd /d "%~dp0"
start "toy 8765" /min "%~dp0.venv\Scripts\python.exe" "%~dp0vendor\sosexy-ble-control\sosexy_server.py"
ping -n 4 127.0.0.1 >nul
start "ai 8000" /min "%~dp0.venv\Scripts\python.exe" "%~dp0backend\main.py"
