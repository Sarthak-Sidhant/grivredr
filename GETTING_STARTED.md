# Getting Started with Grivredr

**Complete guide to set up and start training your first scraper in under 5 minutes!**

## Prerequisites

- **Python 3.8+** installed on your system
- **Internet connection** for downloading dependencies
- **MegaLLM API key** (free tier available at [app.mega-llm.com](https://app.mega-llm.com))

## Installation

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd grivredr
```

### Step 2: Quick Setup (Recommended)

Run the automated setup script:

```bash
chmod +x quickstart.sh
./quickstart.sh
```

This will:
- ✅ Check Python installation
- ✅ Create `.env` file from template
- ✅ Install all dependencies
- ✅ Install Playwright browser
- ✅ Verify setup

### Step 3: Configure API Key

Edit the `.env` file and add your MegaLLM API key:

```bash
nano .env  # or use your preferred editor
```

Replace the placeholder with your actual key:

```
api_key=your_actual_megallm_api_key_here
```

**Get your API key:** https://app.mega-llm.com

## Manual Installation (Alternative)

If you prefer manual setup:

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browser

```bash
python -m playwright install chromium
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your API key
```

## Your First Training Session

### Train Your First Portal

Let's train the system on the Abua Sathi grievance portal:

```bash
python cli/train_cli.py abua_sathi --district ranchi
```

**What happens during training:**

```
┌─────────────────────────────────────────────┐
│ Phase 1: Form Discovery (30-60 seconds)    │
│ • Claude Vision analyzes the form          │
│ • Detects fields, dropdowns, validation    │
│ • Interactive exploration of the page      │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Phase 2: JS Analysis (10-20 seconds)       │
│ • Monitors JavaScript behavior             │
│ • Detects dynamic field population         │
│ • Identifies AJAX calls                    │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Phase 3: Validation (30-60 seconds)        │
│ • Tests empty submission                   │
│ • Validates field types                    │
│ • Tests cascading dropdowns                │
│ • Full submission test                     │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Phase 4: Code Generation (20-40 seconds)   │
│ • Generates production Python code         │
│ • Self-healing validation (3 attempts)     │
│ • Saves to outputs/generated_scrapers/     │
└─────────────────────────────────────────────┘
```

**Total time:** ~2-3 minutes
**Total cost:** ~$0.12 (one-time)
**Future runs:** $0.00 (scraper runs without AI)

### Watch the Training (Recommended)

Training runs with a visible browser by default so you can see what's happening:

- **Browser window** shows form interaction
- **Terminal** shows progress and logs
- **Screenshots** saved to `outputs/screenshots/`

### Headless Training (Optional)

To train without visible browser:

```bash
python cli/train_cli.py abua_sathi --district ranchi --headless
```

## Test Your Generated Scraper

Once training is complete, test the generated scraper:

```bash
python tests/test_abua_sathi_live.py
```

This will:
- Load the generated scraper
- Fill out the form with test data
- Submit the grievance
- Show success/failure result

## Explore Training Results

### View What Was Discovered

```bash
python scripts/check_discovery_results.py
```

Shows:
- All form fields found
- Dropdown options detected
- Required field validation
- Select2 and cascading fields

### Check Training Session

Training sessions are saved with full details:

```bash
ls data/training_sessions/
cat data/training_sessions/abua_sathi_*.json
```

Contains:
- Form discovery results
- Validation test results
- Generated code
- Cost breakdown
- Confidence scores

### View Generated Code

```bash
cat outputs/generated_scrapers/ranchi_district/portals/abua_sathi/abua_sathi_scraper.py
```

This is production-ready Python code you can use directly!

## Use Your Scraper in Python

```python
import asyncio
from outputs.generated_scrapers.ranchi_district.portals.abua_sathi import AbuaSathiScraper

async def submit_grievance():
    scraper = AbuaSathiScraper(headless=False)

    result = await scraper.submit_grievance({
        'name': 'John Doe',
        'contact': '9876543210',
        'village_name': 'Test Village',
        'block_id': '500107',  # Ranchi Municipal Corporation
        'jurisdiction_id': '600624',  # Ward-1
        'department_id': '500107',
        'description': 'Street light not working on Main Road'
    })

    if result['success']:
        print(f"✅ Submitted! Tracking ID: {result['tracking_id']}")
    else:
        print(f"❌ Failed: {result['error']}")

# Run it
asyncio.run(submit_grievance())
```

## Train More Portals

You can train any grievance portal:

```bash
# Generic training command
python cli/train_cli.py <portal_name> --district <district_name>

# Examples
python cli/train_cli.py ranchi_smart --district ranchi
python cli/train_cli.py mumbai_portal --district mumbai
python cli/train_cli.py delhi_complaints --district delhi
```

## Understanding the Cost Model

| Activity | Cost | Frequency |
|----------|------|-----------|
| **Training** | ~$0.12 | One-time per portal |
| **Running Scraper** | $0.00 | Unlimited |
| **Re-training** | ~$0.12 | Only if form changes |

**Example:**
- Train 10 portals: $1.20 total
- Submit 10,000 grievances: $0.00

## Project Structure

After setup, your project looks like this:

```
grivredr/
├── cli/                    # Command-line tools
│   └── train_cli.py       # Main training script
├── outputs/                # Generated outputs
│   ├── generated_scrapers/ # Your trained scrapers
│   └── screenshots/       # Training screenshots
├── data/                   # Training data
│   ├── training_sessions/ # Training logs
│   ├── recordings/        # Human recordings
│   └── cache/             # AI cache
├── tests/                  # Test your scrapers
├── scripts/                # Utility scripts
├── docs/                   # Full documentation
└── [core system files]
```

## Troubleshooting

### Common Issues

**1. "Module not found" errors**
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

**2. "Playwright browser not found"**
```bash
python -m playwright install chromium
```

**3. "API key invalid"**
- Check your `.env` file
- Verify key from https://app.mega-llm.com
- Make sure no extra spaces or quotes

**4. "Training failed at discovery phase"**
- Check internet connection
- Try with `--headless` flag disabled
- Verify the URL is accessible

**5. "Import error for generated scraper"**
- Make sure training completed successfully
- Check file exists: `outputs/generated_scrapers/<district>/...`
- Run from project root directory

### Getting Help

1. **Check Status:** `cat docs/STATUS.md`
2. **View Roadmap:** `cat docs/ROADMAP.md`
3. **Read Architecture:** `cat docs/ARCHITECTURE.md`
4. **Check Training Logs:** `cat data/training_sessions/<latest>.json`

## Next Steps

Now that you're set up, you can:

### 1. **Explore Advanced Features**

```bash
# Record human interactions
python cli/record_cli.py <portal_name>

# Train from recording
python cli/train_from_recording.py <recording_file>

# Batch process multiple portals
python batch/batch_processor.py
```

### 2. **Read Documentation**

- `docs/QUICK_START.md` - Quick reference guide
- `docs/USAGE_GUIDE.md` - Comprehensive usage
- `docs/ARCHITECTURE.md` - System design
- `docs/IMPROVEMENTS.md` - Recent enhancements

### 3. **Train Multiple Districts**

Organize scrapers by district:

```bash
mkdir -p outputs/generated_scrapers/<new_district>/portals/<portal_name>
python cli/train_cli.py <portal_name> --district <new_district>
```

### 4. **Integrate with Your Application**

The generated scrapers are standalone Python modules you can import and use in any application!

## Best Practices

### ✅ Do:
- Run training with visible browser first (to understand the process)
- Test generated scrapers before production use
- Keep `.env` file secure and out of version control
- Review training logs after each session
- Use descriptive portal names

### ❌ Don't:
- Don't commit `.env` file to git
- Don't skip testing phase
- Don't use in production without validation
- Don't train the same portal repeatedly (costs money)
- Don't share API keys

## Quick Reference Card

```bash
# Setup
./quickstart.sh                                    # One-time setup

# Training
python cli/train_cli.py <name> --district <dist>  # Train portal

# Testing
python tests/test_abua_sathi_live.py              # Test scraper

# Debugging
python scripts/check_discovery_results.py          # Check discovery
ls data/training_sessions/                         # View logs

# Documentation
cat README.md                                      # Overview
cat docs/QUICK_START.md                           # Quick guide
cat docs/STATUS.md                                # Current state
```

## Success Indicators

You'll know everything is working when:

1. ✅ Training completes all 4 phases
2. ✅ Confidence score > 0.7
3. ✅ Generated scraper file exists in `outputs/`
4. ✅ Test run succeeds
5. ✅ Tracking ID returned on submission

## What's Next?

You're ready to:
- 🎯 Train your own portals
- 🚀 Build automation workflows
- 🔧 Integrate with your applications
- 📊 Scale to multiple districts
- 💡 Contribute improvements

**Happy scraping! 🎉**

---

**Need help?** Check `docs/` for detailed documentation or review training logs in `data/training_sessions/`.
