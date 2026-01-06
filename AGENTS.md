# AGENTS.md - Developer Guide for AI Coding Agents

This file provides essential development guidance for AI coding agents working in the Grivredr codebase.

## Quick Commands

### Setup & Installation
```bash
# Quick setup (recommended)
./quickstart.sh

# Manual setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium firefox

# Configuration
cp .env.example .env  # Then add: api_key=your_megallm_api_key
```

### Build & Code Quality
```bash
# Format code (REQUIRED before commits)
black agents/ utils/ knowledge/ cli/ tests/

# Check code quality
flake8 agents/ utils/ knowledge/ cli/

# Verify setup
python verify_setup.py
```

### Testing Commands

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests only
pytest tests/e2e/            # End-to-end tests only

# Run a single test file
pytest tests/unit/test_scraper_validator.py -v

# Run a specific test function
pytest tests/unit/test_scraper_validator.py::test_validate_scraper_success -v

# Run tests with coverage
pytest --cov=agents --cov=utils --cov=knowledge

# Run tests matching pattern
pytest -k "test_discovery" -v

# Run async tests (all tests use pytest-asyncio)
pytest tests/unit/agents/test_code_generator_agent.py -v
```

### Training & Execution
```bash
# Train new portal
python cli/train_cli.py <portal_name> --district <district_name>

# Test generated scraper
python tests/test_<portal>_live.py

# Debug discovery results
python scripts/check_discovery_results.py
```

## Code Style Guidelines

### Import Organization
**REQUIRED ORDER** (following PEP 8):
```python
# 1. Standard library imports
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

# 2. Third-party packages
from playwright.async_api import async_playwright, Page, Browser
from anthropic import Anthropic

# 3. Local application imports
from agents.base_agent import BaseAgent, cost_tracker
from config.ai_client import ai_client
from utils.scraper_validator import ValidationResult
```

### Type Hints
**ALWAYS use type hints** for function parameters and return values:
```python
async def validate_scraper(
    scraper_path: Path,
    test_data: Dict[str, Any],
    expected_schema: Optional[Dict] = None
) -> ValidationResult:
    """Docstring here"""
    pass
```

### Naming Conventions
- **Classes**: PascalCase - `FormDiscoveryAgent`, `ScraperValidator`
- **Functions/methods**: snake_case - `validate_scraper()`, `discover_form()`
- **Constants**: UPPER_SNAKE_CASE - `MAX_ATTEMPTS`, `TIMEOUT_SECONDS`
- **Private methods**: Prefix with `_` - `_execute_attempt()`, `_validate_field()`
- **Async functions**: Always prefix with `async def` - `async def train_portal()`

### Docstrings
**REQUIRED** for all public classes and functions:
```python
async def train_portal(url: str, district: str) -> Dict[str, Any]:
    """
    Train AI to scrape a government portal.

    Args:
        url: Portal URL to train on
        district: District name for organization

    Returns:
        Training result with scraper path and metrics
    """
    pass
```

### Error Handling
**ALWAYS** use explicit error handling with detailed context:
```python
try:
    result = await agent.execute(task)
except TimeoutError as e:
    logger.error(f"Timeout during {operation}: {e}")
    return {"success": False, "error": f"Timeout: {e}"}
except Exception as e:
    logger.error(f"Unexpected error in {operation}: {e}", exc_info=True)
    return {"success": False, "error": str(e)}
```

### Logging
Use the `logging` module (NOT print statements):
```python
import logging
logger = logging.getLogger(__name__)

logger.info("✓ Operation completed successfully")
logger.warning("⚠ Detected potential CAPTCHA")
logger.error(f"✗ Failed to validate scraper: {error}", exc_info=True)
```

### Async/Await Patterns
**ALWAYS** use `async`/`await` for I/O operations:
```python
# ✓ GOOD - Async browser operations
async def discover_form(url: str) -> FormSchema:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(url)
        return schema

# ✗ BAD - Blocking operations
def discover_form(url: str):
    browser = playwright.chromium.launch()  # Missing await
```

## Agent Development Patterns

### Creating New Agents
**ALWAYS** inherit from `BaseAgent`:
```python
from agents.base_agent import BaseAgent, cost_tracker
from typing import Dict, Any

