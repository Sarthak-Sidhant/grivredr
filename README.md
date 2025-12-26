# Grivredr - AI-Powered Grievance Automation System

**Train once, automate forever.** Grivredr uses Claude AI to learn how to navigate government grievance portals, then generates production-ready Python scrapers that work without ongoing AI costs.

🎯 **Learn any portal in 2-3 minutes** • 💰 **~$0.12 one-time cost** • 🚀 **Unlimited free usage after**

---

## Quick Start

```bash
# 1. Setup (one-time)
./quickstart.sh

# 2. Train your first portal
python cli/train_cli.py abua_sathi --district ranchi

# 3. Test it
python tests/test_abua_sathi_live.py
```

**📖 New here?** Check out [GETTING_STARTED.md](GETTING_STARTED.md) for a complete walkthrough.

---

## Features

- **AI Website Learning**: Claude Vision + Playwright browser automation to explore forms
- **Smart Form Discovery**: Interactive exploration with dropdown detection and cascading field handling
- **Self-Healing Code Generation**: Generates production-ready scrapers with automatic validation and retry
- **Zero-Cost Execution**: Once learned, scrapers run without AI costs
- **Pattern Library**: Learns from previous sites to speed up future training
- **Multi-Agent System**: Specialized agents for discovery, testing, JS analysis, and code generation

## Cost Model

| Phase | Cost | Frequency |
|-------|------|-----------|
| **Learning** | ~$0.12 per website | One-time |
| **Execution** | $0.00 | Every submission |

**Example**: Learn 10 websites ($1.20) → Submit unlimited grievances ($0.00)

## Project Structure

```
grivredr/
├── agents/                          # Core agent system
│   ├── orchestrator.py              # Main training coordinator
│   ├── form_discovery_agent.py      # Form exploration with Claude Vision
│   ├── test_agent.py                # Validation testing
│   ├── code_generator_agent.py      # Code generation with self-healing
│   ├── js_analyzer_agent.py         # JavaScript runtime analysis
│   └── human_recorder_agent.py      # Human recording-based training
│
├── config/
│   ├── ai_client.py                 # Claude API client (Haiku/Sonnet/Opus)
│   └── healing_prompts.py           # Self-healing prompt templates
│
├── utils/
│   ├── scraper_validator.py        # Validates generated scrapers
│   ├── js_runtime_monitor.py       # Monitors JS during discovery
│   ├── mock_manager.py              # Mock data management
│   ├── ai_cache.py                  # AI response caching
│   └── field_query.py               # Field query utilities
│
├── cli/                             # Command-line interfaces
│   ├── train_cli.py                 # Main training entry point
│   ├── record_cli.py                # Recording-based training
│   └── train_from_recording.py      # Train from recorded sessions
│
├── scripts/                         # Utility scripts
│   ├── check_discovery_results.py   # Debug form discovery
│   ├── explore_abua_sathi_form.py   # Form exploration
│   ├── validate_system.py           # System validation
│   ├── test_scraper.py              # Test generated scrapers
│   └── add_abua_sathi_pattern.py    # Add patterns to library
│
├── outputs/                         # Generated outputs
│   ├── generated_scrapers/          # Generated scraper code by district
│   │   └── ranchi_district/
│   │       └── portals/
│   │           ├── abua_sathi/      # State grievance portal
│   │           ├── ranchi_smart/    # City smart portal
│   │           └── ranchi_municipal/# Municipal portals
│   └── screenshots/                 # Training screenshots
│
├── data/                            # Runtime and training data
│   ├── training_sessions/           # Training session logs
│   ├── recordings/                  # Human recordings
│   └── cache/                       # AI response cache
│
├── knowledge/
│   └── pattern_library.py          # Stores learned patterns
│
├── intelligence/                    # Experimental ML features
│   ├── form_clustering.py           # Form similarity analysis
│   └── scraper_generator_trainer.py # Training improvements
│
├── tests/                           # Test suite
│   ├── test_abua_sathi_live.py     # Live scraper testing
│   ├── test_ai_generated_scraper.py # AI scraper tests
│   └── conftest.py                  # Test configuration
│
├── docs/                            # Documentation
│   ├── STATUS.md                    # Current project state
│   ├── ROADMAP.md                   # Future plans
│   ├── ARCHITECTURE.md              # System design
│   └── [other docs]
│
├── website_learner/                 # Legacy learner (deprecated)
├── scraper_generator/               # Legacy generator (deprecated)
└── executor/                        # Legacy executor (deprecated)
```

