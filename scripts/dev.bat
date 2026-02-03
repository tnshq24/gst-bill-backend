@echo off
REM Windows development script for the chatbot avatar backend

setlocal enabledelayedexpansion

echo [INFO] Setting up development environment...

REM Check if virtual environment exists
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt

REM Check if .env file exists
if not exist ".env" (
    echo [WARN] .env file not found. Creating from template...
    copy .env.example .env
    echo [WARN] Please edit .env file with your actual configuration before running the application.
    pause
    exit /b 1
)

REM Run linting
echo [INFO] Running code linting...
ruff check app\ tests\
ruff format app\ tests\

REM Run tests
echo [INFO] Running tests...
pytest tests\ -v --cov=app

REM Check for required environment variables
echo [INFO] Checking environment configuration...
REM Note: This is a simple check - in practice you might want more robust validation

REM Start the application
echo [INFO] Starting the application...
if "%APP_ENV%"=="dev" (
    uvicorn app.main:app --host 0.0.0.0 --port %APP_PORT:8000% --reload
) else (
    gunicorn -k uvicorn.workers.UvicornWorker -w 2 -c gunicorn.conf.py app.main:app
)

pause