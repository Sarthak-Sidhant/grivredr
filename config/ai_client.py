"""
AI Client for interacting with Claude via MegaLLM API
"""
import os
import base64
from openai import OpenAI
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any

from utils.ai_cache import AICache

load_dotenv()


class AIClient:
    """Unified AI client for Claude models via MegaLLM"""

    def __init__(self, enable_cache: bool = True):
        self.client = OpenAI(
            base_url="https://ai.megallm.io/v1",
            api_key=os.getenv("api_key")
        )

        # Model selection based on task complexity
        self.models = {
            "fast": "claude-haiku-4-5-20251001",  # $1/$5 - Quick tasks
            "balanced": "claude-sonnet-4-5-20250929",  # $3/$15 - Most tasks
            "powerful": "claude-opus-4-5-20251101",  # $5/$25 - Complex reasoning
        }

        # AI call caching for cost optimization
        self.enable_cache = enable_cache
        self.cache = AICache() if enable_cache else None

    def analyze_website_structure(
        self,
        screenshot_base64: str,
        url: str,
        html_snippet: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze website structure using Claude Vision
        Returns form fields, navigation steps, and structure info
        """
        # Check cache first
        prompt = f"""Analyze this grievance/complaint form webpage from {url}.

Your task:
1. Identify ALL form fields (input, textarea, select, file upload, etc.)
2. Determine field types, names, IDs, and whether they're required
3. Identify navigation steps (multi-step forms, captcha, etc.)
4. Note any dropdowns with visible options
5. Identify submit buttons and their selectors

Provide response in this JSON format:
{{
    "form_fields": [
        {{
            "label": "Name",
            "type": "text",
            "selector": "#name",
            "required": true,
            "placeholder": "Enter your name"
        }}
    ],
    "navigation_steps": ["Step 1: Fill details", "Step 2: Upload docs"],
    "submit_button": {{"selector": "#submit", "text": "Submit Complaint"}},
    "captcha_present": false,
    "multi_step": false,
    "form_url": "{url}"
}}

{f"HTML Context: {html_snippet}" if html_snippet else ""}
"""

        if self.cache:
            cached_response = self.cache.get(
                prompt=prompt,
                model=self.models["balanced"],
                image_data=screenshot_base64
            )
            if cached_response:
                return cached_response

        # Cache miss - make AI call
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ]

        response = self.client.chat.completions.create(
            model=self.models["balanced"],
            messages=messages,
            temperature=0.1,
            max_tokens=4000
        )

        result = response.choices[0].message.content

        # Store in cache
        if self.cache:
            self.cache.set(
                prompt=prompt,
                model=self.models["balanced"],
                response=result,
                ttl_hours=24,
                image_data=screenshot_base64
            )

        return result

    def generate_scraper_code(
        self,
        website_analysis: str,
        url: str,
        municipality_name: str
    ) -> str:
        """
        Generate reusable Python scraper code based on website analysis
        """
        prompt = f"""You are an expert Python automation engineer. Generate a production-ready Playwright scraper for this grievance form.

Website: {url}
Municipality: {municipality_name}

Website Analysis:
{website_analysis}

**MANDATORY DEFENSIVE CODING PATTERNS:**

1. **Error Handling:**
   - Wrap ALL Playwright operations in try-except blocks
   - Implement exponential backoff for retries (max 3 attempts)
   - Log detailed error context (selector tried, page state, screenshot)
   - NEVER silently fail - always raise or log errors

2. **Robustness Patterns:**
   - Use explicit waits (page.wait_for_selector) NOT time.sleep()
   - Check element visibility AND interactability before interaction
   - Handle stale element exceptions by refetching the element
   - Validate data types and values before submission

3. **Dynamic Content Handling:**
   - For AJAX dropdowns: select parent → wait 1-2s → verify child options loaded
   - For conditional fields: check if field exists before attempting interaction
   - For multi-step forms: verify page transition completed before proceeding

4. **Selector Fallbacks:**
   Every element interaction must have fallback selectors:
   ```python
   # GOOD - Multiple fallback strategies:
   element = await page.query_selector("#name") or \
             await page.query_selector("[name='name']") or \
             await page.query_selector("input[placeholder*='name' i]")

   # BAD - Single point of failure:
   element = await page.query_selector("#name")
   ```

5. **Test Mode Support:**
   - Include async def run_test_mode(self, test_data: dict) -> dict
   - In test mode: validate field presence but DON'T submit
   - Return structured test results with field coverage

6. **Structured Error Responses:**
   ```python
   return {{
       "success": False,
       "error": "Could not find submit button",
       "attempted_selectors": ["#submit", "button[type='submit']"],
       "page_html": page_html[:500],  # For debugging
       "screenshot": screenshot_path
   }}
   ```

Generate a complete Python class that:
1. Uses Playwright async API
2. Handles navigation and waits intelligently with EXPLICIT WAITS
3. Fills all identified form fields with FALLBACK SELECTORS
4. Handles file uploads if present
5. Submits the form and captures success/error messages
6. Takes screenshots at each step for debugging
7. Returns structured result (success, tracking_id, screenshots, errors)
8. Has COMPREHENSIVE error handling and retries

Requirements:
- Class name: {municipality_name.title().replace(' ', '')}Scraper
- Method: async def submit_grievance(self, data: dict) -> dict
- Include: async def run_test_mode(self, test_data: dict) -> dict
- Input data format: {{"name": "...", "phone": "...", "complaint": "...", "category": "...", "file_path": "..."}}
- Use headless=False for debugging, make it configurable
- Add stealth mode to avoid detection
- Log all actions for debugging

Return ONLY the Python code, no explanations. Make it production-ready with DEFENSIVE patterns.
"""

        response = self.client.chat.completions.create(
            model=self.models["powerful"],  # Use powerful model for code generation
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=8000
        )

        return response.choices[0].message.content

    def improve_scraper_with_feedback(
        self,
        original_code: str,
        error_log: str,
        screenshot_base64: Optional[str] = None
    ) -> str:
        """
        Fix scraper based on execution errors
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""This scraper failed. Fix it based on the error:

Original Code:
```python
{original_code}
```

Error Log:
{error_log}

Return the complete fixed code. Identify the issue and resolve it.
"""
                    }
                ]
            }
        ]

        if screenshot_base64:
            messages[0]["content"].insert(1, {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}
            })

        response = self.client.chat.completions.create(
            model=self.models["balanced"],
            messages=messages,
            temperature=0.2,
            max_tokens=8000
        )

        return response.choices[0].message.content

    def extract_status_from_page(
        self,
        screenshot_base64: str,
        html_text: str,
        tracking_id: str
    ) -> Dict[str, Any]:
        """
        Extract grievance status from status check page
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"}
                    },
                    {
                        "type": "text",
                        "text": f"""Extract grievance status for tracking ID: {tracking_id}

HTML Text:
{html_text[:2000]}

Return JSON:
{{
    "status": "Pending/In Progress/Resolved/Rejected",
    "last_updated": "date",
    "remarks": "any remarks or updates",
    "tracking_id": "{tracking_id}"
}}
"""
                    }
                ]
            }
        ]

        response = self.client.chat.completions.create(
            model=self.models["fast"],  # Fast model for extraction
            messages=messages,
            temperature=0.1,
            max_tokens=500
        )

        return response.choices[0].message.content

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get AI cache statistics

        Returns:
            Cache stats including hit rate and cost savings
        """
        if not self.cache:
            return {"cache_enabled": False}

        stats = self.cache.get_stats()
        savings = self.cache.estimate_cost_savings(avg_cost_per_call=0.05)

        return {
            "cache_enabled": True,
            **stats,
            "cost_savings": savings
        }

    def clear_cache(self):
        """Clear AI cache"""
        if self.cache:
            return self.cache.clear_all()
        return 0


# Singleton instance
ai_client = AIClient()