## What You Get

After training a portal, you get:

✅ **Production-ready Python scraper** - Import and use in any Python project
✅ **Complete form understanding** - All fields, dropdowns, validations detected
✅ **Self-healing code** - Automatically validated and tested
✅ **Zero ongoing costs** - Scraper runs without AI after training
✅ **Full documentation** - Training logs, screenshots, field mappings

**Example output:** `outputs/generated_scrapers/ranchi_district/portals/abua_sathi/abua_sathi_scraper.py`

## Installation

### Automated Setup (Recommended)

```bash
chmod +x quickstart.sh
./quickstart.sh
```

This handles everything: dependencies, Playwright, and configuration.

### Manual Setup

**1. Install Python Dependencies**

```bash
pip install -r requirements.txt
```

**2. Install Playwright Browsers**

```bash
python -m playwright install chromium
```

**3. Configure API Key**

```bash
cp .env.example .env
# Edit .env and add your MegaLLM API key
```

Get your API key: https://app.mega-llm.com

## Quick Start

### Train a New Portal

```bash
# Train with visible browser to watch the process
python cli/train_cli.py <portal_name>

# Example: Train Abua Sathi portal
python cli/train_cli.py abua_sathi --district ranchi
```

**What happens during training:**

1. **Phase 1: Form Discovery** (~30-60 seconds)
   - Opens browser and takes screenshots
   - Claude Vision analyzes form structure
   - Interactive exploration (clicks dropdowns, finds cascading fields)
   - Confidence score: >0.6 to proceed

2. **Phase 2: JavaScript Analysis** (~10-20 seconds)
   - Monitors JS runtime behavior
   - Detects dynamic field population

3. **Phase 3: Test Validation** (~30-60 seconds)
   - Tests empty submission (finds required fields)
   - Tests field types
   - Tests cascading relationships
   - Tests full submission with mock data
   - Confidence score: >0.7 to proceed

4. **Phase 4: Code Generation** (~20-40 seconds)
   - Claude Opus generates Python scraper
   - Self-healing validation loop (3 attempts)
   - Saves to `outputs/generated_scrapers/{district}/portals/{portal_name}/`
   - Stores pattern in knowledge base

**Total time**: ~2-3 minutes per portal
**Total cost**: ~$0.12 per portal

### Test Generated Scraper

```bash
# Test Abua Sathi scraper (visible browser)
python tests/test_abua_sathi_live.py
```

### Use Scraper in Python

```python
from outputs.generated_scrapers.ranchi_district.portals.abua_sathi import AbuaSathiScraper

scraper = AbuaSathiScraper(headless=False)
result = await scraper.submit_grievance({
    'name': 'John Doe',
    'contact': '9876543210',
    'village_name': 'Test Village',
    'description': 'Street light not working'
})

print(f"Success: {result['success']}")
if result.get('tracking_id'):
    print(f"Tracking ID: {result['tracking_id']}")
```

## How It Works

### 4-Phase Training Workflow

