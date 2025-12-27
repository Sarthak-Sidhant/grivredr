"""
AI prompts for self-healing scraper code
"""

HEALING_PROMPT_TEMPLATE = """You are an expert Python developer fixing a failing web scraper.

The generated scraper failed validation with the following errors:

VALIDATION ERRORS:
{error_details}

ORIGINAL REQUIREMENTS:
Municipality: {municipality_name}
URL: {url}
Form Analysis: {form_analysis}

GENERATED CODE (FAILED):
```python
{failed_code}
```

VALIDATION RESULTS:
- Execution Status: {execution_status}
- Execution Errors: {execution_errors}
- Schema Mismatches: {schema_errors}
- Timeout Issues: {timeout_issues}
- Screenshot Available: {screenshot_path}

TASK: Fix the code to address these specific errors.

FOCUS ON:
1. Correcting the specific errors mentioned above
2. Adding more robust error handling
3. Improving wait conditions for dynamic content
4. Validating field extraction logic
5. Ensuring selectors are correct and have fallbacks

DEFENSIVE CODING REQUIREMENTS:
- Use explicit waits (WebDriverWait) instead of time.sleep()
- Add try-except blocks around all Playwright operations
- Provide fallback selectors for each element
- Check element visibility AND interactability before interaction
- Handle stale element exceptions by refetching
- Log detailed context on failures

Return ONLY the complete fixed Python code, no explanations.
The code should start with the imports and class definition.
"""


VALIDATION_ERROR_PROMPT = """You are analyzing why a scraper validation failed.

SCRAPER CODE:
```python
{scraper_code}
```

VALIDATION ATTEMPT:
{validation_log}

ERROR MESSAGE:
{error_message}

TASK: Explain in 2-3 sentences:
1. What caused the failure
2. What specific code change would fix it
3. Whether this is a selector issue, timing issue, or logic error

Keep the response concise and actionable.
"""


CONFIDENCE_ASSESSMENT_PROMPT = """You are assessing the confidence level of a generated scraper.

FORM ANALYSIS:
{form_analysis}

GENERATED SCRAPER CODE:
```python
{scraper_code}
```

VALIDATION RESULTS:
- Syntax Valid: {syntax_valid}
- Test Execution: {execution_result}
- Field Coverage: {field_coverage}
- Error Handling: {has_error_handling}

TASK: Provide a confidence score (0.0 to 1.0) and brief reasoning.

Response format:
{{
    "confidence_score": 0.85,
    "reasoning": "High confidence due to successful validation and comprehensive error handling, but noted AJAX timing concerns.",
    "concerns": ["AJAX dropdown timing may be fragile", "CAPTCHA detection unclear"],
    "strengths": ["All fields covered", "Proper error handling", "Fallback selectors present"]
}}

Return only valid JSON.
"""


API_AWARE_GENERATION_PROMPT = """You are generating a Python web scraper with DIRECT API CALLS when possible.

CAPTURED NETWORK ACTIVITY:
{api_calls}

FORM ANALYSIS:
{form_analysis}

EVENT LISTENERS DETECTED:
{event_listeners}

CRITICAL REQUIREMENTS:

1. **PREFER DIRECT API CALLS OVER BROWSER:**
   - If you see API calls like GET /api/getDistricts?stateId=12, USE httpx/aiohttp directly
   - Only use Playwright if:
     * APIs require complex authentication (session cookies, CSRF tokens)
     * JavaScript computes values client-side
     * Form has CAPTCHA or OTP

2. **GENERATE HYBRID CODE:**
   ```python
   import httpx
   from playwright.async_api import async_playwright

   class ScraperName:
       async def submit_via_api(self, data):
           \"\"\"Direct API submission (fast, no browser)\"\"\"
           async with httpx.AsyncClient() as client:
               # Use captured API calls
               response = await client.post(
                   'actual_endpoint_from_network_tab',
                   json=data,
                   headers=captured_headers
               )
               return response.json()

       async def submit_via_browser(self, data):
           \"\"\"Browser fallback if API doesn't work\"\"\"
           # Playwright code here
   ```

3. **HANDLE EVENT LISTENERS:**
   - For fields with 'blur' listeners: `await field.focus()` then `await field.blur()`
   - For fields with 'input' listeners: Type with delay to trigger validation
   - Example:
   ```python
   # Field has blur validation
   await page.fill('#email', email)
   await page.focus('#email')
   await asyncio.sleep(0.1)
   await page.blur('#email')  # Triggers validation
   await asyncio.sleep(0.3)  # Wait for validation
   ```

4. **API CALL EXAMPLES FROM NETWORK TAB:**
{api_call_examples}

Generate code that:
- Tries direct API first (if safe)
- Falls back to browser if API fails
- Handles all event listeners properly
- Includes proper error handling

Return ONLY the complete Python code.
"""


FLICKER_FIELD_TEMPLATE = """
async def _flicker_field(self, page: Page, selector: str, value: str, has_blur: bool = False):
    \"\"\"
    Fill field and trigger validation events if needed

    Args:
        page: Playwright page
        selector: Field selector
        value: Value to fill
        has_blur: Whether field has blur listener
    \"\"\"
    try:
        element = await page.wait_for_selector(selector, state='visible', timeout=5000)

        # Focus to trigger focus events
        await element.focus()
        await asyncio.sleep(0.1)

        # Fill the value
        await element.fill(value)
        await asyncio.sleep(0.1)

        # If has blur listener, trigger it
        if has_blur:
            await element.blur()
            await asyncio.sleep(0.3)  # Wait for validation
            logger.info(f"Triggered blur validation for {selector}")

        return True

    except Exception as e:
        logger.error(f"Failed to fill {selector}: {e}")
        return False
"""
