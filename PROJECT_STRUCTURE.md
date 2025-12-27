# Project Structure

This document explains the organization of Grivredr's codebase.

## Directory Layout

```
grivredr/
├── agents/                 # AI agents (4-phase training pipeline)
│   ├── orchestrator.py              # Coordinates all agents
│   ├── form_discovery_agent.py      # Phase 1: Form exploration
│   ├── js_analyzer_agent.py         # Phase 2: JavaScript analysis
│   ├── test_agent.py                # Phase 3: Validation testing
│   ├── code_generator_agent.py      # Phase 4: Scraper generation
│   ├── hybrid_discovery_strategy.py # Smart Playwright + Browser Use
│   ├── browser_use_discovery_agent.py # AI-powered exploration
│   ├── human_recorder_agent.py      # Human recording fallback
│   └── base_agent.py                # Base class for all agents
│
├── cli/                    # Command-line interfaces
│   ├── train_cli.py                 # Main training CLI (START HERE)
│   ├── record_cli.py                # Human recording mode
│   └── train_from_recording.py      # Generate from recording
│
├── config/                 # Configuration and AI client
│   ├── ai_client.py                 # Anthropic SDK wrapper
│   └── healing_prompts.py           # Self-healing prompt templates
│
├── knowledge/              # Pattern library (learns from success)
│   ├── pattern_library.py           # SQLite + vector store
│   ├── code_templates.py            # UI framework templates
│   └── framework_detector.py        # Detect UI frameworks
│
├── utils/                  # Utility modules
│   ├── scraper_validator.py        # Validates generated scrapers
│   ├── js_runtime_monitor.py       # Monitors JavaScript behavior
│   ├── ai_cache.py                  # AI response caching
│   ├── portal_manager.py            # Portal configuration
│   └── code_extraction.py           # Code extraction utilities
│
├── intelligence/           # Advanced/experimental features
│   ├── langchain_pattern_matcher.py # LangChain integration
│   ├── form_clustering.py           # Form similarity analysis
│   └── [other experimental features]
│
├── tests/                  # Test suite
│   ├── unit/                        # Unit tests
│   ├── integration/                 # Integration tests
│   ├── e2e/                         # End-to-end tests
│   ├── test_*_live.py               # Live scraper tests
│   └── conftest.py                  # Pytest configuration
│
├── scripts/                # Utility scripts
│   ├── check_discovery_results.py   # Debug form discovery
│   ├── validate_system.py           # System validation
│   └── [other helper scripts]
│
├── docs/                   # Documentation
│   ├── QUICK_START.md               # Getting started guide
│   ├── ARCHITECTURE.md              # System design
│   ├── STATUS.md                    # Current features
│   └── [other documentation]
│
├── legacy/                 # Deprecated code (kept for reference)
│   ├── website_learner/
│   ├── scraper_generator/
│   └── executor/
│
├── outputs/                # Generated artifacts (gitignored)
│   ├── generated_scrapers/          # Generated scraper code
│   └── screenshots/                 # Training screenshots
│
├── data/                   # Runtime data (gitignored)
│   ├── training_sessions/           # Training session logs
│   ├── recordings/                  # Human recordings
│   └── cache/                       # AI cache
│
├── README.md               # Main project documentation
├── CLAUDE.md               # Guide for Claude Code
├── GETTING_STARTED.md      # Quick start guide
├── CONTRIBUTING.md         # Contribution guidelines
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Modern Python project config
├── quickstart.sh           # Automated setup script
├── verify_setup.py         # Setup verification
└── .env.example            # Environment configuration template
```

## Key Files Explained

### Entry Points

- **`cli/train_cli.py`** - Main entry point for training new portals
- **`quickstart.sh`** - One-command setup script
- **`verify_setup.py`** - Verifies installation and configuration

### Core Agents (agents/)

The system uses a **4-phase pipeline** coordinated by `orchestrator.py`:

1. **Form Discovery** (`form_discovery_agent.py`)
   - Uses Claude Vision + Playwright
   - Interactive exploration (clicks dropdowns, detects fields)
   - Hybrid strategy: Playwright first, Browser Use AI fallback

2. **JavaScript Analysis** (`js_analyzer_agent.py`)
   - Monitors JS runtime during interaction
   - Detects AJAX calls, dynamic behavior, event handlers

3. **Test Validation** (`test_agent.py`)
   - Validates discovered schema
   - Tests: empty submission, field types, cascading dropdowns
   - Generates confidence score

4. **Code Generation** (`code_generator_agent.py`)
   - Generates production Python scraper with Claude Opus
   - Self-healing: validates and fixes code (up to 3 attempts)
   - Uses pattern library for learning

### Configuration (config/)

- **`ai_client.py`** - Unified Anthropic SDK interface
  - Model selection: Haiku (fast), Sonnet (balanced), Opus (powerful)
  - AI response caching for cost savings
  - LangChain compatibility

- **`healing_prompts.py`** - Templates for self-healing code generation

### Knowledge Base (knowledge/)

- **`pattern_library.py`** - Stores successful patterns
  - SQLite database for structured data
  - Optional Chroma vector store for semantic search
  - Learns from each successful training run

- **`code_templates.py`** - Code templates for common UI patterns
  - Select2 dropdowns
  - Cascading fields
  - AJAX submissions

### Utilities (utils/)

- **`scraper_validator.py`** - Validates generated scrapers
  - Runs in test mode (no actual submission)
  - Checks syntax, imports, class structure
  - Returns detailed validation results

- **`js_runtime_monitor.py`** - Captures JavaScript behavior
  - Network requests (AJAX)
  - Event handlers (blur/focus/input)
  - Dynamic field population

### Testing (tests/)

- **Unit tests** (`tests/unit/`) - Test individual components
- **Integration tests** (`tests/integration/`) - Test agent interactions
- **E2E tests** (`tests/e2e/`) - Test complete workflow
- **Live tests** (`tests/test_*_live.py`) - Test real portals

## Generated Artifacts

### Training Output Structure

```
outputs/generated_scrapers/{district}/portals/{portal}/
├── __init__.py
├── {portal}_scraper.py     # Generated scraper class
└── tests/
    └── test_{portal}_scraper.py
```

### Training Session Data

```
data/training_sessions/{session_id}.json
```

Contains:
- Discovery results
- JS analysis
- Test results
- Generated code
- Cost breakdown
- Confidence scores

### Human Recordings

```
data/recordings/sessions/{portal}_{timestamp}.json
```

Human actions recorded as ground truth for pattern library.

## Development Workflow

### 1. Training a New Portal

```bash
python cli/train_cli.py portal_name --district district_name [--url https://...]
```

### 2. Testing Generated Scraper

```bash
python tests/test_portal_name_live.py
```

### 3. Debugging Issues

```bash
# Check discovery results
python scripts/check_discovery_results.py

# View training session
cat data/training_sessions/{session_id}.json

# Validate system
python scripts/validate_system.py
```

## Legacy Code

The `legacy/` directory contains deprecated code kept for reference:
- `website_learner/` - Old learning approach
- `scraper_generator/` - Old code generation
- `executor/` - Old execution engine

These are not used in the current system but preserved for historical context.

## Configuration Files

- **`.env`** - Environment variables (API keys, settings)
- **`requirements.txt`** - Python dependencies (pip)
- **`pyproject.toml`** - Modern Python project config (uv, poetry)
- **`.gitignore`** - Excludes generated artifacts from git

## Notes

- All generated artifacts (screenshots, scrapers, sessions) are gitignored
- Pattern library database is gitignored (generated during training)
- Only keep example scrapers in repo (in `outputs/generated_scrapers/example/`)
