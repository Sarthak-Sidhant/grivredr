# Grivredr Testing Infrastructure

Comprehensive testing suite for the AI-powered scraper generation system.

## Overview

**Current Test Coverage Target**: 70%+ (up from ~2%)

**Test Structure**:
```
tests/
├── unit/                    # Fast, isolated tests (~200 tests)
│   ├── agents/             # Agent logic tests
│   ├── config/             # Configuration tests
│   └── utils/              # Utility function tests
├── integration/            # Component integration tests (~50 tests)
│   ├── test_complete_workflow.py
│   └── test_orchestrator_flow.py
├── e2e/                    # End-to-end tests (~5 tests, slow)
│   └── test_ranchi_municipality.py
├── fixtures/               # Test data and mocks
│   ├── sample_forms/
│   ├── mock_responses/
│   └── test_data.json
└── conftest.py            # Shared fixtures
```

---

## Quick Start

### Run All Tests
```bash
# Run everything
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# Run specific test suite
pytest tests/unit/              # Fast unit tests
pytest tests/integration/       # Integration tests
pytest tests/e2e/              # Slow E2E tests (optional)
```

### Run Single Test File
```bash
pytest tests/unit/test_scraper_validator.py -v
```

### Run Specific Test
```bash
pytest tests/unit/test_scraper_validator.py::test_validate_syntax_valid_code -v
```

### Run Tests with Output
```bash
pytest -s -v  # Show print statements
```

---

## Test Categories

### Unit Tests (Fast, ~5-10 seconds)

**Purpose**: Test individual functions and classes in isolation

**Characteristics**:
- No external dependencies (AI, browser, network)
- Uses mocks and fixtures
- Fast execution (<100ms per test)
- High test count

**Examples**:
```python
# Test scraper validator logic
def test_validate_syntax_valid_code():
    validator = ScraperValidator()
    code = "class TestScraper:\n    pass"
    assert validator.validate_syntax(code) == True

# Test cost calculation
def test_cost_tracker_haiku_model():
    tracker = CostTracker()
    cost = tracker.calculate_cost("haiku", input_tokens=1000, output_tokens=500)
    assert cost == 0.00175  # $0.25/$1.25 per 1M tokens
```

**Key Files**:
- `tests/unit/test_scraper_validator.py` - Validation logic
- `tests/unit/agents/test_base_agent.py` - Reflection loops, retries
- `tests/unit/agents/test_code_generator_agent.py` - Code generation logic
- `tests/unit/config/test_ai_client.py` - Prompt formatting, parsing

### Integration Tests (Medium, ~30-60 seconds)

**Purpose**: Test how components work together

**Characteristics**:
- Mocks expensive operations (AI calls, browser)
- Tests workflows across multiple agents
- Validates data flow between components
- Medium execution time (~1-5 seconds per test)

**Examples**:
```python
# Test complete workflow with mocked AI
@pytest.mark.asyncio
async def test_complete_training_workflow_mocked():
    with patch('config.ai_client.ai_client') as mock_ai:
        mock_ai.analyze_website_structure.return_value = mock_form_analysis
        mock_ai.generate_scraper_code.return_value = mock_scraper_code

        orchestrator = Orchestrator(headless=True)
        result = await orchestrator.train_municipality(
            url="https://test.com/form",
            municipality="test_city"
        )

        assert result["success"] is True
        assert "scraper_path" in result
```

**Key Files**:
- `tests/integration/test_complete_workflow.py` - Full training pipeline
- `tests/integration/test_validation_pipeline.py` - Generation → Validation → Healing
- `tests/integration/test_orchestrator_flow.py` - 4-phase workflow

### E2E Tests (Slow, ~5-15 minutes)

**Purpose**: Test on real websites with real AI calls

**Characteristics**:
- Uses real AI API calls (costs money!)
- Real browser automation
- Tests complete user workflows
- Slow execution (~5-10 minutes per test)
- Mark with `@pytest.mark.slow` to skip by default

**Examples**:
```python
@pytest.mark.slow
@pytest.mark.asyncio
async def test_ranchi_training_complete():
    """Test complete training on Ranchi Smart City portal"""
    orchestrator = Orchestrator(headless=True)
    result = await orchestrator.train_municipality(
        url="https://smartranchi.in/Portal/View/ComplaintRegistration.aspx",
        municipality="ranchi_test"
    )

    assert result["success"] is True

    # Test generated scraper
    scraper = import_scraper(result["scraper_path"])
    test_result = await scraper.run_test_mode(test_data)
    assert test_result["success"] is True
```

