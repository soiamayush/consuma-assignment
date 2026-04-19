@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (set "PY=.venv\Scripts\python.exe") else (set "PY=python")
%PY% -c "import uvicorn" 2>nul
if errorlevel 1 (
  echo uvicorn missing; installing requirements.txt ...
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 exit /b 1
)
%PY% -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
