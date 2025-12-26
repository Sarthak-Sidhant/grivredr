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
