# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Grivredr** is an AI-powered web scraper generator for government grievance portals. It uses Claude AI to learn how to navigate forms once (~$0.12, 2-3 minutes), then generates production-ready Python scrapers that work forever without ongoing AI costs.

**Core Workflow**: Train once (AI-powered discovery) → Generate Python scraper → Execute unlimited times (zero AI cost)

## Development Commands

### Setup
```bash
# Quick setup (recommended)
./quickstart.sh

# Manual setup
pip install -r requirements.txt
python -m playwright install chromium

# Configuration
cp .env.example .env
# Edit .env and add: api_key=your_megallm_api_key
```

### Training a New Portal
```bash
# Basic training
python cli/train_cli.py <portal_name> --district <district_name>

# Examples
python cli/train_cli.py abua_sathi --district ranchi
python cli/train_cli.py ranchi_smart --district ranchi --headless

# With custom URL
python cli/train_cli.py new_portal --district mumbai --url https://portal.example.com

# Hybrid discovery options
python cli/train_cli.py portal_name --no-hybrid                    # Playwright only (fast)
python cli/train_cli.py portal_name --browser-use-first            # AI-first approach
python cli/train_cli.py portal_name --no-browser-use-fallback      # Disable AI fallback
```

### Testing
```bash
# Test generated scraper (live)
python tests/test_abua_sathi_live.py

# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# E2E tests
pytest tests/e2e/

# Run all tests
pytest
```

### Debugging
```bash
# Check form discovery results
python scripts/check_discovery_results.py

# View training session
cat data/training_sessions/<session_id>.json

# Inspect generated scraper
cat outputs/generated_scrapers/<district>/portals/<portal>/scraper.py

# Validate system
python scripts/validate_system.py
```

## Architecture

### 4-Phase Training Pipeline

The system uses an **Orchestrator** (`agents/orchestrator.py`) that coordinates 4 specialized agents in sequence:

**Phase 1: Form Discovery** (`agents/form_discovery_agent.py`)
- Uses Claude Vision to analyze screenshots of the form
- Interactive exploration: clicks dropdowns, detects cascading fields
- JavaScript runtime monitoring (`utils/js_runtime_monitor.py`) to capture AJAX calls
- Can use hybrid strategy (Playwright + Browser Use AI) via `agents/hybrid_discovery_strategy.py`
- Output: `FormSchema` with all fields, selectors, validation rules

**Phase 2: JavaScript Analysis** (`agents/js_analyzer_agent.py`)
- Monitors JS runtime during form interaction
- Detects dynamic field population and AJAX dependencies
- Identifies event handlers (blur/focus/input)
- Output: JS complexity analysis and interaction patterns

**Phase 3: Test Validation** (`agents/test_agent.py`)
- Validates discovered schema with actual browser tests
- Tests: empty submission, field types, cascading dropdowns, full submission
- Generates confidence score (must be >0.7 to proceed)
- Output: Validated schema and test results

**Phase 4: Code Generation** (`agents/code_generator_agent.py`)
- Uses Claude Opus to generate production Python scraper
- Self-healing: validates code with `utils/scraper_validator.py`, retries up to 3 times
- Uses pattern library (`knowledge/pattern_library.py`) to learn from previous successes
- Applies code templates (`knowledge/code_templates.py`) for common UI frameworks
- Output: Production scraper saved to `outputs/generated_scrapers/<district>/portals/<portal>/`

### Key Components

**AI Client** (`config/ai_client.py`)
- Unified interface using Anthropic SDK with MegaLLM backend
- Model selection: Haiku (fast), Sonnet (balanced), Opus (powerful)
- AI response caching (`utils/ai_cache.py`) for cost savings
- Supports both native Anthropic and LangChain integration

**Base Agent** (`agents/base_agent.py`)
- All agents inherit from `BaseAgent`
- Provides: retry logic, cost tracking, status callbacks, reflection capability
- Human-in-the-loop support via `on_human_needed` callback

**Pattern Library** (`knowledge/pattern_library.py`)
- SQLite database storing successful scraper patterns
- Optional Chroma vector store for semantic similarity search
- Learns from each successful training run
- Helps future scrapers by providing similar form patterns

**Hybrid Discovery Strategy** (`agents/hybrid_discovery_strategy.py`)
- **Default strategy**: Try Playwright first (fast, cheap, deterministic)
- If confidence < 0.7 → Falls back to Browser Use AI (intelligent exploration)
- Merges insights from both approaches for best results
- Configurable via `DiscoveryConfig`

**Browser Use Integration** (`agents/browser_use_discovery_agent.py`)
- Uses browser-use library for AI-powered form exploration
- Fallback when Playwright can't achieve high confidence
- More expensive but handles complex/dynamic forms better

**Human Recorder** (`agents/human_recorder_agent.py`)
- Fallback when AI fails: record human filling the form
- Stores recording as ground truth in pattern library
- Generates scraper from human actions (100% confidence)

### Generated Scraper Structure

All generated scrapers follow this pattern:
- Class name: `{Municipality}Scraper` (e.g., `AbuaSathiScraper`)
- Main method: `async def submit_grievance(self, data: dict) -> dict`
- Test method: `async def run_test_mode(self, test_data: dict) -> dict`
- Features: retry logic, explicit waits, fallback selectors, screenshot capture, error handling
- Returns: `{"success": bool, "tracking_id": str, "screenshots": list, "errors": list}`

### Cost Tracking

