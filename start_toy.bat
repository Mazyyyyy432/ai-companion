@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0vendor\sosexy-ble-control"
echo [toy service] port 8765 - close this window to disconnect
"..\..\.venv\Scripts\python.exe" sosexy_server.py
echo.
echo toy service exited. press any key.
pause >nul
