"""
Unit tests for ScraperValidator
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from utils.scraper_validator import ScraperValidator, ValidationResult


class TestScraperValidator:
    """Test suite for ScraperValidator"""

    def test_init(self):
        """Test validator initialization"""
        validator = ScraperValidator(test_mode=True, timeout=30)

        assert validator.test_mode is True
        assert validator.timeout == 30

    def test_init_defaults(self):
        """Test validator initialization with defaults"""
        validator = ScraperValidator()

        assert validator.test_mode is True
        assert validator.timeout == 60

    def test_validation_result_to_dict(self):
        """Test ValidationResult.to_dict() method"""
        result = ValidationResult(
            success=True,
            scraper_id="test_scraper",
            execution_status="passed",
            execution_errors=[],
            execution_time=5.2
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["success"] is True
        assert result_dict["scraper_id"] == "test_scraper"
        assert result_dict["execution_status"] == "passed"
        assert result_dict["execution_time"] == 5.2

    def test_validate_syntax_valid_code(self):
        """Test syntax validation with valid Python code"""
        validator = ScraperValidator()

        # Create temp file with valid code
        temp_path = Path("/tmp/test_valid_scraper.py")
        temp_path.write_text("""
class TestScraper:
    def __init__(self):
        self.name = "test"

    async def submit_grievance(self, data):
        return {"success": True}
""")

        try:
            is_valid, error = validator.validate_syntax(temp_path)
            assert is_valid is True
            assert error is None
        finally:
            temp_path.unlink()

    def test_validate_syntax_invalid_code(self):
        """Test syntax validation with invalid Python code"""
        validator = ScraperValidator()

        # Create temp file with invalid code
        temp_path = Path("/tmp/test_invalid_scraper.py")
        temp_path.write_text("""
class TestScraper
    def __init__(self):  # Missing colon above
        self.name = "test"
""")

        try:
            is_valid, error = validator.validate_syntax(temp_path)
            assert is_valid is False
            assert error is not None
            assert "Syntax error" in error or "syntax" in error.lower()
        finally:
            temp_path.unlink()

    @pytest.mark.asyncio
    async def test_find_scraper_class(self):
        """Test finding scraper class in module"""
        validator = ScraperValidator()

        # Create a mock module
        mock_module = Mock()

        # Add a scraper class
        class TestScraper:
            pass

        # Add non-scraper class
        class OtherClass:
            pass

        mock_module.TestScraper = TestScraper
        mock_module.OtherClass = OtherClass
        mock_module.__dict__ = {
            'TestScraper': TestScraper,
            'OtherClass': OtherClass
        }

        # Mock dir() to return class names
        with patch('builtins.dir', return_value=['TestScraper', 'OtherClass']):
            with patch('builtins.getattr', side_effect=lambda m, name: getattr(m, name)):
                scraper_class = validator._find_scraper_class(mock_module)

                assert scraper_class is TestScraper

    def test_validate_schema_success(self):
        """Test schema validation with matching output"""
        validator = ScraperValidator()

        execution_result = {
            "success": True,
            "tracking_id": "ABC123",
            "message": "Submitted successfully"
        }

        expected_schema = {
            "required_fields": ["success", "tracking_id", "message"],
            "field_types": {
                "success": "bool",
                "tracking_id": "str",
                "message": "str"
            }
        }

        result = ValidationResult(
            success=False,
            scraper_id="test",
            execution_status="pending"
        )

        is_valid = validator._validate_schema(
            execution_result,
            expected_schema,
            result
        )

        assert is_valid is True
        assert len(result.schema_errors) == 0

    def test_validate_schema_missing_field(self):
        """Test schema validation with missing required field"""
        validator = ScraperValidator()

        execution_result = {
            "success": True,
            "message": "Submitted"
            # Missing tracking_id
        }

        expected_schema = {
            "required_fields": ["success", "tracking_id", "message"]
        }

        result = ValidationResult(
            success=False,
            scraper_id="test",
            execution_status="pending"
        )

        is_valid = validator._validate_schema(
            execution_result,
            expected_schema,
            result
        )

        assert is_valid is False
        assert len(result.schema_errors) > 0
        assert any("tracking_id" in err for err in result.schema_errors)

    def test_validate_schema_wrong_type(self):
        """Test schema validation with wrong field type"""
        validator = ScraperValidator()

        execution_result = {
            "success": "true",  # Should be bool, not str
            "message": "Submitted"
        }

        expected_schema = {
            "required_fields": ["success", "message"],
            "field_types": {
                "success": "bool",
                "message": "str"
            }
        }

        result = ValidationResult(
            success=False,
            scraper_id="test",
            execution_status="pending"
        )

        is_valid = validator._validate_schema(
            execution_result,
            expected_schema,
            result
        )

        assert is_valid is False
        assert len(result.schema_errors) > 0
        assert any("wrong type" in err for err in result.schema_errors)
