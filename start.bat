@echo off
chcp 65001 >nul
title Light-Enterprise AI Office System v1.0

REM ============================================================
REM  Project root is where this .bat file lives.
REM  requirements.txt / .env are inside the backend/ folder.
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   Light-Enterprise AI Office System v1.0 - Launcher
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    echo         and add it to PATH, then retry.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [Step 1/3] Creating Python virtual environment .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv. Please check your Python.
        pause
        exit /b 1
    )
    echo           OK.
) else (
    echo [Step 1/3] Virtual environment .venv already exists. OK.
)

echo.
echo [Step 2/3] Installing / updating dependencies ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    echo         Possible fix: delete .venv folder and run this script again.
    pause
    exit /b 1
)

if not exist "backend\.env" (
    echo [!] backend\.env not found, falling back to .env.example defaults.
    echo     Copy backend\.env.example to backend\.env to customize.
)

echo.
echo [Step 3/3] Starting FastAPI server on http://127.0.0.1:8000
echo.
echo   - Web UI       : http://127.0.0.1:8000/
echo   - Swagger docs : http://127.0.0.1:8000/docs
echo   - Health check : http://127.0.0.1:8000/health
echo   - Press Ctrl+C to stop the server.
echo.

cd backend
"..\.venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
