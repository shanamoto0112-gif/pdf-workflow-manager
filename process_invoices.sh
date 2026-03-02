#!/bin/bash

# Unified PDF Processing Shell Script
# Updated to support: warranty, maintenance, and pdf_merge workflows

cd "$(dirname "$0")" || exit 1

# ==========================================
# 0. Python check
# ==========================================

if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 not found."
    echo "Please install Python3 first."
    read -p "Press Enter to exit..."
    exit 1
fi

# ==========================================
# 1. Activate virtual environment
# ==========================================

if [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# ==========================================
# 2. Load config.env
# ==========================================

echo ""
echo "===================================================="
echo "Loading configuration"
echo "===================================================="
echo ""

if [ -f "config.env" ]; then
    echo "Loading settings from config.env..."
    # shellcheck disable=SC2046
    export $(cat config.env | xargs)
    echo "Configuration loaded successfully."
else
    echo "Error: config.env file not found."
    echo ""
    echo "Setup required. Follow these steps:"
    echo ""
    echo "1. Copy config.env.example to config.env"
    echo "   Command: cp config.env.example config.env"
    echo ""
    echo "2. Open config.env in a text editor and set:"
    echo "   - GEMINI_API_KEY"
    echo "   - GMAIL_EMAIL"
    echo "   - GMAIL_APP_PASSWORD"
    echo ""
    echo "3. Run this script again"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# ==========================================
# 3. Validate configuration
# ==========================================

echo ""
echo "===================================================="
echo "Configuration check"
echo "===================================================="
echo ""

if [ -z "$GEMINI_API_KEY" ]; then
    echo "Error: GEMINI_API_KEY not set in config.env"
    read -p "Press Enter to exit..."
    exit 1
fi

if [ -z "$GMAIL_EMAIL" ]; then
    echo "Error: GMAIL_EMAIL not set in config.env"
    read -p "Press Enter to exit..."
    exit 1
fi

if [ -z "$GMAIL_APP_PASSWORD" ]; then
    echo "Error: GMAIL_APP_PASSWORD not set in config.env"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "+ GEMINI_API_KEY: (configured)"
echo "+ GMAIL_EMAIL: $GMAIL_EMAIL"
echo "+ GMAIL_APP_PASSWORD: (configured)"
[ -n "$RECIPIENT_EMAIL_WARRANTY" ] && echo "+ RECIPIENT_EMAIL_WARRANTY: $RECIPIENT_EMAIL_WARRANTY"
[ -n "$RECIPIENT_EMAIL_MAINTENANCE" ] && echo "+ RECIPIENT_EMAIL_MAINTENANCE: $RECIPIENT_EMAIL_MAINTENANCE"
echo ""

# ==========================================
# 4. Workflow selection
# ==========================================

workflow_selection() {
    clear
    echo ""
    echo "===================================================="
    echo "PDF Processing System"
    echo "===================================================="
    echo ""
    echo "Select workflow:"
    echo ""
    echo "1) Warranty          - Process warranty repair invoices"
    echo "2) Maintenance       - Process maintenance invoices"
    echo "3) PDF Merge         - Merge and group PDFs by order number"
    echo "4) Exit"
    echo ""
    read -p "Enter choice (1/2/3/4): " workflow_choice

    case "$workflow_choice" in
        1)
            WORKFLOW_NAME="warranty"
            WORKFLOW_DESC="Warranty (warranty repair invoices)"
            NEEDS_EMAIL="yes"
            confirm_selection
            ;;
        2)
            WORKFLOW_NAME="maintenance"
            WORKFLOW_DESC="Maintenance (maintenance invoices)"
            NEEDS_EMAIL="yes"
            confirm_selection
            ;;
        3)
            WORKFLOW_NAME="pdf_merge"
            WORKFLOW_DESC="PDF Merge (group and merge PDFs)"
            NEEDS_EMAIL="no"
            confirm_selection
            ;;
        4)
            echo "Exiting program."
            exit 0
            ;;
        *)
            echo ""
            echo "Error: Invalid input. Please enter 1, 2, 3, or 4."
            echo ""
            read -p "Press Enter to continue..."
            workflow_selection
            ;;
    esac
}

# ==========================================
# 5. Confirm selection
# ==========================================

confirm_selection() {
    clear
    echo ""
    echo "===================================================="
    echo "Confirm settings"
    echo "===================================================="
    echo ""

    echo "Workflow: $WORKFLOW_DESC"
    echo ""

    case "$WORKFLOW_NAME" in
        warranty)
            if [ -n "$RECIPIENT_EMAIL_WARRANTY" ]; then
                echo "Recipient: $RECIPIENT_EMAIL_WARRANTY"
            else
                echo "Recipient: warranty.japan@example.com (default)"
            fi
            echo "Input folder: input_pdfs/"
            echo "Output folder: output_pdfs/"
            ;;
        maintenance)
            if [ -n "$RECIPIENT_EMAIL_MAINTENANCE" ]; then
                echo "Recipient: $RECIPIENT_EMAIL_MAINTENANCE"
            else
                echo "Recipient: maintenance.japan@example.com (default)"
            fi
            echo "Input folder: input_pdfs/"
            echo "Output folder: output_pdfs/"
            ;;
        pdf_merge)
            echo "Note: No email sending for this workflow (local management only)"
            echo "Input folder: input_pdfs_merge/"
            echo "Output folder: output_pdfs_merge/"
            ;;
    esac

    echo "Failed files folder: failed_pdfs_${WORKFLOW_NAME}/"
    echo ""

    read -p "Continue with these settings? (y/n): " confirm

    case "$confirm" in
        y | Y)
            run_workflow
            ;;
        n | N)
            echo "Cancelled."
            echo ""
            read -p "Press Enter to continue..."
            workflow_selection
            ;;
        *)
            echo "Error: Please enter y or n"
            echo ""
            read -p "Press Enter to continue..."
            confirm_selection
            ;;
    esac
}

# ==========================================
# 6. Run workflow
# ==========================================

run_workflow() {
    clear
    echo ""
    echo "===================================================="
    echo "Running workflow: $WORKFLOW_NAME"
    echo "===================================================="
    echo ""

    python3 main_processor.py "$WORKFLOW_NAME"

    if [ $? -ne 0 ]; then
        echo ""
        echo "Error: $WORKFLOW_NAME processing failed."
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    else
        echo ""
        echo "$WORKFLOW_NAME processing completed successfully."
        echo ""
        read -p "Press Enter to exit..."
        exit 0
    fi
}

# ==========================================
# Main execution
# ==========================================

workflow_selection
