@echo off
cd /d "%~dp0"
set PYTHONPATH=src
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