**Running E2E Tests**:
```bash
# Run all E2E tests (slow, costs money!)
pytest tests/e2e/ -v

# Run only E2E tests marked as "slow"
pytest -m slow

# Skip slow tests (default in CI)
pytest -m "not slow"
```

---

## Test Infrastructure

### Fixtures (`conftest.py`)

Shared test data and mocks available to all tests:

**AI Mocks**:
```python
@pytest.fixture
def mock_ai_client():
    """Mock AI client for testing without API calls"""
    with patch('config.ai_client.ai_client') as mock:
        mock.analyze_website_structure.return_value = mock_form_analysis
        mock.generate_scraper_code.return_value = mock_scraper_code
        yield mock
```

**Playwright Mocks**:
```python
@pytest.fixture
def mock_playwright():
    """Mock Playwright browser for testing without real browser"""
    with patch('agents.form_discovery_agent.async_playwright') as mock:
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        # ... setup mocks
        yield mock
```

**Sample Data**:
```python
@pytest.fixture
def sample_form_schema():
    """Standard form schema for testing"""
    return {
        "url": "https://test.com/form",
        "fields": [
            {"name": "name", "type": "text", "required": True},
            {"name": "email", "type": "email", "required": True}
        ]
    }
```

### Test Helpers

**Validation Result Builders**:
```python
@pytest.fixture
def mock_validation_result_success():
    return ValidationResult(
        success=True,
        syntax_valid=True,
        schema_valid=True,
        execution_result={"success": True},
        errors=[],
        warnings=[],
        confidence_score=0.9
    )
```

---

## CI/CD Integration

### GitHub Actions Workflow

**File**: `.github/workflows/test.yml`

**Triggers**:
- On every push to `main`
- On every pull request
- Manual workflow dispatch

**Jobs**:

1. **Linting**:
   - Black (code formatting)
   - Flake8 (style checking)
   - MyPy (type checking)

2. **Unit Tests**:
   - Fast tests only
   - Required to pass

3. **Integration Tests**:
   - Mocked AI/browser
   - Required to pass

4. **Coverage**:
   - Minimum 70% coverage required
   - Uploads to Codecov

**Configuration**:
```yaml
- name: Run tests with coverage
  run: |
    pytest tests/unit/ tests/integration/ \
      --cov=. \
      --cov-report=xml \
      --cov-report=term \
      --cov-fail-under=70
```

**E2E Tests**:
- Skipped in CI by default (too slow, costs money)
- Run manually before releases

---

## Writing New Tests

### Unit Test Template

```python
"""
Test description
"""
import pytest
from unittest.mock import patch, MagicMock

from module_to_test import ClassToTest


def test_function_name():
    """Test description"""
    # Arrange
    instance = ClassToTest()
    input_data = {"key": "value"}

    # Act
    result = instance.method_to_test(input_data)

    # Assert
    assert result["success"] is True
    assert "expected_key" in result


@pytest.mark.asyncio
async def test_async_function():
    """Test async function"""
    # Arrange
    instance = ClassToTest()

    # Act
    result = await instance.async_method()

    # Assert
    assert result is not None
```

### Integration Test Template

```python
"""
Integration test description
"""
import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_workflow(mock_ai_client, sample_form_schema):
    """Test workflow with mocked dependencies"""
    # Arrange
    with patch('agents.form_discovery_agent.async_playwright') as mock_playwright:
        # Setup mocks
        mock_browser = AsyncMock()
        # ... configure mocks

        # Act
        from agents.orchestrator import Orchestrator
        orchestrator = Orchestrator(headless=True)
        result = await orchestrator.train_municipality(
            url="https://test.com/form",
            municipality="test_city"
        )

        # Assert
        assert result["success"] is True
```

### E2E Test Template

```python
"""
End-to-end test (SLOW, costs money!)
"""
import pytest

@pytest.mark.slow
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_real_website():
    """Test on real website (requires API key)"""
    # Requires: OPENAI_API_KEY environment variable
    from agents.orchestrator import Orchestrator

    orchestrator = Orchestrator(headless=True)
    result = await orchestrator.train_municipality(
        url="https://real-website.com/form",
        municipality="test_city"
    )

    assert result["success"] is True
    # ... validate generated scraper
```

---

## Debugging Failed Tests

### View Detailed Output
```bash
pytest tests/unit/test_file.py -v -s
# -v: verbose
# -s: show print statements
```

### Debug Single Test
```bash
pytest tests/unit/test_file.py::test_function_name --pdb
# Drops into debugger on failure
```

