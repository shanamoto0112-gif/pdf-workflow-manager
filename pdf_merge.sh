#!/bin/bash

# PDF Merge Workflow Shell Script
# Merges and groups PDFs by order number

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
echo "Loading configuration for PDF Merge"
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

echo "+ GEMINI_API_KEY: (configured)"
echo ""

# ==========================================
# 4. Run PDF Merge workflow
# ==========================================

clear
echo ""
echo "===================================================="
echo "PDF Merge Workflow"
echo "===================================================="
echo ""
echo "Function: Merge and group PDFs by order number"
echo ""
echo "Input folder: input_pdfs_merge/"
echo "Output folder: output_pdfs_merge/"
echo "Failed files: failed_pdfs_merge/"
echo ""
echo "Status: Processing..."
echo ""

python3 main_processor.py pdf_merge

if [ $? -ne 0 ]; then
    echo ""
    echo "Error: PDF merge workflow failed."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
else
    echo ""
    echo "PDF merge workflow completed successfully."
    echo ""
    read -p "Press Enter to exit..."
    exit 0
fi
