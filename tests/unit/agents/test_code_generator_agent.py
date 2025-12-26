"""
Unit tests for CodeGeneratorAgent
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from agents.code_generator_agent import CodeGeneratorAgent, GeneratedScraper
from utils.scraper_validator import ValidationResult


class TestCodeGeneratorAgent:
    """Test suite for CodeGeneratorAgent"""

    def test_init(self):
        """Test agent initialization"""
        agent = CodeGeneratorAgent(enable_validation=True)

        assert agent.name == "CodeGeneratorAgent"
        assert agent.max_attempts == 3
        assert agent.enable_validation is True
        assert agent.validator is not None

    def test_init_validation_disabled(self):
        """Test initialization with validation disabled"""
        agent = CodeGeneratorAgent(enable_validation=False)

        assert agent.enable_validation is False

    def test_extract_class_name(self):
        """Test extracting class name from code"""
        agent = CodeGeneratorAgent()

        code = """
class TestMunicipalityScraper:
    def __init__(self):
        pass
"""
        class_name = agent._extract_class_name(code)
        assert class_name == "TestMunicipalityScraper"

    def test_extract_class_name_no_match(self):
        """Test extracting class name when no class found"""
        agent = CodeGeneratorAgent()

        code = """
def some_function():
    pass
"""
        class_name = agent._extract_class_name(code)
        assert class_name == "UnknownScraper"

    def test_generate_test_data(self):
        """Test generating test data from schema"""
        agent = CodeGeneratorAgent()

        schema = {
            "fields": [
                {"name": "full_name", "type": "text"},
                {"name": "mobile", "type": "text"},
                {"name": "email", "type": "text"},
                {"name": "category", "type": "dropdown", "options": ["Option1", "Option2"]},
                {"name": "description", "type": "textarea"},
                {"name": "agree", "type": "checkbox"},
                {"name": "document", "type": "file"}
            ]
        }

        test_data = agent._generate_test_data(schema)

        # Check mobile field
        assert "mobile" in test_data
        assert test_data["mobile"] == "9876543210"

        # Check email field
        assert "email" in test_data
        assert "@" in test_data["email"]

        # Check name field
        assert "full_name" in test_data

        # Check dropdown
        assert test_data["category"] == "Option1"

        # Check textarea
        assert "description" in test_data
        assert len(test_data["description"]) > 0

        # Check checkbox
        assert test_data["agree"] is True

        # Check file (should be None in test mode)
        assert test_data["document"] is None

    def test_calculate_confidence_passed_first_try(self):
        """Test confidence calculation when validation passes on first try"""
        agent = CodeGeneratorAgent()

        confidence = agent._calculate_confidence(
            syntax_valid=True,
            validation_passed=True,
            validation_attempts=1,
            test_results={"confidence_score": 0.8}
        )

        # Should get bonus for passing first try
        assert confidence >= 0.8
        assert confidence <= 1.0

    def test_calculate_confidence_failed_validation(self):
        """Test confidence calculation when validation fails"""
        agent = CodeGeneratorAgent()

        confidence = agent._calculate_confidence(
            syntax_valid=True,
            validation_passed=False,
            validation_attempts=3,
            test_results={"confidence_score": 0.8}
        )

        # Should be significantly reduced
        assert confidence < 0.6

    def test_calculate_confidence_syntax_error(self):
        """Test confidence calculation when syntax is invalid"""
        agent = CodeGeneratorAgent()

        confidence = agent._calculate_confidence(
            syntax_valid=False,
            validation_passed=True,
            validation_attempts=1,
            test_results={"confidence_score": 0.8}
        )

        # Should be heavily penalized
        assert confidence < 0.5

    def test_calculate_confidence_multiple_healing_attempts(self):
        """Test confidence when multiple healing attempts needed"""
        agent = CodeGeneratorAgent()

        confidence = agent._calculate_confidence(
            syntax_valid=True,
            validation_passed=True,
            validation_attempts=3,
            test_results={"confidence_score": 0.9}
        )

        # Should be reduced but not as much as failure
        assert confidence < 0.9
        assert confidence > 0.6

    def test_validate_syntax_valid(self):
        """Test syntax validation with valid code"""
        agent = CodeGeneratorAgent()

        valid_code = """
class TestScraper:
    async def submit_grievance(self, data):
        return {"success": True}
"""

        is_valid = agent._validate_syntax(valid_code)
        assert is_valid is True

    def test_validate_syntax_invalid(self):
        """Test syntax validation with invalid code"""
        agent = CodeGeneratorAgent()

        invalid_code = """
class TestScraper
    async def submit_grievance(self, data):  # Missing colon
        return {"success": True}
"""

        is_valid = agent._validate_syntax(invalid_code)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_execute_attempt_validation_disabled(self, mock_ai_client, sample_form_schema):
        """Test code generation with validation disabled"""
        agent = CodeGeneratorAgent(enable_validation=False)

        # Mock AI response with valid Python code
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """
```python
class TestMunicipalityScraper:
    async def submit_grievance(self, data):
        return {"success": True, "message": "Test"}
```
"""
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200

        with patch('config.ai_client.ai_client.client.chat.completions.create', return_value=mock_response):
            result = await agent._execute_attempt({
                "schema": sample_form_schema,
                "js_analysis": {},
                "test_results": {"confidence_score": 0.8}
            })

        assert result["success"] is True
        assert "scraper" in result
        assert result["scraper"]["syntax_valid"] is True
        # Validation should be skipped, so assumed pass
        assert result["scraper"]["validation_passed"] is True

    @pytest.mark.asyncio
    async def test_heal_scraper(self, mock_ai_client, sample_form_schema, mock_validation_result_failure):
        """Test self-healing functionality"""
        agent = CodeGeneratorAgent()

        failed_code = """
class TestScraper:
    async def submit_grievance(self, data):
        # This code fails
        return {"success": False}
"""

        # Mock AI healing response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """
```python
class TestScraper:
    async def submit_grievance(self, data):
        # Fixed code
        return {"success": True, "message": "Fixed"}
```
"""
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 150
        mock_response.usage.completion_tokens = 250

        with patch('config.ai_client.ai_client.client.chat.completions.create', return_value=mock_response):
            healed_code = await agent._heal_scraper(
                failed_code,
                mock_validation_result_failure,
                sample_form_schema
            )

        assert "class TestScraper" in healed_code
        assert "Fixed code" in healed_code or "Fixed" in healed_code
        assert len(healed_code) > 0