### Run with Coverage Report
```bash
pytest --cov=. --cov-report=html
# Open htmlcov/index.html in browser
```

### Check What's Not Covered
```bash
pytest --cov=. --cov-report=term-missing
# Shows line numbers that aren't covered
```

---

## Testing Best Practices

### 1. Fast Tests First
- Write unit tests before integration tests
- Mock expensive operations (AI, browser, network)
- Keep tests under 100ms when possible

### 2. Descriptive Names
```python
# ✅ GOOD
def test_validation_fails_when_syntax_invalid():
    pass

# ❌ BAD
def test_validation():
    pass
```

### 3. Arrange-Act-Assert Pattern
```python
def test_example():
    # Arrange: Setup test data
    validator = ScraperValidator()
    code = "invalid python code"

    # Act: Execute the function
    result = validator.validate_syntax(code)

    # Assert: Verify expectations
    assert result is False
```

### 4. One Assertion Per Test (Ideally)
```python
# ✅ GOOD - Test one thing
def test_validation_success_returns_true():
    assert validate("valid code") is True

def test_validation_failure_returns_false():
    assert validate("invalid code") is False

# ❌ BAD - Testing multiple things
def test_validation():
    assert validate("valid code") is True
    assert validate("invalid code") is False
    assert validate("") is False
```

### 5. Use Fixtures for Common Setup
```python
@pytest.fixture
def scraper_validator():
    """Reusable validator instance"""
    return ScraperValidator(enable_validation=True)

def test_with_fixture(scraper_validator):
    result = scraper_validator.validate_syntax("code")
    assert result is True
```

---

## Test Markers

Mark tests for selective execution:

```python
@pytest.mark.unit         # Fast unit test
@pytest.mark.integration  # Integration test
@pytest.mark.e2e          # End-to-end test
@pytest.mark.slow         # Slow test (skip in CI)
@pytest.mark.asyncio      # Async test (requires pytest-asyncio)
```

**Run specific markers**:
```bash
pytest -m unit           # Only unit tests
pytest -m integration    # Only integration tests
pytest -m "not slow"     # Skip slow tests (CI default)
```

---

## Coverage Goals

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| Core agents | 80%+ | 🔴 Critical |
| Utilities | 90%+ | 🔴 Critical |
| AI client | 70%+ | 🟡 High |
| Dashboard | 50%+ | 🟢 Medium |
| Scripts | 30%+ | 🟢 Low |

**Overall Target**: 70% minimum

---

## Common Issues

### Issue 1: Async Test Not Running
**Problem**: Test decorated with `@pytest.mark.asyncio` doesn't run

**Solution**: Install pytest-asyncio
```bash
pip install pytest-asyncio
```

### Issue 2: Mock Not Applied
**Problem**: Mock doesn't seem to affect test

**Solution**: Check import path is correct
```python
# ❌ WRONG
with patch('ai_client.AIClient') as mock:
    pass

# ✅ RIGHT
with patch('config.ai_client.ai_client') as mock:
    pass
```

### Issue 3: Fixture Not Found
**Problem**: pytest can't find fixture

**Solution**: Check `conftest.py` is in parent directory
```
tests/
├── conftest.py        # ✅ Fixtures available to all tests
├── unit/
│   ├── conftest.py   # ✅ Fixtures for unit tests only
│   └── test_file.py
```

---

## Manual Testing

For components that are hard to unit test:

### Test Dashboard Manually
```bash
python dashboard/app.py
# Open http://localhost:5000
# Verify UI loads, WebSocket connects
```

### Test Scraper Generation Manually
```bash
python scripts/test_ranchi.py
# Watch browser, check logs
```

### Test Pattern Library Manually
```bash
python -m knowledge.pattern_library
# Check database is created, patterns stored
```

---

## Next Steps

1. **Achieve 70% Coverage**:
   - Write missing unit tests for agents
   - Add integration tests for orchestrator phases
   - Mock all expensive operations

2. **Add Performance Tests**:
   - Test generation time <15 min per municipality
   - Test memory usage under load
   - Test concurrent training sessions

3. **Add Security Tests**:
   - Test SQL injection in pattern library
   - Test XSS in dashboard
   - Test secrets not logged

4. **Improve E2E Tests**:
   - Test on 10+ different municipal websites
   - Validate success rate >85%
   - Test self-healing loop

---

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [Coverage.py](https://coverage.readthedocs.io/)

---

## Questions?

If tests are failing or you need help:
1. Check error message carefully
2. Run with `-v -s` for verbose output
3. Use `--pdb` to debug
4. Check this README for common issues
5. Review example tests in the codebase
