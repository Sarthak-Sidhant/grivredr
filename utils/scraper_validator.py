"""
Scraper Validator - Validates generated scrapers before production deployment
"""
import asyncio
import importlib.util
import logging
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.mock_manager import PlaywrightMockContext

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of scraper validation"""
    success: bool
    scraper_id: str
    execution_status: str  # "passed", "failed", "timeout", "error"
    execution_errors: List[str] = field(default_factory=list)
    schema_errors: List[str] = field(default_factory=list)
    timeout_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time: float = 0.0
    captured_operations: List[Dict] = field(default_factory=list)
    screenshot_path: Optional[str] = None
    validation_log: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "scraper_id": self.scraper_id,
            "execution_status": self.execution_status,
            "execution_errors": self.execution_errors,
            "schema_errors": self.schema_errors,
            "timeout_issues": self.timeout_issues,
            "warnings": self.warnings,
            "execution_time": self.execution_time,
            "captured_operations": self.captured_operations,
            "screenshot_path": self.screenshot_path
        }


class ScraperValidator:
    """
    Validates generated scrapers by executing them in a sandboxed environment
    """

    def __init__(self, test_mode: bool = True, timeout: int = 60):
        """
        Initialize validator

        Args:
            test_mode: If True, mock browser operations (no real submissions)
            timeout: Maximum execution time in seconds
        """
        self.test_mode = test_mode
        self.timeout = timeout

    async def validate_scraper(
        self,
        scraper_path: Path,
        test_data: Dict[str, Any],
        expected_schema: Optional[Dict] = None
    ) -> ValidationResult:
        """
        Validate a generated scraper by executing it with test data

        Args:
            scraper_path: Path to the generated scraper Python file
            test_data: Test data to use for submission
            expected_schema: Expected output schema for validation

        Returns:
            ValidationResult with detailed results
        """
        scraper_id = scraper_path.stem
        result = ValidationResult(
            success=False,
            scraper_id=scraper_id,
            execution_status="pending"
        )

        logger.info(f"🧪 Validating scraper: {scraper_id}")

        try:
            # Step 1: Load the scraper module
            scraper_module = await self._load_scraper_module(scraper_path)
            if not scraper_module:
                result.execution_status = "error"
                result.execution_errors.append("Failed to load scraper module")
                return result

            # Step 2: Find the scraper class
            scraper_class = self._find_scraper_class(scraper_module)
            if not scraper_class:
                result.execution_status = "error"
                result.execution_errors.append("No scraper class found in module")
                return result

            # Step 3: Execute the scraper in test mode
            execution_result = await self._execute_scraper(
                scraper_class,
                test_data,
                result
            )

            # Step 4: Validate the output schema
            if expected_schema and execution_result:
                schema_valid = self._validate_schema(
                    execution_result,
                    expected_schema,
                    result
                )

            # Step 5: Determine overall success
            result.success = (
                result.execution_status == "passed" and
                len(result.execution_errors) == 0 and
                len(result.schema_errors) == 0
            )

            logger.info(f"✅ Validation complete: {scraper_id} - {'PASSED' if result.success else 'FAILED'}")

        except asyncio.TimeoutError:
            result.execution_status = "timeout"
            result.timeout_issues.append(f"Execution exceeded {self.timeout}s timeout")
            logger.error(f"⏱️ Validation timeout: {scraper_id}")

        except Exception as e:
            result.execution_status = "error"
            result.execution_errors.append(f"Unexpected error: {str(e)}")
            result.validation_log += f"\n\nException:\n{traceback.format_exc()}"
            logger.error(f"❌ Validation error: {scraper_id} - {e}")

        return result

    async def _load_scraper_module(self, scraper_path: Path):
        """Dynamically load scraper module"""
        try:
            spec = importlib.util.spec_from_file_location(
                scraper_path.stem,
                scraper_path
            )
            if not spec or not spec.loader:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[scraper_path.stem] = module
            spec.loader.exec_module(module)

            logger.info(f"✓ Loaded module: {scraper_path.stem}")
            return module

        except Exception as e:
            logger.error(f"Failed to load module: {e}")
            return None

    def _find_scraper_class(self, module):
        """Find the main scraper class in the module"""
        # Look for classes ending with "Scraper"
        for name in dir(module):
            if name.endswith("Scraper"):
                cls = getattr(module, name)
                if isinstance(cls, type):
                    logger.info(f"✓ Found scraper class: {name}")
                    return cls

        logger.error("No scraper class found (should end with 'Scraper')")
        return None

    async def _execute_scraper(
        self,
        scraper_class,
        test_data: Dict[str, Any],
        result: ValidationResult
    ) -> Optional[Dict]:
        """
        Execute the scraper with test data

        Returns:
            Scraper output dict or None on failure
        """
        import time
        start_time = time.time()

        try:
            # Create scraper instance
            scraper_instance = scraper_class(headless=True)

            # Check if scraper has run_test_mode method
            if hasattr(scraper_instance, 'run_test_mode'):
                logger.info("✓ Using run_test_mode() method")
                execution_result = await asyncio.wait_for(
                    scraper_instance.run_test_mode(test_data),
                    timeout=self.timeout
                )
            elif hasattr(scraper_instance, 'submit_grievance'):
                # Fallback: use mock context
                logger.info("✓ Using submit_grievance() with mocking")
                with PlaywrightMockContext(test_mode=self.test_mode) as mock_mgr:
                    execution_result = await asyncio.wait_for(
                        scraper_instance.submit_grievance(test_data),
                        timeout=self.timeout
                    )
                    result.captured_operations = mock_mgr.get_captured_calls()
            else:
                result.execution_errors.append(
                    "Scraper has no run_test_mode() or submit_grievance() method"
                )
                result.execution_status = "error"
                return None

            result.execution_time = time.time() - start_time

            # Check execution result
            if isinstance(execution_result, dict):
                if execution_result.get("success"):
                    result.execution_status = "passed"
                    logger.info(f"✓ Scraper executed successfully in {result.execution_time:.2f}s")
                else:
                    result.execution_status = "failed"
                    result.execution_errors.append(
                        execution_result.get("error", "Unknown error")
                    )
                    logger.warning(f"⚠️ Scraper execution failed: {execution_result.get('error')}")
            else:
                result.execution_status = "failed"
                result.execution_errors.append(
                    f"Invalid return type: {type(execution_result)}"
                )

            return execution_result

        except asyncio.TimeoutError:
            raise
        except Exception as e:
            result.execution_status = "error"
            result.execution_errors.append(f"Execution exception: {str(e)}")
            result.validation_log += f"\n\nExecution trace:\n{traceback.format_exc()}"
            logger.error(f"❌ Execution error: {e}")
            return None

    def _validate_schema(
        self,
        execution_result: Dict,
        expected_schema: Dict,
        result: ValidationResult
    ) -> bool:
        """
        Validate that execution result matches expected schema

        Args:
            execution_result: Actual output from scraper
            expected_schema: Expected fields and types
            result: ValidationResult to update with errors

        Returns:
            True if schema is valid
        """
        schema_valid = True

        # Check required fields
        required_fields = expected_schema.get("required_fields", [])
        for field in required_fields:
            if field not in execution_result:
                result.schema_errors.append(f"Missing required field: {field}")
                schema_valid = False
            elif execution_result[field] is None:
                result.warnings.append(f"Required field is None: {field}")

        # Check field types
        expected_types = expected_schema.get("field_types", {})
        for field, expected_type in expected_types.items():
            if field in execution_result:
                actual_type = type(execution_result[field]).__name__
                if actual_type != expected_type:
                    result.schema_errors.append(
                        f"Field '{field}' has wrong type: expected {expected_type}, got {actual_type}"
                    )
                    schema_valid = False

        if schema_valid:
            logger.info("✓ Schema validation passed")
        else:
            logger.warning(f"⚠️ Schema validation failed: {len(result.schema_errors)} errors")

        return schema_valid

    def validate_syntax(self, scraper_path: Path) -> tuple[bool, Optional[str]]:
        """
        Validate Python syntax of scraper code

        Returns:
            (is_valid, error_message)
        """
        import ast

        try:
            with open(scraper_path, 'r') as f:
                code = f.read()

            ast.parse(code)
            logger.info(f"✓ Syntax validation passed: {scraper_path.name}")
            return True, None

        except SyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.msg}"
            logger.error(f"❌ Syntax validation failed: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(f"❌ Syntax validation failed: {error_msg}")
            return False, error_msg
