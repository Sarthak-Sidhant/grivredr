#!/bin/bash

echo "=================================================="
echo "🚀 Grivredr AI Grievance Automation - Quick Start"
echo "=================================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Check if dependencies are installed
echo "📦 Checking dependencies..."
if python3 -c "import fastapi" 2>/dev/null; then
    echo "✅ Dependencies already installed"
else
    echo "📥 Installing dependencies..."
    python3 -m pip install --user -r requirements.txt -q
    python3 -m playwright install chromium
fi

echo ""
echo "🧪 Testing AI connection..."
python3 test_ai_client.py

if [ $? -eq 0 ]; then
    echo ""
    echo "=================================================="
    echo "✅ System Ready!"
    echo "=================================================="
    echo ""
    echo "Next steps:"
    echo ""
    echo "1️⃣  Learn Ranchi websites (generates scrapers):"
    echo "   python3 learn_ranchi.py"
    echo ""
    echo "2️⃣  Test generated scrapers:"
    echo "   python3 test_scrapers.py"
    echo ""
    echo "3️⃣  Start API server:"
    echo "   python3 main.py"
    echo ""
    echo "📖 Full documentation: README.md and USAGE_GUIDE.md"
    echo "=================================================="
else
    echo ""
    echo "❌ AI connection failed. Check your .env file."
    echo "Expected: api_key=sk-mega-..."
fi
