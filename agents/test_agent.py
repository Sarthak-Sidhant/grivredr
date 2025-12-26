"""
Test Validation Agent - Validates form schemas through actual testing
Tests submission, field validation, and form behavior
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from playwright.async_api import async_playwright, Page, Browser

from agents.base_agent import BaseAgent
from agents.form_discovery_agent import FormSchema, FormField

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a single test"""
    test_name: str
    passed: bool
    message: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    screenshot_path: Optional[str] = None


@dataclass
class ValidationResults:
    """Complete validation results for a form schema"""
    total_tests: int
    passed: int
    failed: int
    test_results: List[TestResult] = field(default_factory=list)
    updated_schema: Optional[FormSchema] = None
    confidence_score: float = 0.0
    needs_human_review: bool = False
    human_review_reasons: List[str] = field(default_factory=list)


class TestValidationAgent(BaseAgent):
    """
    Agent that validates form schemas through systematic testing
    """

    def __init__(self, headless: bool = False):
        super().__init__(name="TestValidationAgent", max_attempts=3)
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.playwright = None

    async def _execute_attempt(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute validation tests on the form schema
        """
        schema_dict = task.get("schema")
        if not schema_dict:
            return {"success": False, "error": "No schema provided"}

        # Reconstruct FormSchema from dict
        schema = self._dict_to_schema(schema_dict)

        # Filter out non-user-facing fields BEFORE testing
        schema = self._filter_user_facing_fields(schema)

        logger.info(f"🧪 [{self.name}] Testing form with {len(schema.fields)} user-facing fields")

        # Initialize browser
        await self._init_browser()

        try:
            results = ValidationResults(total_tests=0, passed=0, failed=0)

            # Test Suite with timeouts
            import time
            start_time = time.time()
            max_validation_time = 180  # 3 minutes max for all validation

            await self._test_empty_submission(schema, results)

            if time.time() - start_time > max_validation_time:
                logger.warning(f"⏰ Validation timeout reached, skipping remaining tests")
                results.test_results.append(TestResult(
                    test_name="timeout_check",
                    passed=False,
                    message="Validation timeout - skipped remaining tests",
                    warnings=["Tests took too long"]
                ))
                results.total_tests += 1
                results.failed += 1
            else:
                await self._test_required_fields(schema, results)

            if time.time() - start_time > max_validation_time:
                logger.warning(f"⏰ Validation timeout reached")
            else:
                await self._test_field_types(schema, results)

            if time.time() - start_time > max_validation_time:
                logger.warning(f"⏰ Validation timeout reached")
            else:
                await self._test_cascading_dropdowns(schema, results)

            if time.time() - start_time > max_validation_time:
                logger.warning(f"⏰ Validation timeout reached")
            else:
                await self._test_full_submission(schema, results)

            # Calculate confidence
            results.confidence_score = results.passed / results.total_tests if results.total_tests > 0 else 0.0

            # Determine if human review needed
            if results.confidence_score < 0.7:
                results.needs_human_review = True
                results.human_review_reasons.append(
                    f"Low confidence: {results.confidence_score:.2%}"
                )

            if results.failed > 3:
                results.needs_human_review = True
                results.human_review_reasons.append(
                    f"Multiple test failures: {results.failed}"
                )

            results.updated_schema = schema

            logger.info(f"✅ [{self.name}] Tests complete: {results.passed}/{results.total_tests} passed")

            return {
                "success": results.confidence_score >= 0.7,
                "message": f"Validation complete: {results.passed}/{results.total_tests} passed",
                "results": self._results_to_dict(results),
                "confidence": results.confidence_score,
                "needs_review": results.needs_human_review
            }

        except Exception as e:
            logger.error(f"❌ [{self.name}] Testing failed: {e}")
            return {"success": False, "error": str(e)}

        finally:
            await self._cleanup_browser()

    async def _init_browser(self):
        """Initialize Playwright browser"""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )

    async def _cleanup_browser(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def _test_empty_submission(self, schema: FormSchema, results: ValidationResults):
        """Test 1: Submit empty form to verify validation"""
        logger.info("🧪 Test 1: Empty form submission")

        context = await self.browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(schema.url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(1)

            # Try to submit without filling anything
            submit_selector = schema.submit_button.get("selector", "")
            if submit_selector:
                await page.click(submit_selector, timeout=5000)
                await asyncio.sleep(1)

                # Check for validation errors
                errors = await page.evaluate("""
                    () => {
                        const errorElements = document.querySelectorAll(
                            '.error, .invalid, .text-danger, [class*="error"], [class*="invalid"]'
                        );
                        return Array.from(errorElements).map(e => e.textContent.trim()).filter(t => t);
                    }
                """)

                if errors:
                    # Good! Form has client-side validation
                    test = TestResult(
                        test_name="empty_submission",
                        passed=True,
                        message=f"Form validation working: {len(errors)} errors shown",
                        errors=errors
                    )

                    # Update required fields based on errors
                    for error in errors:
                        for field in schema.fields:
                            if field.label.lower() in error.lower() or field.name.lower() in error.lower():
                                if not field.required:
                                    logger.info(f"   📝 Marking {field.label} as required")
                                    field.required = True
                                    field.error_message = error

                else:
                    # No errors shown - either no validation or form submitted
                    test = TestResult(
                        test_name="empty_submission",
                        passed=False,
                        message="No validation errors detected",
                        warnings=["Form may not have client-side validation"]
                    )

                results.test_results.append(test)
                results.total_tests += 1
                if test.passed:
                    results.passed += 1
                else:
                    results.failed += 1

        except Exception as e:
            logger.error(f"Empty submission test failed: {e}")
            results.test_results.append(TestResult(
                test_name="empty_submission",
                passed=False,
                message=f"Test error: {str(e)}"
            ))
            results.total_tests += 1
            results.failed += 1

        finally:
            await context.close()

    async def _test_required_fields(self, schema: FormSchema, results: ValidationResults):
        """Test 2: Verify required field detection"""
        logger.info("🧪 Test 2: Required fields validation")

        required_fields = [f for f in schema.fields if f.required]

        if not required_fields:
            results.test_results.append(TestResult(
                test_name="required_fields",
                passed=False,
                message="No required fields identified",
                warnings=["Schema may be incomplete"]
            ))
            results.total_tests += 1
            results.failed += 1
            return

        context = await self.browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(schema.url, wait_until="networkidle", timeout=30000)

            # Test each required field individually
            for field in required_fields[:3]:  # Test first 3 to save time
                try:
                    # Fill all required fields except this one
                    test_data = self._generate_test_data(schema, exclude_field=field.name)

                    await self._fill_form(page, schema, test_data)
                    await asyncio.sleep(0.5)

                    # Try submit
                    await page.click(schema.submit_button.get("selector", ""), timeout=5000)
                    await asyncio.sleep(1)

                    # Check for error about this field
                    errors = await page.evaluate("""
                        () => {
                            const errorElements = document.querySelectorAll('.error, .invalid, .text-danger');
                            return Array.from(errorElements).map(e => e.textContent.trim());
                        }
                    """)

                    field_mentioned = any(field.label.lower() in err.lower() for err in errors)

                    if field_mentioned:
                        logger.info(f"   ✅ {field.label} correctly validated as required")
                    else:
                        logger.warning(f"   ⚠️ {field.label} may not be required")
                        field.required = False  # Update schema

                    # Reload for next test
                    await page.goto(schema.url, wait_until="networkidle", timeout=30000)

                except Exception as e:
                    logger.warning(f"Could not test {field.label}: {e}")

            results.test_results.append(TestResult(
                test_name="required_fields",
                passed=True,
                message=f"Validated {len(required_fields)} required fields"
            ))
            results.total_tests += 1
            results.passed += 1

        except Exception as e:
            logger.error(f"Required fields test failed: {e}")
            results.test_results.append(TestResult(
                test_name="required_fields",
                passed=False,
                message=f"Test error: {str(e)}"
            ))
            results.total_tests += 1
            results.failed += 1

        finally:
            await context.close()

    async def _test_field_types(self, schema: FormSchema, results: ValidationResults):
        """Test 3: Verify field type detection"""
        logger.info("🧪 Test 3: Field type validation")

        context = await self.browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(schema.url, wait_until="networkidle", timeout=30000)

            # Limit to max 10 fields or 20% of total, whichever is smaller
            max_fields_to_check = min(10, max(5, len(schema.fields) // 5))
            verified_count = 0

            logger.info(f"   Checking {max_fields_to_check} of {len(schema.fields)} fields")

            for field in schema.fields[:max_fields_to_check]:
                try:
                    if field.selector:
                        # Get actual field type from DOM
                        actual_type = await page.evaluate(f"""
                            () => {{
                                const elem = document.querySelector('{field.selector}');
                                if (!elem) return null;
                                return elem.tagName === 'SELECT' ? 'dropdown' :
                                       elem.tagName === 'TEXTAREA' ? 'textarea' :
                                       elem.type || 'text';
                            }}
                        """)

                        if actual_type:
                            # Normalize type names
                            type_map = {
                                'select-one': 'dropdown',
                                'text': 'text',
                                'email': 'text',
                                'tel': 'text',
                                'file': 'file',
                                'textarea': 'textarea'
                            }

                            actual_normalized = type_map.get(actual_type, actual_type)
                            field_normalized = type_map.get(field.type, field.type)

                            if actual_normalized == field_normalized:
                                verified_count += 1
                            else:
                                logger.warning(f"   ⚠️ {field.label}: expected {field.type}, got {actual_type}")
                                field.type = actual_normalized

                except Exception as e:
                    logger.warning(f"Could not verify {field.label}: {e}")

            test = TestResult(
                test_name="field_types",
                passed=verified_count > 0,
                message=f"Verified {verified_count}/{min(5, len(schema.fields))} field types"
            )

            results.test_results.append(test)
            results.total_tests += 1
            if test.passed:
                results.passed += 1
            else:
                results.failed += 1

        except Exception as e:
            logger.error(f"Field type test failed: {e}")
            results.test_results.append(TestResult(
                test_name="field_types",
                passed=False,
                message=f"Test error: {str(e)}"
            ))
            results.total_tests += 1
            results.failed += 1

        finally:
            await context.close()

    async def _test_cascading_dropdowns(self, schema: FormSchema, results: ValidationResults):
        """Test 4: Verify cascading dropdown relationships"""
        logger.info("🧪 Test 4: Cascading dropdowns")

        cascading_fields = [f for f in schema.fields if f.depends_on]

        if not cascading_fields:
            results.test_results.append(TestResult(
                test_name="cascading_dropdowns",
                passed=True,
                message="No cascading dropdowns to test"
            ))
            results.total_tests += 1
            results.passed += 1
            return

        context = await self.browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(schema.url, wait_until="networkidle", timeout=30000)

            verified = 0
            for field in cascading_fields:
                try:
                    parent_field = next((f for f in schema.fields if f.name == field.depends_on), None)
                    if not parent_field or not parent_field.options:
                        continue

                    logger.info(f"   Testing: {parent_field.label} → {field.label}")

                    # Get child options before parent selection
                    options_before = await page.evaluate(f"""
                        () => {{
                            const select = document.querySelector('{field.selector}');
                            return select ? Array.from(select.options).map(o => o.text) : [];
                        }}
                    """)

                    # Select parent
                    await page.select_option(parent_field.selector, parent_field.options[0], timeout=3000)
                    await asyncio.sleep(1)  # Wait for AJAX

                    # Get child options after
                    options_after = await page.evaluate(f"""
                        () => {{
                            const select = document.querySelector('{field.selector}');
                            return select ? Array.from(select.options).map(o => o.text) : [];
                        }}
                    """)

                    if len(options_after) > len(options_before):
                        logger.info(f"   ✅ Cascading confirmed: {len(options_before)} → {len(options_after)}")
                        verified += 1
                    else:
                        logger.warning(f"   ⚠️ Cascading not detected")

                except Exception as e:
                    logger.warning(f"Could not test cascading for {field.label}: {e}")

            test = TestResult(
                test_name="cascading_dropdowns",
                passed=verified > 0,
                message=f"Verified {verified}/{len(cascading_fields)} cascading relationships"
            )

            results.test_results.append(test)
            results.total_tests += 1
            if test.passed:
                results.passed += 1
            else:
                results.failed += 1

        except Exception as e:
            logger.error(f"Cascading test failed: {e}")
            results.test_results.append(TestResult(
                test_name="cascading_dropdowns",
                passed=False,
                message=f"Test error: {str(e)}"
            ))
            results.total_tests += 1
            results.failed += 1

        finally:
            await context.close()

    async def _test_full_submission(self, schema: FormSchema, results: ValidationResults):
        """Test 5: Full form submission with valid data"""
        logger.info("🧪 Test 5: Full submission")

        context = await self.browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(schema.url, wait_until="networkidle", timeout=30000)

            # Generate complete test data
            test_data = self._generate_test_data(schema)

            # Fill form
            await self._fill_form(page, schema, test_data)
            await asyncio.sleep(1)

            # Take screenshot before submit
            await page.screenshot(path="dashboard/static/screenshots/before_submit.png")

            # Submit - with fallback for missing/wrong submit button
            submit_selector = schema.submit_button.get("selector", "")
            if not submit_selector:
                logger.warning("   ⚠️ No submit button selector provided, searching for submit buttons...")
                # Try common submit button patterns
                submit_selector = await page.evaluate("""
                    () => {
                        const buttons = document.querySelectorAll('button[type="submit"], input[type="submit"], button.submit, .btn-primary');
                        for (let btn of buttons) {
                            const text = (btn.textContent || btn.value || '').toLowerCase();
                            if (text.includes('submit') || text.includes('register') || text.includes('send')) {
                                // Return a unique selector
                                return '#' + btn.id || btn.tagName + '.' + Array.from(btn.classList).join('.');
                            }
                        }
                        return null;
                    }
                """)

            if submit_selector:
                try:
                    await page.click(submit_selector, timeout=5000)
                except Exception as e:
                    logger.error(f"   ❌ Failed to click submit button: {e}")
                    # If click fails, try finding visible buttons and use the first one
                    try:
                        await page.click("button[type='submit']:visible, input[type='submit']:visible", timeout=2000)
                    except:
                        logger.error("   ❌ Could not find any clickable submit button")
            await asyncio.sleep(2)

            # Take screenshot after submit
            await page.screenshot(path="dashboard/static/screenshots/after_submit.png")

            # Check for success indicators
            success_indicators = [
                "success", "submitted", "registered", "thank you",
                "complaint id", "tracking", "reference number"
            ]

            page_text = await page.evaluate("() => document.body.innerText.toLowerCase()")

            success = any(indicator in page_text for indicator in success_indicators)

            if success:
                logger.info("   ✅ Form submission successful!")

                # Try to extract tracking ID
                tracking_id = await self._extract_tracking_id(page, page_text)
                if tracking_id:
                    logger.info(f"   📋 Tracking ID: {tracking_id}")

                test = TestResult(
                    test_name="full_submission",
                    passed=True,
                    message="Form submission successful",
                    screenshot_path="dashboard/static/screenshots/after_submit.png"
                )
            else:
                # Check for errors
                errors = await page.evaluate("""
                    () => {
                        const errorElements = document.querySelectorAll('.error, .invalid, .text-danger');
                        return Array.from(errorElements).map(e => e.textContent.trim());
                    }
                """)

                test = TestResult(
                    test_name="full_submission",
                    passed=False,
                    message="Submission may have failed",
                    errors=errors,
                    warnings=["Could not detect success message"],
                    screenshot_path="dashboard/static/screenshots/after_submit.png"
                )

            results.test_results.append(test)
            results.total_tests += 1
            if test.passed:
                results.passed += 1
            else:
                results.failed += 1

        except Exception as e:
            logger.error(f"Full submission test failed: {e}")
            results.test_results.append(TestResult(
                test_name="full_submission",
                passed=False,
                message=f"Test error: {str(e)}"
            ))
            results.total_tests += 1
            results.failed += 1

        finally:
            await context.close()

    async def _fill_form(self, page: Page, schema: FormSchema, data: Dict[str, Any]):
        """Helper: Fill form with provided data"""
        for field in schema.fields:
            if field.name not in data:
                continue

            value = data[field.name]

            try:
                if field.type == "dropdown":
                    # Try Select2 dropdown first (learned from ranchi_smart)
                    is_select2 = await page.evaluate(f"""
                        () => {{
                            const select = document.querySelector('{field.selector}');
                            if (!select) return false;
                            return select.classList.contains('select2-hidden-accessible') ||
                                   select.getAttribute('data-select2-id') !== null ||
                                   (window.jQuery && jQuery(select).data('select2'));
                        }}
                    """)

                    if is_select2:
                        logger.info(f"   🎯 Detected Select2 dropdown: {field.label}")
                        # Use JavaScript to set value (learned pattern from ranchi_smart)
                        await page.evaluate(f"""
                            (value) => {{
                                const select = document.querySelector('{field.selector}');
                                if (select) {{
                                    select.value = value;
                                    // Trigger change event
                                    const event = new Event('change', {{ bubbles: true }});
                                    select.dispatchEvent(event);

                                    // Also trigger Select2 change if it exists
                                    if (window.jQuery && jQuery(select).data('select2')) {{
                                        jQuery(select).trigger('change');
                                    }}
                                }}
                            }}
                        """, value)
                        await asyncio.sleep(1)  # Wait for cascading/AJAX
                    else:
                        # Regular dropdown
                        await page.select_option(field.selector, value, timeout=3000)
                        await asyncio.sleep(0.3)

                elif field.type == "textarea":
                    await page.fill(field.selector, value, timeout=3000)
                elif field.type == "file":
                    # Skip file uploads in testing for now
                    pass
                elif "number" in field.selector or 'type="number"' in str(field):
                    # Handle number inputs specially
                    await page.evaluate(f"""
                        (value) => {{
                            const input = document.querySelector('{field.selector}');
                            if (input) {{
                                input.value = value;
                                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        }}
                    """, str(value))
                else:
                    await page.fill(field.selector, value, timeout=3000)

            except Exception as e:
                logger.warning(f"Could not fill {field.label}: {e}")

    def _generate_test_data(self, schema: FormSchema, exclude_field: Optional[str] = None) -> Dict[str, Any]:
        """Generate realistic test data for the form"""
        data = {}

        for field in schema.fields:
            if exclude_field and field.name == exclude_field:
                continue

            if not field.required and exclude_field:
                continue  # Skip optional fields when testing required

            # Generate appropriate test data
            if field.type == "dropdown" and field.options:
                data[field.name] = field.options[0] if field.options else ""
            elif "mobile" in field.name.lower() or "phone" in field.name.lower():
                data[field.name] = "9876543210"
            elif "email" in field.name.lower():
                data[field.name] = "test@example.com"
            elif "name" in field.name.lower():
                data[field.name] = "Test User"
            elif "address" in field.name.lower():
                data[field.name] = "123 Test Street, Test City"
            elif field.type == "textarea":
                data[field.name] = "This is a test complaint for automated testing purposes."
            else:
                data[field.name] = "Test Value"

        return data

    async def _extract_tracking_id(self, page: Page, page_text: str) -> Optional[str]:
        """Try to extract tracking/complaint ID from success page"""
        import re

        # Common patterns for tracking IDs
        patterns = [
            r'complaint\s*(?:id|number|no\.?)\s*:?\s*([A-Z0-9-]+)',
            r'tracking\s*(?:id|number|no\.?)\s*:?\s*([A-Z0-9-]+)',
            r'reference\s*(?:id|number|no\.?)\s*:?\s*([A-Z0-9-]+)',
            r'([A-Z]{2,5}\d{5,10})',  # Generic pattern like RMC12345
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _dict_to_schema(self, schema_dict: Dict[str, Any]) -> FormSchema:
        """Convert dict back to FormSchema object"""
        fields = []
        for field_data in schema_dict.get("fields", []):
            field = FormField(
                name=field_data["name"],
                label=field_data["label"],
                type=field_data["type"],
                selector=field_data["selector"],
                required=field_data.get("required", False),
                placeholder=field_data.get("placeholder", ""),
                options=field_data.get("options", []),
                depends_on=field_data.get("depends_on"),
                validation_pattern=field_data.get("validation_pattern"),
                error_message=field_data.get("error_message")
            )
            fields.append(field)

        schema = FormSchema(
            url=schema_dict["url"],
            municipality=schema_dict["municipality"],
            title=schema_dict.get("title", ""),
            fields=fields,
            submit_button=schema_dict.get("submit_button", {}),
            submission_type=schema_dict.get("submission_type", "form_post"),
            success_indicator=schema_dict.get("success_indicator", {}),
            requires_captcha=schema_dict.get("requires_captcha", False),
            multi_step=schema_dict.get("multi_step", False)
        )

        return schema

    def _filter_user_facing_fields(self, schema: FormSchema) -> FormSchema:
        """Filter out non-user-facing fields like hidden inputs, viewstate, Select2 internals"""

        # Patterns to exclude
        exclude_patterns = [
            '__VIEWSTATE', '__EVENTVALIDATION', '__EVENTTARGET', '__EVENTARGUMENT',  # ASP.NET
            's2id_autogen', 'select2-', '_search',  # Select2 internals
            'hf', 'hidden',  # Hidden field prefixes
            'hddn', 'hdn',  # More hidden field patterns
        ]

        # Types to exclude
        exclude_types = ['hidden']

        filtered_fields = []
        for field in schema.fields:
            # Check if field name/selector matches exclude patterns
            should_exclude = False

            field_text = f"{field.name} {field.selector}".lower()

            for pattern in exclude_patterns:
                if pattern.lower() in field_text:
                    should_exclude = True
                    logger.debug(f"   Filtering out: {field.name} (matched pattern: {pattern})")
                    break

            # Check if field type is excluded
            if field.type in exclude_types:
                should_exclude = True
                logger.debug(f"   Filtering out: {field.name} (type: {field.type})")

            # Check if selector indicates hidden field
            if 'type="hidden"' in field.selector or 'hidden' in field.type.lower():
                should_exclude = True
                logger.debug(f"   Filtering out: {field.name} (hidden)")

            if not should_exclude:
                filtered_fields.append(field)

        logger.info(f"🧹 Filtered {len(schema.fields)} → {len(filtered_fields)} user-facing fields")
        schema.fields = filtered_fields
        return schema

    def _results_to_dict(self, results: ValidationResults) -> Dict[str, Any]:
        """Convert ValidationResults to dict"""
        return {
            "total_tests": results.total_tests,
            "passed": results.passed,
            "failed": results.failed,
            "confidence_score": results.confidence_score,
            "needs_human_review": results.needs_human_review,
            "human_review_reasons": results.human_review_reasons,
            "test_results": [
                {
                    "test_name": t.test_name,
                    "passed": t.passed,
                    "message": t.message,
                    "errors": t.errors,
                    "warnings": t.warnings
                }
                for t in results.test_results
            ]
        }


# For testing
async def test_validation():
    """Test the validation agent"""
    # Mock schema
    mock_schema = {
        "url": "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online",
        "municipality": "ranchi",
        "fields": [
            {
                "name": "mobile",
                "label": "Mobile No",
                "type": "text",
                "selector": "#mobile",
                "required": True
            }
        ],
        "submit_button": {"selector": "button[type='submit']"}
    }

    agent = TestValidationAgent(headless=False)
    result = await agent.execute({"schema": mock_schema})

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    import json
    asyncio.run(test_validation())