class NewAgent(BaseAgent):
    """Brief description of agent's purpose"""

    def __init__(self, **kwargs):
        super().__init__(name="NewAgent", max_attempts=3)
        # Agent-specific initialization

    async def _execute_attempt(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent's main logic (called by BaseAgent.execute).

        Args:
            task: Task dictionary with required parameters

        Returns:
            Result dict with "success" (bool) and data
        """
        # Implementation
        return {"success": True, "data": result}
```

### Cost Tracking
**ALWAYS** use the global `cost_tracker` from `agents.base_agent`:
```python
from agents.base_agent import cost_tracker

# BaseAgent automatically tracks costs via ai_client
# Access breakdown via:
total_cost = cost_tracker.total_cost
by_model = cost_tracker.calls_by_model
by_agent = cost_tracker.calls_by_agent
```

### Dataclass Usage
Use `@dataclass` for structured data (NOT dictionaries):
```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class FormSchema:
    """Form schema discovered by agent"""
    url: str
    municipality: str
    fields: List[Dict] = field(default_factory=list)
    confidence_score: float = 0.0
    metadata: Optional[Dict] = None
```

## Testing Patterns

### Async Test Setup
```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_async_function():
    """Test async operations"""
    result = await some_async_function()
    assert result["success"] is True
```

### Using Fixtures
```python
def test_with_fixtures(sample_form_schema, mock_ai_client):
    """Use shared fixtures from tests/conftest.py"""
    validator = ScraperValidator(test_mode=True)
    result = validator.validate_schema(sample_form_schema)
    assert result.success
```

### Mocking AI Calls
```python
from unittest.mock import patch, MagicMock

@patch('config.ai_client.ai_client')
def test_without_real_api(mock_client):
    """Mock AI client to avoid API costs in tests"""
    mock_client._create_message.return_value = '{"success": true}'
    # Test code here
```

## File Paths & Project Structure

### Generated Scrapers
```
outputs/generated_scrapers/
└── {district_name}/
    └── portals/
        └── {portal_name}/
            ├── __init__.py
            ├── {portal}_scraper.py
            └── tests/
                └── test_{portal}_scraper.py
```

### Training Sessions
```
data/training_sessions/{session_id}.json
```

### Screenshots
```
outputs/screenshots/{portal_name}/
```

## Common Patterns & Anti-Patterns

### ✓ DO THIS
- Use `pathlib.Path` for file operations
- Validate inputs at function entry
- Return structured data (dicts/dataclasses)
- Log errors with context
- Use async/await for I/O
- Keep functions under 50 lines
- Add type hints everywhere

### ✗ AVOID THIS
- Using `time.sleep()` (use `await page.wait_for_timeout()` in Playwright)
- Hard-coded file paths (use `Path(__file__).parent`)
- Print statements (use `logger`)
- Catching `Exception` without logging
- Missing type hints
- Long functions (>100 lines)
- Nested try/except blocks

## Git Commit Guidelines

Use conventional commit format:
```bash
# Examples
git commit -m "feat: add OTP handling for SMS verification"
git commit -m "fix: handle timeout in cascading dropdowns"
git commit -m "test: add unit tests for scraper validator"
git commit -m "docs: update AGENTS.md with async patterns"
git commit -m "refactor: simplify form discovery logic"
```

**Prefixes**:
- `feat:` - New feature
- `fix:` - Bug fix
- `test:` - Adding/updating tests
- `docs:` - Documentation changes
- `refactor:` - Code restructuring
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks

## Critical Implementation Notes

1. **Select2 Dropdowns** - Require special handling (see CLAUDE.md)
2. **Cascading Dropdowns** - Must wait 1-2s for AJAX between selections
3. **Validation Loop** - Code generation uses up to 3 healing attempts
4. **Browser Types** - Support chromium, firefox, webkit via `--browser` flag
5. **Cost Optimization** - Use AI cache via `utils.ai_cache.AICache`
6. **Pattern Library** - Automatically learns from successful trainings

## Environment Variables

Required in `.env`:
```bash
api_key=your_megallm_api_key  # Get from https://app.mega-llm.com
```

Optional:
```bash
ANTHROPIC_API_URL=https://ai.megallm.io  # Default endpoint
```

---

**For detailed architecture and workflow information, see CLAUDE.md**
