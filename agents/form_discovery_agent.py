"""
Form Discovery Agent - Intelligently explores and understands grievance forms
Uses iterative exploration with Claude Vision and reflection
"""
import asyncio
import base64
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path
from playwright.async_api import async_playwright, Page, Browser

from agents.base_agent import BaseAgent, cost_tracker
from config.ai_client import ai_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FormField:
    """Represents a single form field"""
    name: str
    label: str
    type: str  # text, dropdown, textarea, file, checkbox, radio
    selector: str
    required: bool = False
    placeholder: str = ""
    options: List[str] = field(default_factory=list)
    depends_on: Optional[str] = None  # For cascading dropdowns
    validation_pattern: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class FormSchema:
    """Complete form structure"""
    url: str
    municipality: str
    title: str = ""
    sections: List[Dict[str, Any]] = field(default_factory=list)
    fields: List[FormField] = field(default_factory=list)
    submit_button: Dict[str, str] = field(default_factory=dict)
    submission_type: str = "form_post"  # or "ajax"
    success_indicator: Dict[str, Any] = field(default_factory=dict)
    requires_captcha: bool = False
    multi_step: bool = False
    discovered_fields_count: int = 0
    confidence_score: float = 0.0

    def to_dict(self):
        return asdict(self)


class FormDiscoveryAgent(BaseAgent):
    """
    Agent that discovers form structure through iterative exploration
    """

    def __init__(self, headless: bool = False):
        super().__init__(name="FormDiscoveryAgent", max_attempts=3)
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.screenshots_dir = Path("dashboard/static/screenshots")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    async def _execute_attempt(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute form discovery process
        """
        url = task["url"]
        municipality = task.get("municipality", "unknown")
        hints = task.get("hints", {})

        logger.info(f"🔍 [{self.name}] Discovering form at {url}")

        # Initialize browser
        await self._init_browser()

        try:
            # Phase 1: Initial visual analysis
            visual_analysis = await self._visual_analysis_phase(url, municipality)
            if not visual_analysis["success"]:
                return visual_analysis

            # Phase 2: Interactive exploration
            interactive_analysis = await self._interactive_exploration_phase(
                url, visual_analysis["initial_schema"], hints
            )

            # Phase 3: Validation discovery
            validation_analysis = await self._validation_discovery_phase(
                url, interactive_analysis["schema"]
            )

            # Phase 4: Build final schema
            final_schema = await self._build_final_schema(
                url, municipality, validation_analysis
            )

            # Confidence check
            if final_schema.confidence_score < 0.6:
                return {
                    "success": False,
                    "message": f"Low confidence: {final_schema.confidence_score}",
                    "schema": final_schema.to_dict(),
                    "reason": "Need human verification"
                }

            return {
                "success": True,
                "message": f"Discovered {len(final_schema.fields)} fields",
                "schema": final_schema.to_dict(),
                "confidence": final_schema.confidence_score
            }

        except Exception as e:
            logger.error(f"❌ [{self.name}] Discovery failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Discovery exception"
            }

        finally:
            await self._cleanup_browser()

    async def _init_browser(self):
        """Initialize Playwright browser"""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox'
                ]
            )

    async def _cleanup_browser(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def _visual_analysis_phase(
        self,
        url: str,
        municipality: str
    ) -> Dict[str, Any]:
        """
        Phase 1: Visual analysis with Claude Vision
        """
        logger.info(f"📸 [{self.name}] Phase 1: Visual analysis")

        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()

        try:
            # Navigate
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # Let page settle

            # Take screenshot
            screenshot_path = self.screenshots_dir / f"{municipality}_initial.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)

            # Convert to base64
            with open(screenshot_path, "rb") as f:
                screenshot_base64 = base64.b64encode(f.read()).decode()

            # Get page HTML
            html_content = await page.content()

            # Analyze with Claude Vision
            analysis = await self._ask_claude_vision(
                screenshot_base64,
                url,
                html_content[:5000],  # First 5000 chars
                phase="initial"
            )

            self._record_action(
                action_type="visual_analysis",
                description="Analyzed page with Claude Vision",
                result=analysis["response"][:200],
                success=True,
                cost=analysis["cost"]
            )

            # Parse response to initial schema
            initial_schema = self._parse_vision_response(
                analysis["response"],
                url,
                municipality
            )

            return {
                "success": True,
                "initial_schema": initial_schema,
                "screenshot": str(screenshot_path)
            }

        except Exception as e:
            logger.error(f"Visual analysis failed: {e}")
            return {"success": False, "error": str(e)}

        finally:
            await context.close()

    async def _ask_claude_vision(
        self,
        screenshot_base64: str,
        url: str,
        html_snippet: str,
        phase: str = "initial"
    ) -> Dict[str, Any]:
        """
        Ask Claude Vision to analyze the form
        """
        if phase == "initial":
            prompt = f"""Analyze this grievance/complaint form from {url}.

Your task:
1. Identify the form title and purpose
2. List ALL visible form fields with:
   - Field label/name
   - Input type (text, dropdown, textarea, file, checkbox, radio)
   - Whether it appears required (look for *, "Required", red indicators)
   - CSS selector (id or class)
   - Placeholder text if visible

3. Identify the submit button (text and selector)
4. Note any sections/groups
5. Detect if this appears to be multi-step form
6. Check for CAPTCHA
7. Look for validation hints (e.g., "10 digits", "valid email")

HTML Context (first 5000 chars):
{html_snippet}

Return detailed JSON:
{{
    "form_title": "...",
    "sections": [
        {{
            "section_name": "...",
            "fields": [
                {{
                    "label": "...",
                    "type": "text|dropdown|textarea|file|checkbox",
                    "selector": "#id or .class",
                    "required": true/false,
                    "placeholder": "...",
                    "validation_hint": "..."
                }}
            ]
        }}
    ],
    "submit_button": {{"text": "...", "selector": "..."}},
    "multi_step": true/false,
    "captcha": true/false,
    "notes": ["Any observations about the form"]
}}
"""

        import time
        start = time.time()

        response = ai_client.client.chat.completions.create(
            model=ai_client.models["balanced"],  # Sonnet for Vision
            messages=[{
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
            }],
            temperature=0.1,
            max_tokens=4000
        )

        elapsed = time.time() - start
        usage = response.usage

        cost = cost_tracker.track_call(
            model=ai_client.models["balanced"],
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            agent_name=self.name
        )

        return {
            "response": response.choices[0].message.content,
            "cost": cost,
            "elapsed": elapsed
        }

    def _parse_vision_response(
        self,
        response: str,
        url: str,
        municipality: str
    ) -> FormSchema:
        """Parse Claude's vision response into FormSchema"""
        import re

        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
            except:
                # Try to find raw JSON
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                data = json.loads(json_match.group(0)) if json_match else {}
        else:
            data = {}

        schema = FormSchema(url=url, municipality=municipality)

        schema.title = data.get("form_title", "")
        schema.multi_step = data.get("multi_step", False)
        schema.requires_captcha = data.get("captcha", False)
        schema.submit_button = data.get("submit_button", {})

        # Parse fields from sections
        for section in data.get("sections", []):
            schema.sections.append({
                "name": section.get("section_name", ""),
                "fields": section.get("fields", [])
            })

            for field_data in section.get("fields", []):
                field = FormField(
                    name=field_data.get("label", "").lower().replace(" ", "_"),
                    label=field_data.get("label", ""),
                    type=field_data.get("type", "text"),
                    selector=field_data.get("selector", ""),
                    required=field_data.get("required", False),
                    placeholder=field_data.get("placeholder", ""),
                    validation_pattern=field_data.get("validation_hint", "")
                )
                schema.fields.append(field)

        schema.discovered_fields_count = len(schema.fields)
        schema.confidence_score = 0.5  # Initial confidence

        logger.info(f"📋 Parsed {len(schema.fields)} fields from vision analysis")

        return schema

    async def _interactive_exploration_phase(
        self,
        url: str,
        schema: FormSchema,
        hints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Phase 2: Interactive exploration to find dynamic content
        """
        logger.info(f"🎮 [{self.name}] Phase 2: Interactive exploration")

        context = await self.browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(1)

            # Explore dropdowns
            await self._explore_dropdowns(page, schema)

            # Check for fields below the fold
            await self._scroll_and_discover(page, schema)

            # Detect cascading relationships
            await self._detect_cascading_fields(page, schema)

            schema.confidence_score += 0.2  # Boost confidence

            return {
                "success": True,
                "schema": schema
            }

        finally:
            await context.close()

    async def _explore_dropdowns(self, page: Page, schema: FormSchema):
        """Click dropdowns to see their options"""
        for field in schema.fields:
            if field.type == "dropdown" and field.selector:
                try:
                    # Try to find the dropdown
                    dropdown = page.locator(field.selector).first
                    if await dropdown.count() > 0:
                        logger.info(f"🔽 Exploring dropdown: {field.label}")

                        # Click to open
                        await dropdown.click(timeout=5000)
                        await asyncio.sleep(0.5)

                        # Try to get options
                        options = await page.evaluate(f"""
                            () => {{
                                const select = document.querySelector('{field.selector}');
                                if (select && select.tagName === 'SELECT') {{
                                    return Array.from(select.options).map(opt => opt.text);
                                }}
                                return [];
                            }}
                        """)

                        if options:
                            field.options = [opt for opt in options if opt.strip()]
                            logger.info(f"   Found {len(field.options)} options")

                except Exception as e:
                    logger.warning(f"   Could not explore {field.label}: {e}")

    async def _scroll_and_discover(self, page: Page, schema: FormSchema):
        """Scroll page to discover lazy-loaded fields"""
        logger.info(f"📜 Scrolling to discover hidden fields")

        # Scroll to bottom
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        # Get all form inputs
        all_inputs = await page.evaluate("""
            () => {
                const inputs = document.querySelectorAll('input, select, textarea');
                return Array.from(inputs).map(input => ({
                    type: input.type || input.tagName.toLowerCase(),
                    name: input.name || input.id,
                    id: input.id,
                    required: input.required,
                    placeholder: input.placeholder
                }));
            }
        """)

        existing_names = {f.name for f in schema.fields}

        for input_data in all_inputs:
            name = input_data.get("name", "")
            if name and name not in existing_names:
                # Found new field!
                logger.info(f"   ✨ Discovered new field: {name}")

                field = FormField(
                    name=name,
                    label=name.replace("_", " ").title(),
                    type=input_data["type"],
                    selector=f"#{input_data['id']}" if input_data['id'] else f"[name='{name}']",
                    required=input_data.get("required", False),
                    placeholder=input_data.get("placeholder", "")
                )
                schema.fields.append(field)
                existing_names.add(name)

    async def _detect_cascading_fields(self, page: Page, schema: FormSchema):
        """Detect if any dropdowns trigger others"""
        logger.info(f"🔗 Detecting cascading relationships")

        dropdowns = [f for f in schema.fields if f.type == "dropdown"]

        for i, parent in enumerate(dropdowns):
            for child in dropdowns[i+1:]:
                # Test if selecting parent populates child
                try:
                    if parent.options:
                        logger.info(f"   Testing: {parent.label} → {child.label}")

                        # Select first option in parent
                        await page.select_option(parent.selector, parent.options[0], timeout=3000)
                        await asyncio.sleep(0.5)

                        # Check if child got populated
                        child_options_after = await page.evaluate(f"""
                            () => {{
                                const select = document.querySelector('{child.selector}');
                                if (select) {{
                                    return Array.from(select.options).map(o => o.text);
                                }}
                                return [];
                            }}
                        """)

                        if len(child_options_after) > len(child.options):
                            logger.info(f"   ✅ Cascading detected!")
                            child.depends_on = parent.name
                            child.options = child_options_after

                except Exception as e:
                    logger.debug(f"   Cascade test failed: {e}")

    async def _validation_discovery_phase(
        self,
        url: str,
        schema: FormSchema
    ) -> Dict[str, Any]:
        """
        Phase 3: Submit empty form to discover required fields
        """
        logger.info(f"✅ [{self.name}] Phase 3: Validation discovery")

        context = await self.browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Try to submit empty form
            submit_selector = schema.submit_button.get("selector", "")
            if submit_selector:
                logger.info(f"🚀 Submitting empty form to discover validation")

                await page.click(submit_selector, timeout=5000)
                await asyncio.sleep(1)

                # Capture any error messages
                error_messages = await page.evaluate("""
                    () => {
                        const errors = document.querySelectorAll(
                            '.error, .invalid, .text-danger, [class*="error"]'
                        );
                        return Array.from(errors).map(e => e.textContent.trim());
                    }
                """)

                logger.info(f"   Found {len(error_messages)} validation errors")

                # Update field requirements based on errors
                for error in error_messages:
                    for field in schema.fields:
                        if field.label.lower() in error.lower():
                            field.required = True
                            field.error_message = error
                            logger.info(f"   ✓ {field.label} marked as required")

                schema.confidence_score += 0.2

                return {
                    "success": True,
                    "validation_errors": error_messages,
                    "schema": schema
                }

        except Exception as e:
            logger.warning(f"Validation discovery failed: {e}")

        finally:
            await context.close()

        return {"success": True, "schema": schema}

    async def _build_final_schema(
        self,
        url: str,
        municipality: str,
        validation_result: Dict[str, Any]
    ) -> FormSchema:
        """
        Phase 4: Build final schema with confidence scoring
        """
        schema = validation_result["schema"]

        # Calculate final confidence
        confidence_factors = []

        # Has fields?
        if len(schema.fields) > 0:
            confidence_factors.append(0.3)

        # Has submit button?
        if schema.submit_button:
            confidence_factors.append(0.2)

        # Required fields identified?
        required_count = sum(1 for f in schema.fields if f.required)
        if required_count > 0:
            confidence_factors.append(0.2)

        # Dropdown options populated?
        dropdowns_with_options = sum(
            1 for f in schema.fields
            if f.type == "dropdown" and len(f.options) > 0
        )
        if dropdowns_with_options > 0:
            confidence_factors.append(0.15)

        # Validation errors captured?
        if validation_result.get("validation_errors"):
            confidence_factors.append(0.15)

        schema.confidence_score = sum(confidence_factors)

        logger.info(f"📊 Final confidence: {schema.confidence_score:.2f}")
        logger.info(f"📋 Final field count: {len(schema.fields)}")

        return schema


# For testing
async def test_form_discovery():
    """Test the form discovery agent"""
    agent = FormDiscoveryAgent(headless=False)

    result = await agent.execute({
        "url": "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online",
        "municipality": "ranchi"
    })

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(test_form_discovery())
