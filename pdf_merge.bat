@echo off
REM PDF Merge Workflow Batch Script
REM Merges and groups PDFs by order number

setlocal enabledelayedexpansion

cd /d "%~dp0"

REM ==========================================
REM 0. Python check
REM ==========================================

python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found.
    echo Please install Python or add it to PATH.
    pause
    exit /b 1
)

REM ==========================================
REM 1. Activate virtual environment
REM ==========================================

if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM ==========================================
REM 2. Load config.env
REM ==========================================

echo.
echo ====================================================
echo Loading configuration for PDF Merge
echo ====================================================
echo.

if exist "config.env" (
    echo Loading settings from config.env...
    for /f "delims== tokens=1,2" %%a in (config.env) do (
        if not "%%a"=="" (
            set "%%a=%%b"
        )
    )
    echo Configuration loaded successfully.
) else (
    echo Error: config.env file not found.
    echo.
    echo Setup required. Follow these steps:
    echo.
    echo 1. Copy config.env.example to config.env
    echo    Command: copy config.env.example config.env
    echo.
    echo 2. Open config.env in a text editor and set:
    echo    - GEMINI_API_KEY
    echo.
    echo 3. Run this batch file again
    echo.
    pause
    exit /b 1
)

REM ==========================================
REM 3. Validate configuration
REM ==========================================

echo.
echo ====================================================
echo Configuration check
echo ====================================================
echo.

if not defined GEMINI_API_KEY (
    echo Error: GEMINI_API_KEY not set in config.env
    pause
    exit /b 1
)

echo + GEMINI_API_KEY: (configured)
echo.

REM ==========================================
REM 4. Run PDF Merge workflow
REM ==========================================

cls
echo.
echo ====================================================
echo PDF Merge Workflow
echo ====================================================
echo.
echo Function: Merge and group PDFs by order number
echo.
echo Input folder: input_pdfs_merge\
echo Output folder: output_pdfs_merge\
echo Failed files: failed_pdfs_merge\
echo.
echo Status: Processing...
echo.

python main_processor.py pdf_merge

if errorlevel 1 (
    echo.
    echo Error: PDF merge workflow failed.
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo PDF merge workflow completed successfully.
    echo.
    pause
    exit /b 0
)
