@echo off
REM Unified PDF Processing Batch Script with config.env
REM Updated to support: warranty, maintenance, and pdf_merge workflows

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
echo Loading configuration
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
    echo    - GMAIL_EMAIL
    echo    - GMAIL_APP_PASSWORD
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

if not defined GMAIL_EMAIL (
    echo Error: GMAIL_EMAIL not set in config.env
    pause
    exit /b 1
)

if not defined GMAIL_APP_PASSWORD (
    echo Error: GMAIL_APP_PASSWORD not set in config.env
    pause
    exit /b 1
)

echo + GEMINI_API_KEY: (configured)
echo + GMAIL_EMAIL: %GMAIL_EMAIL%
echo + GMAIL_APP_PASSWORD: (configured)
if defined RECIPIENT_EMAIL_WARRANTY (
    echo + RECIPIENT_EMAIL_WARRANTY: %RECIPIENT_EMAIL_WARRANTY%
)
if defined RECIPIENT_EMAIL_MAINTENANCE (
    echo + RECIPIENT_EMAIL_MAINTENANCE: %RECIPIENT_EMAIL_MAINTENANCE%
)
echo.

REM ==========================================
REM 4. Workflow selection
REM ==========================================

:WORKFLOW_SELECTION
cls
echo.
echo ====================================================
echo PDF Processing System
echo ====================================================
echo.
echo Select workflow:
echo.
echo 1) Warranty          - Process warranty repair invoices
echo 2) Maintenance       - Process maintenance invoices
echo 3) PDF Merge         - Merge and group PDFs by order number
echo 4) Exit
echo.

set /p WORKFLOW_CHOICE="Enter choice (1/2/3/4): "

if "%WORKFLOW_CHOICE%"=="1" (
    set WORKFLOW_NAME=warranty
    set WORKFLOW_DESC=Warranty (warranty repair invoices)
    set NEEDS_EMAIL=yes
    goto CONFIRM_SELECTION
)

if "%WORKFLOW_CHOICE%"=="2" (
    set WORKFLOW_NAME=maintenance
    set WORKFLOW_DESC=Maintenance (maintenance invoices)
    set NEEDS_EMAIL=yes
    goto CONFIRM_SELECTION
)

if "%WORKFLOW_CHOICE%"=="3" (
    set WORKFLOW_NAME=pdf_merge
    set WORKFLOW_DESC=PDF Merge (group and merge PDFs)
    set NEEDS_EMAIL=no
    goto CONFIRM_SELECTION
)

if "%WORKFLOW_CHOICE%"=="4" (
    echo Exiting program.
    pause
    exit /b 0
)

echo.
echo Error: Invalid input. Please enter 1, 2, 3, or 4.
echo.
pause
goto WORKFLOW_SELECTION

REM ==========================================
REM 5. Confirm selection
REM ==========================================

:CONFIRM_SELECTION
cls
echo.
echo ====================================================
echo Confirm settings
echo ====================================================
echo.

echo Workflow: %WORKFLOW_DESC%
echo.

if "%WORKFLOW_NAME%"=="warranty" (
    if defined RECIPIENT_EMAIL_WARRANTY (
        echo Recipient: !RECIPIENT_EMAIL_WARRANTY!
    ) else (
        echo Recipient: warranty.japan@example.com (default)
    )
    echo Input folder: input_pdfs\
    echo Output folder: output_pdfs\
) else if "%WORKFLOW_NAME%"=="maintenance" (
    if defined RECIPIENT_EMAIL_MAINTENANCE (
        echo Recipient: !RECIPIENT_EMAIL_MAINTENANCE!
    ) else (
        echo Recipient: maintenance.japan@example.com (default)
    )
    echo Input folder: input_pdfs\
    echo Output folder: output_pdfs\
) else if "%WORKFLOW_NAME%"=="pdf_merge" (
    echo Note: No email sending for this workflow (local management only)
    echo Input folder: input_pdfs_merge\
    echo Output folder: output_pdfs_merge\
)

echo Failed files folder: failed_pdfs_%WORKFLOW_NAME%\
echo.

set /p CONFIRM="Continue with these settings? (y/n): "

if /i "%CONFIRM%"=="y" (
    goto RUN_WORKFLOW
) else if /i "%CONFIRM%"=="n" (
    echo Cancelled.
    echo.
    pause
    goto WORKFLOW_SELECTION
) else (
    echo Error: Please enter y or n
    echo.
    pause
    goto CONFIRM_SELECTION
)

REM ==========================================
REM 6. Run workflow
REM ==========================================

:RUN_WORKFLOW
cls
echo.
echo ====================================================
echo Running workflow: %WORKFLOW_NAME%
echo ====================================================
echo.

python main_processor.py %WORKFLOW_NAME%

if errorlevel 1 (
    echo.
    echo Error: %WORKFLOW_NAME% processing failed.
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo %WORKFLOW_NAME% processing completed successfully.
    echo.
    pause
    exit /b 0
)
