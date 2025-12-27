"""
AI Client - Unified interface using Anthropic SDK with MegaLLM
Supports both Anthropic native and LangChain integration
"""
import os
from anthropic import Anthropic
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any
import logging

from utils.ai_cache import AICache

load_dotenv()
logger = logging.getLogger(__name__)


class AIClient:
    """
    Unified AI client using Anthropic SDK with MegaLLM backend
    Compatible with both native Anthropic and LangChain
    """

    def __init__(self, enable_cache: bool = True):
        """
        Initialize Anthropic client with MegaLLM endpoint

        Args:
            enable_cache: Enable AI response caching for cost savings
        """
        # Validate API key exists
        api_key = os.getenv("api_key")
        if not api_key:
            raise ValueError(
                "API key not found. Set 'api_key' environment variable. "
                "Example: export api_key='your_megallm_api_key'"
            )

        # Initialize Anthropic client with MegaLLM
        self.client = Anthropic(
            base_url="https://ai.megallm.io",
            api_key=api_key
        )

        # Model selection based on task complexity
        self.models = {
            "fast": "claude-haiku-4.5",  # $1/$5 - Quick tasks
            "balanced": "claude-sonnet-4.5",  # $3/$15 - Most tasks
            "powerful": "claude-opus-4.5",  # $5/$25 - Complex reasoning
        }

        # AI call caching for cost optimization
        self.enable_cache = enable_cache
        self.cache = AICache() if enable_cache else None

        logger.info("✓ Anthropic client initialized with MegaLLM")

    def _create_message(
        self,
        prompt: str,
        model: str = "balanced",
        max_tokens: int = 4000,
        temperature: float = 0.1,
        images: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Create a message using Anthropic SDK

        Args:
            prompt: Text prompt
            model: Model tier (fast/balanced/powerful)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            images: Optional list of images (base64 encoded)

        Returns:
            Response text
        """
        # Check cache first
        cache_key = f"{prompt}_{model}"
        if self.cache and not images:
            cached = self.cache.get(prompt=prompt, model=self.models[model])
            if cached:
                logger.debug(f"Cache hit for model={model}")
                return cached

        # Build content array
        content = []

        # Add images if provided
        if images:
            for img in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("media_type", "image/png"),
                        "data": img["data"]
                    }
                })

        # Add text prompt
        content.append({
            "type": "text",
            "text": prompt
        })

        # Create message with Anthropic SDK
        try:
            message = self.client.messages.create(
                model=self.models[model],
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{
                    "role": "user",
                    "content": content
                }]
            )

            # Extract text from response
            response_text = message.content[0].text

            # Cache response (if no images for simpler caching)
            if self.cache and not images:
                self.cache.set(
                    prompt=prompt,
                    model=self.models[model],
                    response=response_text,
                    ttl_hours=24
                )

            return response_text

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def analyze_website_structure(
        self,
        screenshot_base64: str,
        url: str,
        html_snippet: Optional[str] = None
    ) -> str:
        """
        Analyze website structure using Claude Vision

        Args:
            screenshot_base64: Base64 encoded screenshot
            url: Website URL
            html_snippet: Optional HTML context

        Returns:
            JSON string with form analysis
        """
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

        images = [{
            "media_type": "image/png",
            "data": screenshot_base64
        }]

        return self._create_message(
            prompt=prompt,
            model="balanced",
            max_tokens=4000,
            temperature=0.1,
            images=images
        )

    def generate_scraper_code(
        self,
        website_analysis: str,
        url: str,
        municipality_name: str
    ) -> str:
        """
        Generate reusable Python scraper code

        Args:
            website_analysis: Analyzed form structure
            url: Form URL
            municipality_name: Municipality identifier

        Returns:
            Complete Python scraper code
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
   Every element interaction must have fallback selectors

5. **Test Mode Support:**
   - Include async def run_test_mode(self, test_data: dict) -> dict
   - In test mode: validate field presence but DON'T submit
   - Return structured test results with field coverage

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
- Use headless=False for debugging, make it configurable
- Add stealth mode to avoid detection
- Log all actions for debugging

Return ONLY the Python code, no explanations. Make it production-ready with DEFENSIVE patterns.
"""

        return self._create_message(
            prompt=prompt,
            model="powerful",
            max_tokens=8000,
            temperature=0.2
        )

    def improve_scraper_with_feedback(
        self,
        original_code: str,
        error_log: str,
        screenshot_base64: Optional[str] = None
    ) -> str:
        """
        Fix scraper based on execution errors

        Args:
            original_code: Original scraper code
            error_log: Execution error details
            screenshot_base64: Optional error screenshot

        Returns:
            Fixed scraper code
        """
        prompt = f"""This scraper failed. Fix it based on the error:

Original Code:
```python
{original_code}
```

Error Log:
{error_log}

Return the complete fixed code. Identify the issue and resolve it.
"""

        images = None
        if screenshot_base64:
            images = [{
                "media_type": "image/png",
                "data": screenshot_base64
            }]

        return self._create_message(
            prompt=prompt,
            model="balanced",
            max_tokens=8000,
            temperature=0.2,
            images=images
        )

    def extract_status_from_page(
        self,
        screenshot_base64: str,
        html_text: str,
        tracking_id: str
    ) -> str:
        """
        Extract grievance status from status check page

        Args:
            screenshot_base64: Page screenshot
            html_text: Page HTML
            tracking_id: Tracking/reference ID

        Returns:
            JSON with extracted status
        """
        prompt = f"""Extract grievance status for tracking ID: {tracking_id}

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

        images = [{
            "media_type": "image/png",
            "data": screenshot_base64
        }]

        return self._create_message(
            prompt=prompt,
            model="fast",
            max_tokens=500,
            temperature=0.1,
            images=images
        )

    def get_langchain_chat_model(self, model_tier: str = "balanced"):
        """
        Get LangChain-compatible Anthropic chat model

        Args:
            model_tier: Model tier (fast/balanced/powerful)

        Returns:
            ChatAnthropic instance
        """
        try:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=self.models[model_tier],
                anthropic_api_key=os.getenv("api_key"),
                anthropic_api_url="https://ai.megallm.io",
                max_tokens=4000,
                temperature=0.1
            )
        except ImportError:
            logger.warning("langchain-anthropic not installed")
            return None

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