The `cost_tracker` singleton (`agents/base_agent.py`) tracks:
- Total cost across all agents
- Per-model costs (Haiku/Sonnet/Opus)
- Per-agent costs
- Accessible via `Orchestrator.get_cost_breakdown()`

## Critical Implementation Details

### Select2 Dropdown Handling
Select2 dropdowns require special handling:
```python
# Don't use standard select - must trigger Select2 UI
await page.click('.select2-container')  # Open dropdown
await page.fill('.select2-search__field', 'search term')  # Search
await page.click('.select2-results__option')  # Select
await page.wait_for_timeout(1000)  # Wait for AJAX
```

### Cascading Dropdowns
When one dropdown depends on another:
1. Select parent dropdown value
2. Wait 1-2 seconds for AJAX call to populate child
3. Verify child options loaded before selecting
4. JS analyzer detects these patterns automatically

### Validation & Self-Healing
Code generation uses a validation loop:
1. Generate code with Claude Opus
2. Validate syntax (AST parsing)
3. Run `ScraperValidator` in test mode (no actual submission)
4. If validation fails: use healing prompts (`config/healing_prompts.py`) to fix
5. Retry up to 3 times
6. If all fail: offer human recording fallback

### Directory Structure for Generated Scrapers
```
outputs/generated_scrapers/
└── {district_name}/           # e.g., ranchi_district
    └── portals/
        └── {portal_name}/     # e.g., abua_sathi
            ├── __init__.py
            ├── {portal}_scraper.py
            └── tests/
                └── test_{portal}_scraper.py
```

## Known Patterns

### Portal Types Handled
- Simple HTML forms (direct POST)
- AJAX-based submissions
- Select2/Chosen.js dropdowns
- Cascading dropdowns (parent → child relationships)
- Multi-step forms
- File uploads
- ASP.NET ViewState/EventValidation

### Known Limitations
- CAPTCHA: Detected but requires human intervention
- OTP: Requires real phone numbers (not automated)
- reCAPTCHA: Can be detected but not bypassed
- Very slow AJAX (>10s): May timeout

## Key Files to Understand

When modifying core behavior, these are the critical files:

- `agents/orchestrator.py` - Main training workflow coordinator
- `agents/form_discovery_agent.py` - Form exploration and schema extraction
- `agents/code_generator_agent.py` - Scraper code generation with validation
- `config/ai_client.py` - AI model interface (Anthropic SDK)
- `config/healing_prompts.py` - Self-healing prompt templates
- `utils/scraper_validator.py` - Validates generated scrapers
- `knowledge/pattern_library.py` - Learns from successful patterns
- `cli/train_cli.py` - Main entry point for training

## Environment Variables

Required in `.env`:
```bash
api_key=your_megallm_api_key  # Get from https://app.mega-llm.com
```

Optional:
```bash
ANTHROPIC_API_URL=https://ai.megallm.io  # Default MegaLLM endpoint
```

## Testing Strategy

- **Unit tests** (`tests/unit/`): Test individual components in isolation
- **Integration tests** (`tests/integration/`): Test agent interactions
- **E2E tests** (`tests/e2e/`): Test complete training workflow
- **Live tests** (`tests/test_*_live.py`): Test generated scrapers against real portals

Use `pytest -v` for verbose output, `pytest -k <test_name>` for specific tests.

## Code Quality Notes

### Error Handling in Generated Scrapers
All generated scrapers MUST include:
- Explicit waits (NOT `time.sleep()`) - use `page.wait_for_selector()`
- Fallback selectors for each element
- Retry logic with exponential backoff (max 3 attempts)
- Screenshot capture on error
- Detailed error logging with context

### AI Model Selection
- **Haiku** (`fast`): Quick analysis, cheap ($1/$5 per 1M tokens)
- **Sonnet** (`balanced`): Form discovery, testing ($3/$15 per 1M tokens)
- **Opus** (`powerful`): Code generation, complex reasoning ($5/$25 per 1M tokens)

Selection is automatic in agents, but can be overridden in `ai_client._create_message()`.

## Adding New Features

### Adding a New Agent
1. Inherit from `BaseAgent` in `agents/base_agent.py`
2. Implement `async def _execute_attempt(self, task: Dict[str, Any]) -> Dict[str, Any]`
3. Add to Orchestrator workflow if needed
4. Update cost tracking

### Adding a New Portal
No code changes needed:
```bash
python cli/train_cli.py new_portal_name --district district_name --url https://portal.url
```

The system will automatically discover, validate, and generate a scraper.

### Extending Pattern Library
Pattern library automatically learns from successful training runs. To manually add patterns:
```python
from knowledge.pattern_library import PatternLibrary
pattern_lib = PatternLibrary()
pattern_lib.store_pattern(
    municipality_name="portal_name",
    form_url="https://...",
    form_schema=schema_dict,
    generated_code=code,
    confidence_score=0.95,
    validation_attempts=1
)
```

## Common Issues

### "API key not found"
Ensure `.env` has `api_key=your_megallm_api_key`

### "Playwright browser not installed"
Run: `python -m playwright install chromium`

### "Low confidence score" during discovery
Try hybrid discovery (enabled by default) or use `--browser-use-first` flag for complex forms.

### Generated scraper fails validation
- Check `data/training_sessions/<session_id>.json` for details
- Review screenshots in `outputs/screenshots/`
- Manual intervention: use `--no-recording` to disable human fallback

### Scraper times out on cascading dropdown
Increase wait time in generated code or JS analyzer. Look for AJAX patterns in `js_analysis_result`.
