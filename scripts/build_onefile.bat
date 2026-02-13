@echo off
setlocal

set PY=.venv\Scripts\python.exe
set ICON=assets\app.ico
set VERSION_FILE=packaging\version_info.txt
set DISTPATH=dist\onefile
set WORKPATH=build\onefile

if not exist "%PY%" (
  echo [ERROR] Python venv not found: %PY%
  exit /b 1
)

"%PY%" -m PyInstaller --noconfirm --clean --windowed --onefile --name VideoDuplicateCheck --icon "%ICON%" --version-file "%VERSION_FILE%" --distpath "%DISTPATH%" --workpath "%WORKPATH%" run_app.py
if errorlevel 1 exit /b 1

echo.
echo Build finished: %DISTPATH%\VideoDuplicateCheck.exe
exit /b 0
