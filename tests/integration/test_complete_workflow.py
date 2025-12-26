"""
Integration test for complete Grivredr workflow
Tests: Form Discovery → JS Analysis → Validation → Code Generation → Pattern Storage
"""
import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from agents.orchestrator import Orchestrator
from knowledge.pattern_library import PatternLibrary


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_training_workflow_mocked():
    """
    Test the complete training workflow with mocked AI calls
    This validates that all phases integrate correctly
    """

    # Mock AI responses
    mock_form_analysis = json.dumps({
        "form_fields": [
            {
                "label": "Name",
                "type": "text",
                "selector": "#name",
                "required": True,
                "placeholder": "Enter your name"
            },
            {
                "label": "Email",
                "type": "email",
                "selector": "#email",
                "required": True,
                "placeholder": "Enter email"
            },
            {
                "label": "Complaint",
                "type": "textarea",
                "selector": "#complaint",
                "required": True,
                "placeholder": "Describe your issue"
            }
        ],
        "submit_button": {"selector": "#submit", "text": "Submit"},
        "captcha_present": False,
        "multi_step": False,
        "form_url": "https://test.com/form"
    })

    mock_scraper_code = '''
class TestScraper:
    async def submit_grievance(self, data: dict) -> dict:
        """Test scraper - always succeeds in test mode"""
        return {
            "success": True,
            "tracking_id": "TEST123",
            "message": "Test submission successful"
        }

    async def run_test_mode(self, test_data: dict) -> dict:
        """Test mode - validates without submission"""
        return {
            "success": True,
            "fields_validated": ["name", "email", "complaint"],
            "tracking_id": "TEST123"
        }
'''

    with patch('config.ai_client.ai_client') as mock_ai:
        # Mock AI client responses
        mock_ai.analyze_website_structure.return_value = mock_form_analysis
        mock_ai.generate_scraper_code.return_value = mock_scraper_code

        # Mock Playwright browser operations
        with patch('agents.form_discovery_agent.async_playwright') as mock_playwright:
            mock_browser = AsyncMock()
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.screenshot = AsyncMock(return_value=b'fake_screenshot')
            mock_page.content = AsyncMock(return_value='<html><form id="test-form"></form></html>')
            mock_browser.new_page.return_value = mock_page
            mock_playwright.return_value.__aenter__.return_value.chromium.launch.return_value = mock_browser

            # Initialize orchestrator
            orchestrator = Orchestrator(
                headless=True,
                dashboard_enabled=False
            )

            # Run complete training workflow
            result = await orchestrator.train_municipality(
                url="https://test.com/form",
                municipality="test_city"
            )

    # Assertions
    assert result["success"] is True, f"Training failed: {result.get('error')}"
    assert result["municipality"] == "test_city"
    assert "scraper_path" in result
    assert result.get("human_interventions", 0) == 0

    # Verify session was saved
    assert result["session_id"] in orchestrator.sessions
    session = orchestrator.sessions[result["session_id"]]
    assert session.status == "completed"

    # Verify all phases completed
    assert session.discovery_result is not None
    assert session.js_analysis_result is not None
    assert session.test_result is not None
    assert session.code_gen_result is not None

    print(f"✅ Complete workflow test passed!")
    print(f"   Session: {result['session_id']}")
    print(f"   Cost: ${session.total_cost:.4f}")
    print(f"   Scraper: {result['scraper_path']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pattern_library_integration():
    """
    Test that pattern library stores and retrieves patterns correctly
    """
    pattern_lib = PatternLibrary()

    # Create test pattern
    test_schema = {
        "url": "https://test.com/form",
        "fields": [
            {"name": "name", "type": "text", "required": True},
            {"name": "email", "type": "email", "required": True},
            {"name": "complaint", "type": "textarea", "required": True}
        ]
    }

    # Store pattern
    pattern_lib.store_pattern(
        municipality_name="test_city",
        form_schema=test_schema,
        code_snippets={"selector_fallbacks": "# test code"},
        confidence_score=0.95,
        success_rate=1.0
    )

    # Find similar patterns
    similar_patterns = pattern_lib.find_similar_patterns(test_schema, top_k=1)

    # Assertions
    assert len(similar_patterns) > 0
    assert similar_patterns[0].municipality_name == "test_city"
    assert similar_patterns[0].confidence_score == 0.95

    print(f"✅ Pattern library integration test passed!")
    print(f"   Stored and retrieved pattern for test_city")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_self_healing_workflow():
    """
    Test that self-healing loop works when scraper validation fails
    """

    # Mock validation that fails first, then succeeds
    validation_attempt = 0

    async def mock_validate(*args, **kwargs):
        nonlocal validation_attempt
        validation_attempt += 1

        if validation_attempt == 1:
            # First attempt fails
            from utils.scraper_validator import ValidationResult
            return ValidationResult(
                success=False,
                syntax_valid=True,
                schema_valid=False,
                execution_result=None,
                errors=["Missing required field: tracking_id"],
                warnings=[],
                confidence_score=0.4
            )
        else:
            # Second attempt succeeds
            from utils.scraper_validator import ValidationResult
            return ValidationResult(
                success=True,
                syntax_valid=True,
                schema_valid=True,
                execution_result={"success": True, "tracking_id": "TEST123"},
                errors=[],
                warnings=[],
                confidence_score=0.9
            )

    mock_scraper_code_v1 = '''
class TestScraper:
    async def submit_grievance(self, data: dict) -> dict:
        return {"success": True}  # Missing tracking_id!

    async def run_test_mode(self, test_data: dict) -> dict:
        return {"success": True}
'''

    mock_scraper_code_v2 = '''
class TestScraper:
    async def submit_grievance(self, data: dict) -> dict:
        return {"success": True, "tracking_id": "TEST123"}  # Fixed!

    async def run_test_mode(self, test_data: dict) -> dict:
        return {"success": True, "tracking_id": "TEST123"}
'''

    with patch('utils.scraper_validator.ScraperValidator.validate_scraper', side_effect=mock_validate):
        with patch('config.ai_client.ai_client') as mock_ai:
            # First generation returns broken code, second returns fixed code
            mock_ai.generate_scraper_code.side_effect = [
                mock_scraper_code_v1,
                mock_scraper_code_v2  # After healing
            ]

            from agents.code_generator_agent import CodeGeneratorAgent

            agent = CodeGeneratorAgent(enable_validation=True)

            task = {
                "schema": {
                    "url": "https://test.com/form",
                    "fields": [{"name": "name", "type": "text"}]
                },
                "js_analysis": {},
                "test_results": {}
            }

            result = await agent.execute(task)

    # Assertions
    assert result["success"] is True
    assert result["scraper"]["validation_passed"] is True
    assert result["scraper"]["validation_attempts"] == 2  # Failed once, then succeeded

    print(f"✅ Self-healing workflow test passed!")
    print(f"   Validation attempts: {result['scraper']['validation_attempts']}")
    print(f"   Confidence: {result['scraper']['confidence_score']:.2f}")


@pytest.mark.integration
def test_dashboard_integration():
    """
    Test that dashboard can be imported and started
    """
    from dashboard.app import app, socketio, emit_training_update, emit_training_complete

    # Test that Flask app is configured
    assert app.config['SECRET_KEY'] is not None

    # Test that SocketIO is initialized
    assert socketio is not None

    # Test emit functions exist
    assert callable(emit_training_update)
    assert callable(emit_training_complete)

    print(f"✅ Dashboard integration test passed!")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_js_monitoring_integration():
    """
    Test that JS monitoring captures events correctly
    """
    from utils.js_runtime_monitor import JSRuntimeMonitor

    monitor = JSRuntimeMonitor()

    # Get monitoring script
    script = monitor.get_monitoring_script()
    assert 'window.__grivredr_events' in script
    assert 'XMLHttpRequest' in script

    # Test event analysis
    mock_events = [
        {
            "type": "ajax_complete",
            "url": "https://test.com/api/cities",
            "status": 200,
            "method": "GET",
            "timestamp": 1000
        },
        {
            "type": "dom_mutation",
            "target": "#city-dropdown",
            "mutation_type": "childList",
            "timestamp": 1100
        }
    ]

    analysis = monitor.analyze_events(mock_events)

    assert analysis["has_ajax"] is True
    assert analysis["has_dynamic_content"] is True
    assert len(analysis["ajax_endpoints"]) > 0

    print(f"✅ JS monitoring integration test passed!")
    print(f"   Detected AJAX: {analysis['has_ajax']}")
    print(f"   Endpoints: {analysis['ajax_endpoints']}")


if __name__ == "__main__":
    """Run integration tests manually"""
    asyncio.run(test_complete_training_workflow_mocked())
    asyncio.run(test_pattern_library_integration())
    asyncio.run(test_self_healing_workflow())
    test_dashboard_integration()
    asyncio.run(test_js_monitoring_integration())

    print("\n" + "="*80)
    print("🎉 ALL INTEGRATION TESTS PASSED!")
    print("="*80)
