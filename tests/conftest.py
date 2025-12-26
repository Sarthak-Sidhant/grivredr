"""
Pytest configuration and shared fixtures
"""
import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Configure async test support
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture
def mock_ai_client():
    """Mock AIClient to avoid real API calls"""
    with patch('config.ai_client.ai_client') as mock:
        # Mock the client.chat.completions.create method
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"success": true}'
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200

        mock.client.chat.completions.create.return_value = mock_response
        yield mock


@pytest.fixture
def mock_playwright():
    """Mock Playwright browser automation"""
    with patch('playwright.async_api.async_playwright') as mock:
        # Create mock browser context
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_context = MagicMock()

        async def mock_start():
            return mock

        async def mock_launch(*args, **kwargs):
            return mock_browser

        async def mock_new_context(*args, **kwargs):
            return mock_context

        async def mock_new_page():
            return mock_page

        mock.start = mock_start
        mock.chromium.launch = mock_launch
        mock_browser.new_context = mock_new_context
        mock_context.new_page = mock_new_page

        yield mock


@pytest.fixture
def sample_form_schema():
    """Sample form schema for testing"""
    return {
        "url": "https://example.com/grievance-form",
        "municipality": "test_municipality",
        "title": "Test Grievance Form",
        "fields": [
            {
                "name": "full_name",
                "label": "Full Name",
                "type": "text",
                "selector": "#fullName",
                "required": True,
                "placeholder": "Enter your full name"
            },
            {
                "name": "mobile",
                "label": "Mobile Number",
                "type": "text",
                "selector": "#mobile",
                "required": True,
                "validation_pattern": "^[0-9]{10}$"
            },
            {
                "name": "email",
                "label": "Email Address",
                "type": "text",
                "selector": "#email",
                "required": False
            },
            {
                "name": "category",
                "label": "Complaint Category",
                "type": "dropdown",
                "selector": "#category",
                "required": True,
                "options": ["Water Supply", "Electricity", "Roads", "Garbage"]
            },
            {
                "name": "description",
                "label": "Complaint Description",
                "type": "textarea",
                "selector": "#description",
                "required": True
            }
        ],
        "submit_button": {
            "selector": "button[type='submit']",
            "text": "Submit Complaint"
        },
        "multi_step": False,
        "requires_captcha": False,
        "confidence_score": 0.85
    }


@pytest.fixture
def sample_test_data():
    """Sample test data for form submission"""
    return {
        "full_name": "Test User",
        "mobile": "9876543210",
        "email": "test@example.com",
        "category": "Water Supply",
        "description": "This is a test complaint for automated testing."
    }


@pytest.fixture
def mock_validation_result_success():
    """Mock successful validation result"""
    from utils.scraper_validator import ValidationResult

    return ValidationResult(
        success=True,
        scraper_id="test_scraper",
        execution_status="passed",
        execution_errors=[],
        schema_errors=[],
        timeout_issues=[],
        warnings=[],
        execution_time=5.2,
        captured_operations=[
            {"operation": "goto", "url": "https://example.com"},
            {"operation": "fill", "selector": "#fullName", "value": "Test User"},
            {"operation": "click", "selector": "button[type='submit']"}
        ]
    )


@pytest.fixture
def mock_validation_result_failure():
    """Mock failed validation result"""
    from utils.scraper_validator import ValidationResult

    return ValidationResult(
        success=False,
        scraper_id="test_scraper",
        execution_status="failed",
        execution_errors=[
            "Element not found: button[type='submit']",
            "Timeout waiting for page load"
        ],
        schema_errors=["Missing required field: tracking_id"],
        timeout_issues=[],
        warnings=["Detected potential CAPTCHA"],
        execution_time=30.0,
        captured_operations=[]
    )


@pytest.fixture
def fixtures_dir():
    """Path to fixtures directory"""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture(fixtures_dir):
    """Helper to load JSON fixtures"""
    def _load(filename: str):
        fixture_path = fixtures_dir / filename
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found: {filename}")

        with open(fixture_path, 'r') as f:
            return json.load(f)

    return _load


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
