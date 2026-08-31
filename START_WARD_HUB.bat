@echo off
setlocal enabledelayedexpansion
title IPD Smart Sentinel - Autonomous Ward Hub

echo =====================================================================
echo  🏥 IPD SMART SENTINEL - AUTONOMOUS WARD HUB
echo  (Bedside PDA Companion ^& Autonomous In-Memory Hub Engine)
echo =====================================================================
echo.

set "PROJECT_ROOT=%~dp0"
set "PYTHON_EXE="

:: 1. Detect Embedded / Local Virtualenv / System Python
if exist "%PROJECT_ROOT%python\python.exe" (
    set "PYTHON_EXE=%PROJECT_ROOT%python\python.exe"
    echo [*] Found Embedded Python: !PYTHON_EXE!
) else if exist "%PROJECT_ROOT%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_ROOT%.venv\Scripts\python.exe"
    echo [*] Found Virtualenv Python: !PYTHON_EXE!
) else (
    where python >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "PYTHON_EXE=python"
        echo [*] Using System Python
    ) else (
        echo [ERROR] Python environment not found!
        echo Please ensure Python or .venv is present in %PROJECT_ROOT%
        pause
        exit /b 1
    )
)

:: 2. Set Environment for Zero-Install Portable Execution
set "SW_ENVIRONMENT=pilot"
set "SW_AUTO_CREATE_DB=true"
set "SW_SEED_DATA=false"
set "SW_ENABLE_DOCS=false"
set "SW_ALLOWED_HOSTS=127.0.0.1,localhost,testserver"
set "SW_DATABASE_PATH=%PROJECT_ROOT%ward_hub.db"
set "SW_TELEMETRY_STATE_PATH=%PROJECT_ROOT%edge_telemetry_state.json"
set "SW_AUDIT_LOG_PATH=%PROJECT_ROOT%audit_events.jsonl"
set "SW_FORENSIC_ANCHOR_PATH=%PROJECT_ROOT%forensic_anchors.jsonl"
set "SW_RATE_LIMIT_PER_MINUTE=6000"
set "SW_DEVICE_TRUST_MODE=observe"

echo.
echo [*] Initializing Ward Hub Engine on http://127.0.0.1:8080 ...
echo [*] Press Ctrl+C to stop the service.
echo.

start "" http://127.0.0.1:8080/kiosk

"!PYTHON_EXE!" -m uvicorn main:app --host 127.0.0.1 --port 8080

if !ERRORLEVEL! neq 0 (
    echo.
    echo [ERROR] Hub terminated unexpectedly with exit code !ERRORLEVEL!
    pause
)
