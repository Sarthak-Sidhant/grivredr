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
from utils.js_runtime_monitor import JSRuntimeMonitor

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

    def __init__(self, headless: bool = False, enable_js_monitoring: bool = True):
        super().__init__(name="FormDiscoveryAgent", max_attempts=3)
        self.headless = headless
        self.enable_js_monitoring = enable_js_monitoring
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.screenshots_dir = Path("outputs/screenshots")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.js_monitor = JSRuntimeMonitor() if enable_js_monitoring else None
        self.js_events = []

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

            # Phase 2: Interactive exploration (with JS monitoring)
            interactive_analysis = await self._interactive_exploration_phase(
                url, visual_analysis["initial_schema"], hints
            )

            # Phase 2.5: Analyze captured JS events
            if self.js_monitor and self.js_events:
                js_analysis = self.js_monitor.analyze_events(self.js_events)
                interactive_analysis["js_analysis"] = js_analysis
                logger.info(f"📊 JS Analysis: {self.js_monitor.get_summary()}")

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

            # NEW: Extract event listeners from form fields
            event_listeners = await self._extract_event_listeners(page)
            logger.info(f"   🎯 Detected {len(event_listeners)} fields with event listeners")

            # Analyze with Claude Vision
            analysis = await self._ask_claude_vision(
                screenshot_base64,
                url,
                html_content[:5000],  # First 5000 chars
                phase="initial",
                event_listeners=event_listeners  # Pass event info to Claude
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
        phase: str = "initial",
        event_listeners: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Ask Claude Vision to analyze the form
        """
        if phase == "initial":
            event_info = ""
            if event_listeners:
                event_info = f"""
**DETECTED EVENT LISTENERS:**
The following fields have JavaScript event handlers that may trigger validation or dynamic behavior:
{json.dumps(event_listeners, indent=2)}

NOTE: Fields with 'blur' listeners need to be focused then unfocused to trigger validation.
Fields with 'input' listeners validate as you type.
"""

            prompt = f"""Analyze this grievance/complaint form from {url}.

{event_info}

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

IMPORTANT for dropdowns:
- Do NOT extract visible dropdown OPTIONS from the screenshot
- The system will programmatically extract dropdown options later
- Only identify that a dropdown EXISTS and its selector
- Do NOT list the dropdown choices you see in the image

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

        response = ai_client.client.messages.create(
            model=ai_client.models["balanced"],  # Sonnet for Vision
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_base64
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
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            agent_name=self.name
        )

        return {
            "response": response.content[0].text,
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
                # Ensure we have a specific selector (prefer ID)
                selector = field_data.get("selector", "")

                # If selector is too generic, skip it for now (will be found later by scroll_and_discover)
                if selector and not any(generic in selector for generic in ['input[type=', 'select', 'textarea']):
                    field = FormField(
                        name=field_data.get("label", "").lower().replace(" ", "_"),
                        label=field_data.get("label", ""),
                        type=field_data.get("type", "text"),
                        selector=selector,
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

            # Inject JS monitoring if enabled
            if self.js_monitor:
                logger.info(f"🔍 [{self.name}] Injecting JS runtime monitoring...")
                await self.js_monitor.inject_monitoring(page)
                await asyncio.sleep(0.5)

            # Explore dropdowns
            await self._explore_dropdowns(page, schema)

            # Check for fields below the fold
            await self._scroll_and_discover(page, schema)

            # Detect cascading relationships
            await self._detect_cascading_fields(page, schema)

            # Interact with form to trigger JS (if monitoring enabled)
            if self.js_monitor:
                logger.info(f"🖱️ [{self.name}] Interacting with form to trigger JS...")
                await self.js_monitor.interact_with_form(page)
                await asyncio.sleep(1)

                # Capture events
                self.js_events = await self.js_monitor.capture_events(page, timeout=2)
                logger.info(f"✓ Captured {len(self.js_events)} JS events")

            schema.confidence_score += 0.2  # Boost confidence

            return {
                "success": True,
                "schema": schema
            }

        finally:
            await context.close()

    async def _explore_dropdowns(self, page: Page, schema: FormSchema):
        """Click dropdowns to see their options - handles both standard and Select2 dropdowns"""
        for field in schema.fields:
            if field.type == "dropdown" and field.selector:
                try:
                    logger.info(f"🔽 Exploring dropdown: {field.label}")

                    # Skip language selectors and login dropdowns
                    if any(skip in field.selector.lower() for skip in ['language', 'login', 'txtloginid']):
                        logger.info(f"   Skipping {field.label} (appears to be non-form dropdown)")
                        continue

                    # Try multiple strategies to extract options
                    options = await page.evaluate(f"""
                        (selector) => {{
                            const select = document.querySelector(selector);
                            if (!select) return [];

                            // Strategy 1: Standard <select> element
                            if (select.tagName === 'SELECT') {{
                                const opts = Array.from(select.options).map(opt => ({{
                                    text: opt.text.trim(),
                                    value: opt.value
                                }}));
                                return opts.filter(o => o.text && o.text !== 'Please Select' && o.text !== 'Select');
                            }}

                            // Strategy 2: Select2 - look for data stored in original select
                            const select2Container = select.closest('.select2-container') ||
                                                    document.querySelector(`[data-select2-id="${{select.id}}"]`) ||
                                                    select.parentElement?.querySelector('select');

                            if (select2Container) {{
                                // Find the actual hidden select element
                                const hiddenSelect = document.getElementById(select.id) ||
                                                   select.parentElement?.querySelector('select[id*="' + select.id.split('_')[0] + '"]');

                                if (hiddenSelect && hiddenSelect.options) {{
                                    const opts = Array.from(hiddenSelect.options).map(opt => ({{
                                        text: opt.text.trim(),
                                        value: opt.value
                                    }}));
                                    return opts.filter(o => o.text && o.text !== 'Please Select' && o.text !== 'Select');
                                }}
                            }}

                            return [];
                        }}
                    """, field.selector)

                    # If no options found via DOM, try clicking and capturing visible options
                    if not options:
                        try:
                            # Find the Select2 trigger element
                            select2_trigger = page.locator(f"{field.selector}").or_(
                                page.locator(f"span.select2-container").filter(has=page.locator(field.selector))
                            ).or_(
                                page.locator(f"#{field.selector.strip('#')}_container")
                            ).first

                            if await select2_trigger.count() > 0:
                                await select2_trigger.click(timeout=3000)
                                await asyncio.sleep(0.5)

                                # Capture visible options from dropdown
                                options = await page.evaluate("""
                                    () => {
                                        const results = document.querySelectorAll('.select2-results li, .select2-results__option');
                                        return Array.from(results).map(li => ({
                                            text: li.textContent.trim(),
                                            value: li.getAttribute('data-value') || li.textContent.trim()
                                        })).filter(o => o.text && !o.text.includes('Searching') && !o.text.includes('Loading'));
                                    }
                                """)

                                # Close dropdown
                                await page.keyboard.press('Escape')
                                await asyncio.sleep(0.3)
                        except Exception as e:
                            logger.debug(f"Select2 click failed for {field.label}: {e}")

                    if options:
                        field.options = [opt['text'] for opt in options if opt.get('text')]
                        logger.info(f"   Found {len(field.options)} options: {field.options[:3]}..." if len(field.options) > 3 else f"   Found {len(field.options)} options: {field.options}")
                    else:
                        logger.warning(f"   No options found for {field.label}")

                except Exception as e:
                    logger.warning(f"   Could not explore {field.label}: {e}")

    async def _scroll_and_discover(self, page: Page, schema: FormSchema):
        """Scroll page to discover lazy-loaded fields - focuses on main complaint form"""
        logger.info(f"📜 Scrolling to discover hidden fields")

        # Scroll to bottom
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        # Get all form inputs, but filter out common non-form sections
        all_inputs = await page.evaluate("""
            () => {
                // First, try to find the main complaint/grievance form
                const mainForm = document.querySelector(
                    'form[id*="complaint"], form[id*="grievance"], form[id*="ContentPlaceHolder"], ' +
                    'div[id*="complaint"], div[id*="grievance"], main, .main-content'
                );

                // If found, search only within that form; otherwise search entire page
                const searchRoot = mainForm || document;

                const inputs = searchRoot.querySelectorAll('input, select, textarea');

                return Array.from(inputs)
                    .filter(input => {
                        // Filter out fields from login, navbar, footer
                        const isInLogin = input.closest('#login, .login, [class*="login"], [id*="login"]');
                        const isInNav = input.closest('nav, .navbar, header, .header');
                        const isInFooter = input.closest('footer, .footer');
                        const isLanguageSelector = input.id?.includes('Language') || input.name?.includes('Language');

                        return !isInLogin && !isInNav && !isInFooter && !isLanguageSelector;
                    })
                    .map(input => ({
                        type: input.type || input.tagName.toLowerCase(),
                        name: input.name || input.id,
                        id: input.id,
                        required: input.required,
                        placeholder: input.placeholder,
                        visible: input.offsetParent !== null  // Check if actually visible
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

    async def _disambiguate_submit_button_with_claude(
        self,
        page: Page,
        possible_buttons: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Use Claude to identify the correct submit button from multiple candidates
        Handles cases like abua_sathi where "Register Complaint" appears as both heading and button
        """
        logger.info(f"🤔 [{self.name}] Multiple submit buttons found, asking Claude to disambiguate...")

        # Take screenshot
        screenshot = await page.screenshot()
        screenshot_base64 = base64.b64encode(screenshot).decode()

        # Get button details
        buttons_info = []
        for i, btn in enumerate(possible_buttons):
            buttons_info.append({
                "index": i,
                "text": btn.get("text", ""),
                "type": btn.get("type", ""),
                "selector": btn.get("selector", ""),
                "class": btn.get("class", ""),
                "visible": btn.get("visible", False),
                "in_viewport": btn.get("in_viewport", False)
            })

        prompt = f"""You are analyzing a form to identify the ACTUAL submit button.

Multiple button candidates were found, but only ONE is the real submit button.
The others might be:
- Headings styled as buttons
- Navigation buttons
- Decorative elements
- Back-to-top buttons

Here are the candidates:
{json.dumps(buttons_info, indent=2)}

Look at the screenshot and determine which candidate is the REAL form submit button.

Consider:
1. Is it visible and clickable?
2. Is it positioned near form fields?
3. Does its text clearly indicate submission (e.g., "Submit", "Register", "Send")?
4. Is it a button/input element (not just styled text)?
5. Is it in the viewport (not a floating back-to-top button)?

Return JSON with:
{{
    "correct_index": <index of the real submit button>,
    "reasoning": "<brief explanation>",
    "confidence": <0.0 to 1.0>
}}
"""

        try:
            response = ai_client.client.messages.create(
                model=ai_client.models["balanced"],
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }],
                temperature=0.1,
                max_tokens=500
            )

            cost_tracker.track_call(
                model=ai_client.models["balanced"],
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                agent_name=self.name
            )

            result_text = response.content[0].text.strip()
            # Extract JSON from markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)

            if result.get("confidence", 0) > 0.6:
                correct_button = possible_buttons[result["correct_index"]]
                logger.info(f"   ✅ Claude identified: '{correct_button.get('text')}' (confidence: {result['confidence']:.2f})")
                logger.info(f"   💡 Reasoning: {result['reasoning']}")
                return correct_button.get("selector")
            else:
                logger.warning(f"   ⚠️ Low confidence ({result['confidence']:.2f}), using fallback")
                return None

        except Exception as e:
            logger.error(f"Button disambiguation failed: {e}")
            return None

    async def _extract_event_listeners(self, page: Page) -> Dict[str, Any]:
        """
        Extract event listeners from form fields
        Returns which fields have blur, focus, input, change handlers
        """
        try:
            event_map = await page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('input, select, textarea, button');
                    const eventMap = {};

                    elements.forEach(el => {
                        const id = el.id || el.name || el.className || 'unknown';

                        // Check for inline event handlers
                        const hasOnBlur = !!el.onblur || el.hasAttribute('onblur');
                        const hasOnFocus = !!el.onfocus || el.hasAttribute('onfocus');
                        const hasOnChange = !!el.onchange || el.hasAttribute('onchange');
                        const hasOnInput = !!el.oninput || el.hasAttribute('oninput');

                        // Check for jQuery event handlers (if jQuery exists)
                        let hasJQueryEvents = false;
                        if (typeof $ !== 'undefined' && $.data) {
                            const events = $._data(el, 'events');
                            if (events) {
                                hasJQueryEvents = true;
                            }
                        }

                        if (hasOnBlur || hasOnFocus || hasOnChange || hasOnInput || hasJQueryEvents) {
                            eventMap[id] = {
                                element: el.tagName.toLowerCase(),
                                id: el.id,
                                name: el.name,
                                class: el.className,
                                listeners: {
                                    blur: hasOnBlur,
                                    focus: hasOnFocus,
                                    change: hasOnChange,
                                    input: hasOnInput,
                                    jquery: hasJQueryEvents
                                },
                                // Check if element is part of validation
                                required: el.required || el.hasAttribute('required'),
                                pattern: el.pattern || null
                            };
                        }
                    });

                    return eventMap;
                }
            """)

            return event_map

        except Exception as e:
            logger.warning(f"Failed to extract event listeners: {e}")
            return {}

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

            # Enhanced submit button detection
            submit_selector = schema.submit_button.get("selector", "")
            if not submit_selector:
                # Try to find submit buttons
                possible_buttons = await page.evaluate("""
                    () => {
                        const buttons = [];
                        const selectors = [
                            'button[type="submit"]',
                            'input[type="submit"]',
                            'button:not([type="button"])',
                            '.btn-primary',
                            'button.submit',
                            '*[onclick*="submit"]'
                        ];

                        selectors.forEach(sel => {
                            document.querySelectorAll(sel).forEach((btn, idx) => {
                                const rect = btn.getBoundingClientRect();
                                buttons.push({
                                    text: btn.textContent?.trim() || btn.value || '',
                                    type: btn.tagName,
                                    selector: sel + ':nth-of-type(' + (idx + 1) + ')',
                                    class: btn.className,
                                    visible: rect.width > 0 && rect.height > 0,
                                    in_viewport: rect.top >= 0 && rect.bottom <= window.innerHeight
                                });
                            });
                        });

                        return buttons;
                    }
                """)

                if len(possible_buttons) > 1:
                    # Use Claude to disambiguate
                    submit_selector = await self._disambiguate_submit_button_with_claude(page, possible_buttons)
                elif len(possible_buttons) == 1:
                    submit_selector = possible_buttons[0].get("selector")

                if submit_selector:
                    schema.submit_button["selector"] = submit_selector

            # Try to submit empty form
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