The `Orchestrator` coordinates 4 specialized agents:

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: Form Discovery Agent                                   │
│ - Claude Vision analyzes screenshots                            │
│ - Interactive exploration (dropdowns, cascading fields)         │
│ - Detects validation requirements                               │
│ - Confidence scoring                                             │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: JavaScript Analyzer Agent                              │
│ - Monitors JS runtime during form interaction                   │
│ - Detects dynamic behavior                                       │
│ - Identifies AJAX calls and event handlers                       │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: Test Validation Agent                                  │
│ - Empty submission test (finds required fields)                 │
│ - Field type validation                                          │
│ - Cascading dropdown testing                                     │
│ - Full submission with test data                                 │
└─────────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 4: Code Generator Agent                                   │
│ - Generates production Python scraper                           │
│ - Self-healing validation loop (3 attempts)                     │
│ - Stores pattern in knowledge base                              │
│ - Saves to generated_scrapers/                                  │
└─────────────────────────────────────────────────────────────────┘
```

### AI Models Used

Via MegaLLM API (OpenAI-compatible):

- **Claude Haiku 4.5**: Fast analysis ($1/$5 per 1M tokens)
- **Claude Sonnet 4.5**: Form discovery & testing ($3/$15 per 1M tokens)
- **Claude Opus 4.5**: Code generation ($5/$25 per 1M tokens)

The orchestrator automatically selects the appropriate model for each phase.

## Current Scrapers (Ranchi District)

### 1. Abua Sathi Portal
- **Type**: State-level grievance system (Jharkhand)
- **URL**: https://abuasathi.jharkhand.gov.in/
- **Features**:
  - Select2 dropdowns with cascading (block → jurisdiction)
  - File upload support
  - 12 form fields including hidden ASP.NET fields
- **Location**: `outputs/generated_scrapers/ranchi_district/portals/abua_sathi/`

### 2. Ranchi Smart Portal
- **Type**: City-level smart portal
- **URL**: https://smartranchi.in/
- **Features**:
  - Dropdown-based problem categorization
  - Ward/area selection
- **Location**: `outputs/generated_scrapers/ranchi_district/portals/ranchi_smart/`

### 3. Ranchi Municipal Portals
- **Location**: `outputs/generated_scrapers/ranchi_district/portals/ranchi_municipal/`
- Complaint form scraper
- State grievance scraper

## Debugging

### Check Form Discovery Results

```bash
python scripts/check_discovery_results.py
```

Shows what Claude discovered during Phase 1:
- All form fields found
- Dropdown detection (Select2, cascading)
- Required field validation

### View Training Session

Training sessions are saved in `data/training_sessions/` with full details:

```bash
cat data/training_sessions/abua_sathi_20251224_224523.json
```

Contains:
- Form discovery results
- Test validation results
- Generated code
- Cost breakdown
- Confidence scores

### Check Generated Code

```bash
cat outputs/generated_scrapers/ranchi_district/portals/abua_sathi/abua_sathi_scraper.py
```

## Known Limitations

1. **Select2 Dropdowns**: Handled via JS runtime monitoring
2. **Cascading Dropdowns**: Works but may timeout on slow AJAX
3. **File Uploads**: Detected but not fully tested
4. **CAPTCHA**: Detected but requires human intervention
5. **OTP**: Requires real phone numbers (not automated)

## Documentation

- **docs/STATUS.md**: Current project state, what's working, what's experimental
- **docs/ROADMAP.md**: Future enhancements and planned features
- **docs/ARCHITECTURE.md**: Detailed system design
- **docs/QUICK_START.md**: Step-by-step guide
- **docs/USAGE_GUIDE.md**: Comprehensive usage documentation
- **docs/IMPROVEMENTS.md**: Completed enhancements and their impact
- **docs/AGENTIC_EXAMPLE.md**: Agent workflow examples

## Adding New Districts

To organize scrapers for a new district:

```bash
mkdir -p outputs/generated_scrapers/{district_name}/portals/{portal_name}
python cli/train_cli.py {portal_name} --district {district_name}
```

The trainer will automatically organize scrapers by district structure.

## License

MIT

## Legal Notice

This tool is for legitimate civic engagement. Ensure compliance with website Terms of Service before use. No warranty provided.

---

**Built with Claude AI, Playwright, and Python**

For questions or issues, see docs/STATUS.md for current state or docs/ROADMAP.md for planned features.
