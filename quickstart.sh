#!/bin/bash

echo "=========================================================="
echo "🚀 Grivredr - AI-Powered Web Scraper Generator"
echo "=========================================================="
echo ""
echo "Quick Setup Script"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check Python
echo -e "${BLUE}[1/6]${NC} Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    echo "   Please install Python 3.11+ from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✅ Python $PYTHON_VERSION found${NC}"
echo ""

# Check if .env exists
echo -e "${BLUE}[2/6]${NC} Checking environment configuration..."
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found${NC}"
    echo ""
    echo "Creating .env from template..."
    cp .env.example .env
    echo ""
    echo -e "${YELLOW}📝 IMPORTANT: Edit .env and add your MegaLLM API key:${NC}"
    echo "   api_key=your_megallm_api_key_here"
    echo ""
    echo "   Get your key from: https://app.mega-llm.com"
    echo ""
    read -p "Press Enter after you've updated .env..." -r
    echo ""
else
    echo -e "${GREEN}✅ .env file exists${NC}"

    # Check if API key is set
    if grep -q "api_key=your_megallm_api_key_here" .env; then
        echo -e "${YELLOW}⚠️  API key not configured${NC}"
        echo "   Please edit .env and add your MegaLLM API key"
        echo "   Get your key from: https://app.mega-llm.com"
        echo ""
        read -p "Press Enter after you've updated .env..." -r
        echo ""
    else
        echo -e "${GREEN}✅ API key configured${NC}"
    fi
fi
echo ""

# Check if virtual environment exists
echo -e "${BLUE}[3/6]${NC} Checking virtual environment..."
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${GREEN}✅ Virtual environment exists${NC}"
fi
echo ""

# Activate virtual environment
echo -e "${BLUE}[4/6]${NC} Installing dependencies..."
source .venv/bin/activate

# Check if dependencies are installed
if python3 -c "import playwright" 2>/dev/null; then
    echo -e "${GREEN}✅ Dependencies already installed${NC}"
else
    echo "Installing Python packages..."
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
    echo -e "${GREEN}✅ Python packages installed${NC}"
fi
echo ""

# Install Playwright browsers
echo -e "${BLUE}[5/6]${NC} Installing Playwright browsers..."
if [ -d "$HOME/.cache/ms-playwright" ] || [ -d "$HOME/Library/Caches/ms-playwright" ]; then
    echo -e "${GREEN}✅ Playwright browsers already installed${NC}"
else
    echo "Installing Chromium browser (this may take a minute)..."
    python3 -m playwright install chromium
    echo -e "${GREEN}✅ Playwright browsers installed${NC}"
fi
echo ""

# Verify setup
echo -e "${BLUE}[6/6]${NC} Verifying setup..."
python3 verify_setup.py

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================================="
    echo -e "${GREEN}✅ Setup Complete! System Ready!${NC}"
    echo "=========================================================="
    echo ""
    echo -e "${BLUE}📖 Quick Start Commands:${NC}"
    echo ""
    echo "  1️⃣  Train a new portal (example: Abua Sathi):"
    echo -e "     ${GREEN}python cli/train_cli.py abua_sathi --district ranchi${NC}"
    echo ""
    echo "  2️⃣  Test a generated scraper:"
    echo -e "     ${GREEN}python tests/test_abua_sathi_live.py${NC}"
    echo ""
    echo "  3️⃣  Check what was discovered:"
    echo -e "     ${GREEN}python scripts/check_discovery_results.py${NC}"
    echo ""
    echo "  4️⃣  View training results:"
    echo -e "     ${GREEN}ls data/training_sessions/${NC}"
    echo ""
    echo -e "${BLUE}📚 Documentation:${NC}"
    echo "   • README.md - Full project documentation"
    echo "   • GETTING_STARTED.md - Detailed quick start guide"
    echo "   • PROJECT_STRUCTURE.md - Codebase organization"
    echo "   • docs/STATUS.md - Current features and roadmap"
    echo ""
    echo -e "${BLUE}💡 Tips:${NC}"
    echo "   • Training takes 2-3 minutes per portal"
    echo "   • Costs ~\$0.12 per portal (one-time)"
    echo "   • Generated scrapers run for free forever"
    echo "   • Use --headless flag to hide browser"
    echo ""
    echo -e "${BLUE}🔧 Troubleshooting:${NC}"
    echo "   • If training fails, check data/training_sessions/ for logs"
    echo "   • For low confidence, try --browser-use-first flag"
    echo "   • Join discussions: https://github.com/yourusername/grivredr/discussions"
    echo ""
    echo "=========================================================="
    echo ""
else
    echo ""
    echo "=========================================================="
    echo -e "${RED}⚠️  Setup verification failed${NC}"
    echo "=========================================================="
    echo ""
    echo "Common issues:"
    echo "  • API key not set in .env"
    echo "  • Missing dependencies (run: pip install -r requirements.txt)"
    echo "  • Playwright not installed (run: python -m playwright install chromium)"
    echo ""
    echo "For help, see: https://github.com/yourusername/grivredr/issues"
    echo ""
    exit 1
fi
