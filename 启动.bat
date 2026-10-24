@echo off
setlocal enabledelayedexpansion
set PYTHONUTF8=1
cd /d "%~dp0"

if not exist "vendor\sosexy-ble-control\sosexy_server.py" (
  echo Fetching toy protocol library ...
  git clone --depth 1 https://github.com/51enuxu/sosexy-ble-control.git "vendor\sosexy-ble-control"
)

if not exist ".venv\Scripts\python.exe" (
  echo First run: creating Python environment, please wait...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
  if errorlevel 1 (
    echo Failed to install dependencies. Check your network.
    pause
    exit /b 1
  )
)

echo Starting toy service on 8765 ...
start "toy 8765" cmd /c ""%~dp0start_toy.bat""

ping -n 4 127.0.0.1 >nul

echo Starting AI service on 8000 ...
start "ai 8000" cmd /c ""%~dp0start_ai.bat""

ping -n 5 127.0.0.1 >nul

set LANIP=
for /f "delims=" %%i in ('powershell -NoProfile -Command "$a=Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.IPAddress -like '192.168.*' -or $_.IPAddress -like '10.*' -or $_.IPAddress -like '172.*' } ^| Select-Object -First 1; if($a){$a.IPAddress}"') do set LANIP=%%i

echo.
echo ================================================
echo   Phone (same Wi-Fi):  http://!LANIP!:8000
echo   This PC:             http://127.0.0.1:8000
echo ================================================
echo.
echo Keep both windows open.
start "" "http://127.0.0.1:8000/admin.html"
pause
