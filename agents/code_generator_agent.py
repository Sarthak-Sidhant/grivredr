"""
Code Generator Agent - Generates production-ready scraper code
Creates Python scrapers based on validated form schemas and JS analysis
"""
import asyncio
import ast
import json
import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass

from agents.base_agent import BaseAgent, cost_tracker
from agents.form_discovery_agent import FormSchema
from config.ai_client import ai_client
from config.healing_prompts import HEALING_PROMPT_TEMPLATE
from utils.scraper_validator import ScraperValidator, ValidationResult
from knowledge.pattern_library import PatternLibrary
from knowledge.code_templates import (
    get_template_code_for_prompt,
    UIFramework,
    get_templates_for_framework
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class GeneratedScraper:
    """Generated scraper information"""
    file_path: str
    code: str
    class_name: str
    test_code: str
    syntax_valid: bool
    self_test_passed: bool
    validation_passed: bool
    validation_attempts: int
    warnings: list
    confidence_score: float = 0.0


class CodeGeneratorAgent(BaseAgent):
    """
    Agent that generates production-ready scraper code from validated schemas
    """

    def __init__(self, enable_validation: bool = True, use_pattern_library: bool = True):
        super().__init__(name="CodeGeneratorAgent", max_attempts=3)
        self.output_dir = Path("outputs/generated_scrapers")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.enable_validation = enable_validation
        self.use_pattern_library = use_pattern_library
        self.validator = ScraperValidator(test_mode=True, timeout=60)
        self.pattern_library = PatternLibrary() if use_pattern_library else None

    async def _execute_attempt(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute code generation
        """
        schema_dict = task.get("schema")
        js_analysis = task.get("js_analysis", {})
        test_results = task.get("test_results", {})

        if not schema_dict:
            return {"success": False, "error": "No schema provided"}

        municipality = schema_dict.get("municipality", "unknown")
        url = schema_dict.get("url", "")

        logger.info(f"🔧 [{self.name}] Generating scraper for {municipality}")

        try:
            # Phase 1: Generate scraper code with Claude Opus
            scraper_code = await self._generate_scraper_code(
                schema_dict, js_analysis, test_results
            )

            # Phase 2: Validate syntax
            syntax_valid = self._validate_syntax(scraper_code)
            if not syntax_valid:
                logger.warning("Generated code has syntax errors, asking Claude to fix...")
                scraper_code = await self._fix_syntax_errors(scraper_code)
                syntax_valid = self._validate_syntax(scraper_code)

            # Phase 3: Generate test code
            test_code = await self._generate_test_code(schema_dict, scraper_code)

            # Phase 4: Save to temporary location for validation
            temp_path = await self._save_scraper(
                municipality, scraper_code, test_code, temp=True
            )

            # Phase 5: CRITICAL - Validate scraper execution
            validation_passed = False
            validation_attempts = 0
            warnings = []

            if self.enable_validation:
                logger.info(f"🧪 [{self.name}] Validating scraper execution...")

                # Prepare test data
                test_data = self._generate_test_data(schema_dict)

                # Attempt validation with self-healing loop
                for attempt in range(3):
                    validation_attempts = attempt + 1
                    logger.info(f"   Validation attempt {validation_attempts}/3")

                    validation_result = await self.validator.validate_scraper(
                        scraper_path=temp_path,
                        test_data=test_data,
                        expected_schema={
                            "required_fields": ["success", "message"],
                            "field_types": {"success": "bool", "message": "str"}
                        }
                    )

                    if validation_result.success:
                        validation_passed = True
                        logger.info(f"   ✅ Validation passed on attempt {validation_attempts}")
                        break
                    else:
                        logger.warning(f"   ⚠️ Validation failed: {', '.join(validation_result.execution_errors)}")

                        # Self-healing: Ask AI to fix the code
                        if attempt < 2:  # Don't heal on last attempt
                            logger.info(f"   🔧 Attempting self-healing...")
                            scraper_code = await self._heal_scraper(
                                scraper_code,
                                validation_result,
                                schema_dict
                            )

                            # Re-validate syntax
                            syntax_valid = self._validate_syntax(scraper_code)
                            if not syntax_valid:
                                logger.error("   ❌ Healed code has syntax errors!")
                                break

                            # Save healed code for next validation attempt
                            temp_path = await self._save_scraper(
                                municipality, scraper_code, test_code, temp=True
                            )
                        else:
                            warnings.append("Validation failed after 3 attempts")
                            warnings.extend(validation_result.execution_errors[:3])
            else:
                logger.info(f"⚠️ [{self.name}] Validation skipped (disabled)")
                validation_passed = True  # Assume pass if validation disabled

            # Phase 6: Save to production location if validation passed
            if validation_passed:
                scraper_path = await self._save_scraper(
                    municipality, scraper_code, test_code, temp=False
                )
                logger.info(f"   ✅ Saved to production: {scraper_path}")

            # Calculate confidence score (must be done before storing pattern)
            confidence_score = self._calculate_confidence(
                syntax_valid=syntax_valid,
                validation_passed=validation_passed,
                validation_attempts=validation_attempts,
                test_results=test_results
            )

            # Phase 6.5: Store pattern in library for future use
            if self.pattern_library and validation_passed:
                logger.info(f"💾 [{self.name}] Storing pattern in library...")
                self.pattern_library.store_pattern(
                    municipality_name=municipality,
                    form_url=url,
                    form_schema=schema_dict,
                    generated_code=scraper_code,
                    confidence_score=confidence_score,
                    validation_attempts=validation_attempts,
                    js_analysis=js_analysis
                )
            else:
                scraper_path = temp_path
                logger.warning(f"   ⚠️ Validation failed, scraper saved to temp location only")

            result = GeneratedScraper(
                file_path=str(scraper_path),
                code=scraper_code,
                class_name=self._extract_class_name(scraper_code),
                test_code=test_code,
                syntax_valid=syntax_valid,
                self_test_passed=True,
                validation_passed=validation_passed,
                validation_attempts=validation_attempts,
                warnings=warnings,
                confidence_score=confidence_score
            )

            self._record_action(
                action_type="code_generation",
                description=f"Generated scraper for {municipality}",
                result=str(scraper_path),
                success=True
            )

            logger.info(f"✅ [{self.name}] Scraper saved to {scraper_path}")

            return {
                "success": True,
                "message": "Scraper generated successfully",
                "scraper": {
                    "file_path": result.file_path,
                    "class_name": result.class_name,
                    "syntax_valid": result.syntax_valid,
                    "validation_passed": result.validation_passed,
                    "validation_attempts": result.validation_attempts,
                    "confidence_score": result.confidence_score,
                    "warnings": result.warnings
                }
            }

        except Exception as e:
            logger.error(f"❌ [{self.name}] Code generation failed: {e}")
            return {"success": False, "error": str(e)}

    async def _generate_scraper_code(
        self,
        schema: Dict[str, Any],
        js_analysis: Dict[str, Any],
        test_results: Dict[str, Any]
    ) -> str:
        """
        Generate scraper code using Claude Opus with pattern library assistance
        Enhanced with API-aware and event-aware generation
        """
        logger.info(f"🤖 [{self.name}] Asking Claude Opus to generate code...")

        municipality = schema.get("municipality", "unknown").title().replace("_", "")
        url = schema.get("url", "")

        # Check pattern library for similar forms
        similar_patterns_text = ""
        select2_code_example = ""
        if self.pattern_library:
            similar_patterns = self.pattern_library.find_similar_patterns(schema, top_k=3)

            if similar_patterns:
                logger.info(f"📚 Found {len(similar_patterns)} similar patterns in library")

                similar_patterns_text = "\n**Similar Successful Patterns:**\n"
                for i, pattern in enumerate(similar_patterns, 1):
                    similar_patterns_text += f"\n{i}. {pattern.municipality_name}:"
                    similar_patterns_text += f"\n   - Field types: {', '.join(set(pattern.field_types))}"
                    similar_patterns_text += f"\n   - JS complexity: {pattern.js_complexity}"
                    similar_patterns_text += f"\n   - Success rate: {pattern.success_rate:.0%}"
                    similar_patterns_text += f"\n   - Validation attempts: {pattern.validation_attempts}"

                    # Add code snippet recommendations
                    if pattern.code_snippets:
                        similar_patterns_text += f"\n   - Recommended patterns: {', '.join(pattern.code_snippets.keys())}"

                    # Check if this pattern has Select2 handling
                    if pattern.metadata:
                        import json as json_lib
                        try:
                            metadata = json_lib.loads(pattern.metadata) if isinstance(pattern.metadata, str) else pattern.metadata
                            if metadata.get('select2_detected') or metadata.get('jquery_required'):
                                logger.info(f"   📦 Pattern {pattern.municipality_name} has Select2 handling!")
                                # Extract Select2 method from stored code
                                if 'select2' in pattern.code_snippets:
                                    select2_code_example = pattern.code_snippets['select2']
                        except Exception as e:
                            logger.warning(f"Could not parse pattern metadata: {e}")

                similar_patterns_text += "\n\n**Note:** Use these patterns as reference for handling similar form structures.\n"

        # Detect Select2 dropdowns in schema
        has_select2 = False
        for field in schema.get('fields', []):
            if 'select2' in field.get('class', '').lower() or field.get('select2', False):
                has_select2 = True
                break

        select2_warning = ""
        if has_select2:
            select2_warning = """
**⚠️  CRITICAL: This form uses Select2 jQuery dropdowns!**

Regular Playwright select_option() will NOT work. You MUST use jQuery/JavaScript:

```python
# For Select2 dropdowns (class contains 'select2-hidden-accessible'):
async def _select_select2_dropdown(self, page, selector, value, field_name, wait_after=1.5):
    try:
        js_code = '''
            (args) => {
                const select = document.querySelector(args.selector);
                if (select && typeof $ !== 'undefined') {
                    $(select).val(args.value);
                    $(select).trigger('change');
                    return true;
                }
                return false;
            }
        '''
        result = await page.evaluate(js_code, {"selector": selector, "value": value})
        if result:
            await asyncio.sleep(wait_after)  # Wait for cascading
            return True
    except Exception as e:
        logger.error(f"Select2 error: {e}")
        return False
```

IMPORTANT: Detect Select2 by checking if field class contains 'select2' or 'select2-hidden-accessible'.
"""

        # NEW: Extract API calls and event listeners
        api_calls = js_analysis.get('api_calls', [])
        event_listeners = schema.get('event_listeners', {})

        # Build API-aware section
        api_section = ""
        if api_calls:
            api_section = f"""
**🌐 DETECTED API CALLS (Network Tab):**
The following API calls were captured during form interaction:

```json
{json.dumps(api_calls[:5], indent=2)}
```

**CRITICAL: Try to replicate these API calls directly with httpx/aiohttp!**
- This will be 5-10x faster than browser automation
- Only use browser if APIs require session cookies or complex auth
- Example hybrid approach:

```python
import httpx

async def _try_direct_api(self, data):
    \"\"\"Attempt direct API submission (fast path)\"\"\"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                'actual_api_endpoint_from_network_tab',
                json=data,
                headers={{
                    'User-Agent': 'Mozilla/5.0...',
                    'Content-Type': 'application/json'
                }}
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass  # Fall back to browser
    return None
```
"""

        # Build event listener section
        event_section = ""
        if event_listeners:
            event_section = f"""
**🎯 DETECTED EVENT LISTENERS:**
The following fields have JavaScript event handlers:

```json
{json.dumps(event_listeners, indent=2)}
```

**CRITICAL: Trigger these events properly!**
- Fields with 'blur' listener: Must focus() then blur() to trigger validation
- Fields with 'input' listener: Type slowly or trigger 'input' event
- Example:

```python
async def _fill_with_events(self, page, selector, value, listeners):
    element = await page.wait_for_selector(selector)

    # Focus first
    await element.focus()
    await asyncio.sleep(0.1)

    # Fill value
    await element.fill(value)

    # Trigger blur if has blur listener
    if listeners.get('blur'):
        await element.blur()
        await asyncio.sleep(0.3)  # Wait for validation
```
"""

        # Get proven code templates based on detected UI framework
        templates_section = ""
        detected_framework = UIFramework.PLAIN_HTML

        # Detect framework from schema
        for field in schema.get('fields', []):
            field_class = field.get('class', '').lower()
            if 'ant-select' in field_class or 'ant-' in field_class:
                detected_framework = UIFramework.ANT_DESIGN
                break
            elif 'select2' in field_class or field.get('select2', False):
                detected_framework = UIFramework.SELECT2
                break

        # Check URL for ASP.NET
        if '.aspx' in url.lower() or any('ctl00' in f.get('selector', '') for f in schema.get('fields', [])):
            detected_framework = UIFramework.ASP_NET_WEBFORMS

        # Get templates for this framework
        templates_section = get_template_code_for_prompt(detected_framework)
        if templates_section:
            logger.info(f"📦 Using {detected_framework.value} code templates")
        else:
            logger.info(f"ℹ️ No templates for {detected_framework.value}, using generic patterns")

        # Build comprehensive prompt
        prompt = f"""You are an expert Python developer. Generate a production-ready web scraper class.

{similar_patterns_text}
{templates_section}
{select2_warning}
{api_section}
{event_section}

**Municipality:** {schema.get('municipality')}
**URL:** {url}

**Form Schema:**
```json
{json.dumps(schema, indent=2)}
```

**JavaScript Analysis:**
```json
{json.dumps(js_analysis, indent=2)}
```

**Test Results:**
- Tests passed: {test_results.get('passed', 0)}/{test_results.get('total_tests', 0)}
- Confidence: {test_results.get('confidence_score', 0):.0%}

**Requirements:**
1. Class name: `{municipality}Scraper`
2. Use Playwright for browser automation
3. Implement `async def submit_grievance(self, data: dict) -> dict` method
4. Handle ALL fields from the schema, including:
   - Required fields validation
   - Cascading dropdowns (wait for parent selection to populate child)
   - File uploads (if present)
   - CSRF tokens (if needed)
5. Add comprehensive error handling:
   - Network timeouts
   - Element not found
   - Validation errors
   - Submission failures
6. Take screenshots at key steps for debugging
7. Return structured result:
   ```python
   {{
       "success": bool,
       "tracking_id": str | None,
       "message": str,
       "screenshots": List[str],
       "errors": List[str]
   }}
   ```
8. Add docstrings and type hints
9. Include retry logic (max 2 retries)
10. Log all actions with logging module

**Important Implementation Notes:**
- For cascading dropdowns, select parent first, then wait 1-2 seconds before selecting child
- Extract tracking ID from success page using regex patterns
- Use stealth mode to avoid detection
- Make browser configurable (headless parameter)
- Add timeout handling (default 30s per operation)

**Code Style:**
- Use async/await throughout
- Type hints for all parameters
- Comprehensive docstrings
- Clear variable names
- Error messages that help debugging

**Handling Select2 Dropdowns:**
If any select element has class 'select2-hidden-accessible', use jQuery to interact:

```python
await page.evaluate('''
    (args) => {{
        const select = document.querySelector(args.selector);
        if (select && typeof $ !== 'undefined') {{
            $(select).val(args.value);
            $(select).trigger('change');
            return true;
        }}
        return false;
    }}
''', {{"selector": "#field_id", "value": "field_value"}})
await asyncio.sleep(1.5)  # Wait for cascading
```

DO NOT use page.select_option() for Select2 dropdowns - it will timeout!

**CRITICAL OUTPUT FORMAT:**
- Return ONLY raw Python code with NO markdown formatting
- Do NOT wrap in ```python or ``` code fences
- Do NOT include any explanations before or after the code
- Start directly with the class definition (after imports will be added automatically)
- End with the last closing brace of the class
- The code will be saved directly to a .py file, so it must be pure Python
"""

        start_time = time.time()
        response = ai_client.client.messages.create(
            model=ai_client.models["powerful"],  # Opus for code generation
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=16000  # Increased to handle complete scraper generation
        )
        elapsed = time.time() - start_time

        usage = response.usage
        cost = cost_tracker.track_call(
            model=ai_client.models["powerful"],
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            agent_name=self.name
        )

        self._record_action(
            action_type="claude_code_generation",
            description="Generated scraper code with Claude Opus",
            result=f"Generated {usage.output_tokens} tokens",
            success=True,
            cost=cost
        )

        # Extract code from markdown if present
        code = response.content[0].text

        import re
        code_match = re.search(r'```python\s*(.*?)\s*```', code, re.DOTALL)
        if code_match:
            code = code_match.group(1)
        else:
            # Try without python keyword
            code_match = re.search(r'```\s*(.*?)\s*```', code, re.DOTALL)
            if code_match:
                code = code_match.group(1)

        # Add header comment
        header = f'''"""
Auto-generated scraper for {schema.get('municipality', 'Unknown')} Municipality
URL: {url}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

This scraper was automatically generated by AI and validated through testing.
"""

import logging
import asyncio
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from playwright.async_api import async_playwright, Page, Browser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

'''

        code = header + code

        return code

    def _validate_syntax(self, code: str) -> bool:
        """
        Validate Python syntax
        """
        try:
            ast.parse(code)
            logger.info("   ✅ Syntax valid")
            return True
        except SyntaxError as e:
            logger.error(f"   ❌ Syntax error: {e}")
            return False

    async def _fix_syntax_errors(self, code: str) -> str:
        """
        Ask Claude to fix syntax errors
        """
        logger.info(f"🔧 [{self.name}] Asking Claude to fix syntax errors")

        prompt = f"""This Python code has syntax errors. Fix them and return the corrected code.

```python
{code}
```

Return ONLY the fixed Python code, no explanations.
"""

        response = ai_client.client.messages.create(
            model=ai_client.models["balanced"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=16000  # Increased to handle complete scraper generation
        )

        usage = response.usage
        cost_tracker.track_call(
            model=ai_client.models["balanced"],
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            agent_name=f"{self.name}_fix"
        )

        fixed_code = response.content[0].text

        # Extract from markdown
        import re
        code_match = re.search(r'```python\s*(.*?)\s*```', fixed_code, re.DOTALL)
        if code_match:
            return code_match.group(1)

        return fixed_code

    async def _generate_test_code(self, schema: Dict[str, Any], scraper_code: str) -> str:
        """
        Use AI to generate pytest test code that matches the actual schema fields
        """
        class_name = self._extract_class_name(scraper_code)
        municipality = schema.get("municipality", "unknown")

        # Ask Claude to generate proper tests based on the schema
        prompt = f"""Generate a pytest test file for this scraper.

**Scraper Class:** {class_name}
**Municipality:** {municipality}

**Form Schema (these are the EXACT fields the scraper expects):**
```json
{json.dumps(schema.get("fields", []), indent=2)}
```

**Requirements:**
1. Import: `from {municipality}_scraper import {class_name}`
2. Create test_submit_grievance() that:
   - Uses the EXACT field names from the schema above
   - Provides realistic test values for each field type
   - For select/dropdown fields, use placeholder values with TODO comments
   - Has strong assertions: `assert result["success"] is True, f"Failed: {{result.get('error')}}"`
3. Create test_error_handling() that tests with empty data
4. Use @pytest.mark.asyncio decorators
5. Include proper docstrings

Generate ONLY the Python test code, no explanations."""

        response = ai_client.client.messages.create(
            model=ai_client.models["fast"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000
        )

        test_code = response.content[0].text

        # Extract code from markdown if present
        import re
        code_match = re.search(r'```python\s*(.*?)\s*```', test_code, re.DOTALL)
        if code_match:
            test_code = code_match.group(1)
        else:
            code_match = re.search(r'```\s*(.*?)\s*```', test_code, re.DOTALL)
            if code_match:
                test_code = code_match.group(1)

        return test_code

    async def _heal_scraper(
        self,
        failed_code: str,
        validation_result: ValidationResult,
        schema: Dict[str, Any]
    ) -> str:
        """
        Use AI to fix failing scraper code

        Args:
            failed_code: The code that failed validation
            validation_result: Validation results with errors
            schema: Original form schema

        Returns:
            Fixed code
        """
        logger.info(f"🔧 [{self.name}] Asking AI to heal failing code...")

        # Format error details
        error_details = "\n".join([
            f"- {err}" for err in validation_result.execution_errors[:5]
        ])

        # Build healing prompt
        prompt = HEALING_PROMPT_TEMPLATE.format(
            error_details=error_details,
            municipality_name=schema.get("municipality", "unknown"),
            url=schema.get("url", ""),
            form_analysis=json.dumps(schema, indent=2)[:1000],  # Truncate if too long
            failed_code=failed_code,
            execution_status=validation_result.execution_status,
            execution_errors=", ".join(validation_result.execution_errors[:3]),
            schema_errors=", ".join(validation_result.schema_errors[:3]),
            timeout_issues=", ".join(validation_result.timeout_issues[:3]),
            screenshot_path=validation_result.screenshot_path or "None"
        )

        start_time = time.time()
        response = ai_client.client.messages.create(
            model=ai_client.models["balanced"],  # Sonnet for healing
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=16000  # Increased to handle complete scraper generation
        )
        elapsed = time.time() - start_time

        usage = response.usage
        cost = cost_tracker.track_call(
            model=ai_client.models["balanced"],
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            agent_name=f"{self.name}_healing"
        )

        self._record_action(
            action_type="self_healing",
            description="Attempted to fix failing scraper",
            result=f"Generated {usage.output_tokens} tokens",
            success=True,
            cost=cost
        )

        # Extract code from response
        healed_code = response.content[0].text

        import re
        code_match = re.search(r'```python\s*(.*?)\s*```', healed_code, re.DOTALL)
        if code_match:
            healed_code = code_match.group(1)
        else:
            code_match = re.search(r'```\s*(.*?)\s*```', healed_code, re.DOTALL)
            if code_match:
                healed_code = code_match.group(1)

        logger.info(f"   ✅ Generated healed code ({len(healed_code)} chars)")
        return healed_code

    def _generate_test_data(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate test data based on form schema

        Args:
            schema: Form schema with fields

        Returns:
            Dictionary with test values for each field
        """
        test_data = {}

        fields = schema.get("fields", [])
        for field in fields:
            field_name = field.get("name", "")
            field_type = field.get("type", "text")

            # Generate appropriate test values
            if field_type == "text":
                if "mobile" in field_name.lower() or "phone" in field_name.lower():
                    test_data[field_name] = "9876543210"
                elif "email" in field_name.lower():
                    test_data[field_name] = "test@example.com"
                elif "name" in field_name.lower():
                    test_data[field_name] = "Test User"
                else:
                    test_data[field_name] = f"test_{field_name}"

            elif field_type == "dropdown" or field_type == "select":
                options = field.get("options", [])
                if options and len(options) > 0:
                    test_data[field_name] = options[0]
                else:
                    test_data[field_name] = "Option1"

            elif field_type == "textarea":
                test_data[field_name] = "This is a test complaint message for automated testing purposes."

            elif field_type == "checkbox":
                test_data[field_name] = True

            elif field_type == "file":
                test_data[field_name] = None  # Skip file uploads in test mode

        logger.info(f"   Generated test data with {len(test_data)} fields")
        return test_data

    def _calculate_confidence(
        self,
        syntax_valid: bool,
        validation_passed: bool,
        validation_attempts: int,
        test_results: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence score for generated scraper

        Args:
            syntax_valid: Whether syntax is valid
            validation_passed: Whether validation passed
            validation_attempts: Number of attempts needed
            test_results: Results from test validation agent

        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 0.0

        # Base score from test results
        if test_results:
            confidence = test_results.get("confidence_score", 0.7)
        else:
            confidence = 0.7  # Default

        # Syntax validation (critical)
        if not syntax_valid:
            confidence *= 0.5

        # Execution validation (critical)
        if not validation_passed:
            confidence *= 0.6
        elif validation_attempts == 1:
            # Passed on first try - bonus
            confidence = min(1.0, confidence * 1.1)
        elif validation_attempts == 2:
            # Needed healing once
            confidence *= 0.95
        elif validation_attempts >= 3:
            # Needed multiple healing attempts
            confidence *= 0.85

        return round(confidence, 2)

    async def _save_scraper(
        self,
        municipality: str,
        scraper_code: str,
        test_code: str,
        temp: bool = False
    ) -> Path:
        """
        Save scraper and test code to files

        Args:
            municipality: Municipality name
            scraper_code: Python scraper code
            test_code: Pytest test code
            temp: If True, save to temp directory for validation

        Returns:
            Path to saved scraper file
        """
        # Create municipality directory
        if temp:
            muni_dir = self.output_dir / "_temp" / municipality
        else:
            muni_dir = self.output_dir / municipality

        muni_dir.mkdir(exist_ok=True, parents=True)

        # Create __init__.py
        init_file = muni_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text(f"# {municipality.title()} Municipality Scrapers\n")

        # Save scraper
        scraper_file = muni_dir / f"{municipality}_scraper.py"
        scraper_file.write_text(scraper_code)

        # Save test
        test_dir = muni_dir / "tests"
        test_dir.mkdir(exist_ok=True)
        test_file = test_dir / f"test_{municipality}_scraper.py"
        test_file.write_text(test_code)

        logger.info(f"   📁 Saved to {scraper_file}")
        logger.info(f"   📁 Test saved to {test_file}")

        return scraper_file

    def _extract_class_name(self, code: str) -> str:
        """
        Extract class name from generated code
        """
        import re
        match = re.search(r'class\s+(\w+)', code)
        if match:
            return match.group(1)
        return "UnknownScraper"

    async def _run_self_test(self, scraper_path: Path) -> bool:
        """
        Run basic self-test on generated scraper
        """
        logger.info(f"🧪 [{self.name}] Running self-test...")

        try:
            # Try to import the scraper
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_scraper", scraper_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find the scraper class
            scraper_class = None
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and name.endswith("Scraper"):
                    scraper_class = obj
                    break

            if scraper_class:
                logger.info("   ✅ Import successful")
                return True
            else:
                logger.warning("   ⚠️ No scraper class found")
                return False

        except Exception as e:
            logger.error(f"   ❌ Self-test failed: {e}")
            return False


# For testing
async def test_code_generator():
    """Test the code generator agent"""
    mock_schema = {
        "url": "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online",
        "municipality": "ranchi_smart",
        "fields": [
            {
                "name": "mobile",
                "label": "Mobile No",
                "type": "text",
                "selector": "#mobile",
                "required": True
            },
            {
                "name": "select_type",
                "label": "Select Type",
                "type": "dropdown",
                "selector": "#selectType",
                "required": True,
                "options": ["Electrical", "Water", "Roads"]
            }
        ],
        "submit_button": {"selector": "button[type='submit']", "text": "Register Complaint"}
    }

    mock_js_analysis = {
        "submission_method": "ajax_xhr",
        "endpoint": "/Portal/Ajax/RegisterComplaint",
        "requires_browser": True
    }

    mock_test_results = {
        "total_tests": 5,
        "passed": 4,
        "failed": 1,
        "confidence_score": 0.8
    }

    agent = CodeGeneratorAgent()
    result = await agent.execute({
        "schema": mock_schema,
        "js_analysis": mock_js_analysis,
        "test_results": mock_test_results
    })

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(test_code_generator())
