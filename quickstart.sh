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

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found!"
    echo ""
    echo "Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "📝 Please edit .env and add your MegaLLM API key:"
    echo "   api_key=your_megallm_api_key_here"
    echo ""
    echo "Get your key from: https://app.mega-llm.com"
    echo ""
    read -p "Press Enter after you've updated .env..."
fi

# Check if dependencies are installed
echo "📦 Checking dependencies..."
if python3 -c "import playwright" 2>/dev/null; then
    echo "✅ Dependencies already installed"
else
    echo "📥 Installing dependencies..."
    python3 -m pip install --user -r requirements.txt
    echo ""
    echo "📥 Installing Playwright browsers..."
    python3 -m playwright install chromium
fi

echo ""
echo "🔍 Verifying setup..."
python3 verify_setup.py

if [ $? -eq 0 ]; then
    echo ""
    echo "=================================================="
    echo "✅ Setup Complete! System Ready!"
    echo "=================================================="
else
    echo ""
    echo "=================================================="
    echo "⚠️  Setup verification failed"
    echo "=================================================="
    exit 1
fi
echo ""
echo "Quick Start Commands:"
echo ""
echo "1️⃣  Train a new portal (example: Abua Sathi):"
echo "   python3 cli/train_cli.py abua_sathi --district ranchi"
echo ""
echo "2️⃣  Test a generated scraper:"
echo "   python3 tests/test_abua_sathi_live.py"
echo ""
echo "3️⃣  Check what was discovered:"
echo "   python3 scripts/check_discovery_results.py"
echo ""
echo "4️⃣  View training results:"
echo "   ls data/training_sessions/"
echo ""
echo "📖 Documentation:"
echo "   • README.md - Full guide"
echo "   • docs/QUICK_START.md - Detailed quick start"
echo "   • docs/STATUS.md - Current features"
echo ""
echo "💡 Tips:"
echo "   • Training takes 2-3 minutes per portal"
echo "   • Costs ~$0.12 per portal (one-time)"
echo "   • Generated scrapers run for free forever"
echo "   • Use --headless flag to hide browser"
echo ""
echo "=================================================="
