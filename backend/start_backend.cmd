@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo Backend virtual environment not found.
  echo Run: python -m venv venv
  pause
  exit /b 1
)
"venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
