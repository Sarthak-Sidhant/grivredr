#!/usr/bin/env python3
"""
Hybrid Form Discovery - Browser-use AI brain + Playwright tools

The AI decides WHAT to do, Playwright tools do the heavy lifting efficiently.
This combines the intelligence of browser-use with the speed of Playwright.
"""
import asyncio
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Any
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, Browser as PWBrowser
import anthropic

load_dotenv()


class CostTracker:
    """Track API costs"""
    PRICING = {
        "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
        "claude-opus-4-5-20250929": {"input": 15.0, "output": 75.0},
    }

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.calls = 0

    def add(self, model: str, input_tokens: int, output_tokens: int):
        pricing = self.PRICING.get(model, {"input": 3.0, "output": 15.0})
        cost = (input_tokens * pricing["input"] / 1_000_000) + \
               (output_tokens * pricing["output"] / 1_000_000)
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
        self.calls += 1
        return cost


class PlaywrightTools:
    """
    Playwright-based tools that the AI can call.
    These are FAST and FREE (no AI tokens).
    """

    def __init__(self, page: Page):
        self.page = page

    async def get_all_form_fields(self) -> dict:
        """Extract all form fields from the page - ONE call gets everything"""
        js_code = """
        () => {
            const fields = [];

            // Get all inputs, textareas, selects
            document.querySelectorAll('input, textarea, select').forEach(el => {
                if (el.type === 'hidden' || el.type === 'submit' || el.type === 'button') return;

                // Find label
                let label = '';
                if (el.id) {
                    const labelEl = document.querySelector(`label[for="${el.id}"]`);
                    if (labelEl) label = labelEl.textContent.trim();
                }
                if (!label) label = el.placeholder || el.getAttribute('aria-label') || el.name || el.id || '';

                // Determine type
                let fieldType = el.tagName.toLowerCase();
                if (el.tagName === 'INPUT') {
                    if (el.getAttribute('role') === 'combobox') fieldType = 'searchable_select';
                    else fieldType = el.type || 'text';
                }

                // Check if it's an ant-design select
                const antSelect = el.closest('.ant-select');
                if (antSelect) fieldType = 'ant_select';

                fields.push({
                    id: el.id || null,
                    name: el.name || null,
                    label: label,
                    type: fieldType,
                    selector: el.id ? '#' + el.id : (el.name ? `[name="${el.name}"]` : null),
                    required: el.required || el.getAttribute('aria-required') === 'true',
                    readonly: el.hasAttribute('readonly'),
                    placeholder: el.placeholder || '',
                    value: el.value || '',
                    visible: el.offsetParent !== null
                });
            });

            return {
                url: window.location.href,
                title: document.title,
                fields: fields,
                field_count: fields.length
            };
        }
        """
        return await self.page.evaluate(js_code)

    async def get_dropdown_options(self, selector: str) -> dict:
        """Click a dropdown and extract ALL its options - handles Ant-Design and Select2"""
        try:
            # Find the element
            element = self.page.locator(selector).first
            await element.scroll_into_view_if_needed()

            options = []
            framework = "unknown"
            is_searchable = False

            # Check for Select2 container (common in ASP.NET forms like Smart Ranchi)
            select2_container = self.page.locator(f".select2-container[id*='{selector.replace('#', '').replace('[', '').replace(']', '')}'], .select2-container").first

            # Try to detect which framework
            has_select2 = await self.page.locator(".select2-container").count() > 0
            has_ant = await self.page.locator(".ant-select").count() > 0

            if has_select2 and not has_ant:
                # === SELECT2 HANDLING ===
                framework = "select2"

                # Find the Select2 container for this field
                # Select2 creates a container next to the original select element
                try:
                    # Click the Select2 container to open dropdown
                    s2_choice = self.page.locator(f"{selector} + .select2-container .select2-choice, {selector} ~ .select2-container .select2-choice, .select2-container .select2-choice").first
                    if await s2_choice.count() > 0:
                        await s2_choice.click(force=True)
                    else:
                        # Try clicking the container directly
                        await self.page.locator(".select2-container").first.click(force=True)

                    await asyncio.sleep(1.0)  # Select2 needs more time

                    # Check if dropdown opened
                    dropdown_visible = await self.page.locator(".select2-drop, .select2-dropdown").first.is_visible()

                    if dropdown_visible:
                        # Extract Select2 options
                        option_elements = self.page.locator(".select2-results li, .select2-results .select2-result-selectable")
                        count = await option_elements.count()

                        for i in range(min(count, 100)):
                            try:
                                opt = option_elements.nth(i)
                                if await opt.is_visible():
                                    text = await opt.text_content()
                                    if text and text.strip():
                                        # Get data-value if available
                                        value = await opt.get_attribute("data-value") or await opt.get_attribute("id") or text
                                        options.append({"text": text.strip(), "value": str(value).strip()})
                            except:
                                pass

                        is_searchable = await self.page.locator(".select2-search input").count() > 0

                    # Close dropdown
                    await self.page.keyboard.press("Escape")
                    await asyncio.sleep(0.3)

                except Exception as e:
                    # Fallback: try to get options directly from the hidden select
                    try:
                        select_options = self.page.locator(f"{selector} option")
                        count = await select_options.count()
                        for i in range(min(count, 100)):
                            opt = select_options.nth(i)
                            text = await opt.text_content()
                            value = await opt.get_attribute("value") or text
                            if text and text.strip():
                                options.append({"text": text.strip(), "value": str(value).strip()})
                    except:
                        pass

            else:
                # === ANT-DESIGN HANDLING (default) ===
                framework = "ant_design"

                # Find parent ant-select wrapper and click it
                wrapper = element.locator("xpath=ancestor::div[contains(@class,'ant-select')]").first
                await wrapper.click(force=True)
                await asyncio.sleep(0.8)

                # Check if dropdown opened
                dropdown_visible = await self.page.locator(".ant-select-dropdown").first.is_visible()

                if dropdown_visible:
                    # Extract all options
                    option_elements = self.page.locator(".ant-select-item-option")
                    count = await option_elements.count()

                    for i in range(min(count, 100)):  # Limit to 100 options
                        try:
                            opt = option_elements.nth(i)
                            if await opt.is_visible():
                                text = await opt.text_content()
                                value = await opt.get_attribute("data-value") or text
                                options.append({"text": text.strip(), "value": str(value).strip()})
                        except:
                            pass

                # Close dropdown
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)

                # Check if field is readonly (non-searchable)
                is_searchable = await element.get_attribute("readonly") is None

            return {
                "selector": selector,
                "framework": framework,
                "is_searchable": is_searchable,
                "option_count": len(options),
                "options": options
            }

        except Exception as e:
            return {"selector": selector, "error": str(e), "options": []}

    async def select_dropdown_option(self, selector: str, value: str) -> dict:
        """Select a specific option from a dropdown - handles Ant-Design and Select2"""
        try:
            element = self.page.locator(selector).first
            await element.scroll_into_view_if_needed()

            # Detect framework
            has_select2 = await self.page.locator(".select2-container").count() > 0
            has_ant = await self.page.locator(".ant-select").count() > 0

            if has_select2 and not has_ant:
                # === SELECT2 HANDLING ===
                # Click Select2 container to open
                s2_choice = self.page.locator(f"{selector} + .select2-container .select2-choice, .select2-container .select2-choice").first
                if await s2_choice.count() > 0:
                    await s2_choice.click(force=True)
                else:
                    await self.page.locator(".select2-container").first.click(force=True)

                await asyncio.sleep(1.0)

                # Type in search if available
                search_input = self.page.locator(".select2-search input, .select2-input")
                if await search_input.count() > 0 and value:
                    await search_input.fill(value)
                    await asyncio.sleep(0.8)

                # Find and click matching option
                options = self.page.locator(".select2-results li, .select2-result-selectable")
                count = await options.count()

                for i in range(count):
                    opt = options.nth(i)
                    if await opt.is_visible():
                        text = await opt.text_content()
                        if text and (not value or value.lower() in text.lower()):
                            await opt.click()
                            await asyncio.sleep(0.5)
                            return {"success": True, "selected": text.strip(), "framework": "select2"}

                # Fallback: first visible option
                for i in range(count):
                    opt = options.nth(i)
                    if await opt.is_visible():
                        text = await opt.text_content()
                        if text and text.strip():
                            await opt.click()
                            await asyncio.sleep(0.5)
                            return {"success": True, "selected": text.strip(), "fallback": True, "framework": "select2"}

                await self.page.keyboard.press("Escape")
                return {"success": False, "error": "No matching option found", "framework": "select2"}

            else:
                # === ANT-DESIGN HANDLING ===
                # Click to open
                wrapper = element.locator("xpath=ancestor::div[contains(@class,'ant-select')]").first
                await wrapper.click(force=True)
                await asyncio.sleep(0.5)

                # Check if searchable
                is_readonly = await element.get_attribute("readonly") is not None

                if not is_readonly and value:
                    # Type to search
                    await element.fill(value)
                    await asyncio.sleep(0.8)

                # Find and click matching option
                options = self.page.locator(".ant-select-item-option")
                count = await options.count()

                for i in range(count):
                    opt = options.nth(i)
                    if await opt.is_visible():
                        text = await opt.text_content()
                        if not value or value.lower() in text.lower():
                            await opt.click()
                            return {"success": True, "selected": text.strip(), "framework": "ant_design"}

                # Fallback: select first option
                first = self.page.locator(".ant-select-item-option").first
                if await first.is_visible():
                    text = await first.text_content()
                    await first.click()
                    return {"success": True, "selected": text.strip(), "fallback": True, "framework": "ant_design"}

                return {"success": False, "error": "No matching option found", "framework": "ant_design"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_network_requests(self) -> list:
        """Get recent API/XHR requests - useful for understanding cascading dropdowns"""
        js_code = """
        () => {
            // This only works if we set up network interception beforehand
            return window.__networkRequests || [];
        }
        """
        return await self.page.evaluate(js_code)

    async def check_cascading_dependency(self, parent_selector: str, child_selector: str) -> dict:
        """Check if selecting parent affects child dropdown options"""
        try:
            # Get child options BEFORE selecting parent
            child_before = await self.get_dropdown_options(child_selector)
            before_count = child_before.get("option_count", 0)

            # Select first option in parent
            parent_result = await self.select_dropdown_option(parent_selector, "")

            await asyncio.sleep(1)  # Wait for cascade

            # Get child options AFTER
            child_after = await self.get_dropdown_options(child_selector)
            after_count = child_after.get("option_count", 0)

            return {
                "parent": parent_selector,
                "child": child_selector,
                "is_cascading": before_count != after_count or before_count == 0,
                "parent_selected": parent_result.get("selected"),
                "child_options_before": before_count,
                "child_options_after": after_count,
                "child_options": child_after.get("options", [])[:10]  # First 10
            }

        except Exception as e:
            return {"error": str(e)}


class HybridFormDiscovery:
    """
    Hybrid discovery: AI brain + Playwright muscle.

    The AI orchestrates, Playwright executes.
    """

    def __init__(self, output_dir: str = "scrapers"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.api_key = os.getenv("api_key")
        self.cost_tracker = CostTracker()
        self.client = anthropic.Anthropic(
            api_key=self.api_key,
            base_url="https://ai.megallm.io"
        )

    def _build_tools(self):
        """Define tools the AI can call"""
        return [
            {
                "name": "get_all_form_fields",
                "description": "Extract all form fields from the current page. Returns field IDs, types, labels, selectors, and whether they're required. Call this FIRST to understand the form structure.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_dropdown_options",
                "description": "Click on a dropdown field and extract all available options. Use this for select/dropdown fields to understand what values are available.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "CSS selector for the dropdown field (e.g., '#category_id')"
                        }
                    },
                    "required": ["selector"]
                }
            },
            {
                "name": "select_dropdown_option",
                "description": "Select a specific option from a dropdown. Use this to test cascading dropdowns - select a parent value to see how it affects child dropdowns.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "CSS selector for the dropdown"
                        },
                        "value": {
                            "type": "string",
                            "description": "Value or partial text to search for and select"
                        }
                    },
                    "required": ["selector", "value"]
                }
            },
            {
                "name": "check_cascading_dependency",
                "description": "Check if two dropdowns have a parent-child cascading relationship. Selects an option in the parent and observes if child options change.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "parent_selector": {
                            "type": "string",
                            "description": "CSS selector for the parent dropdown"
                        },
                        "child_selector": {
                            "type": "string",
                            "description": "CSS selector for the child dropdown"
                        }
                    },
                    "required": ["parent_selector", "child_selector"]
                }
            },
            {
                "name": "complete_discovery",
                "description": "Call this when you have fully analyzed the form and are ready to provide the complete form structure. Include all fields, their types, selectors, options, and any cascading relationships.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "form_structure": {
                            "type": "object",
                            "description": "Complete form structure with all fields, options, and relationships"
                        }
                    },
                    "required": ["form_structure"]
                }
            }
        ]

    async def discover(self, url: str, headless: bool = True) -> dict:
        """Run hybrid discovery on a form"""

        print(f"\n{'='*60}")
        print("Hybrid Form Discovery")
        print(f"{'='*60}")
        print(f"URL: {url[:60]}...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            # Navigate
            print("\n[1] Loading page...")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Create tools
            tools = PlaywrightTools(page)

            # Run AI agent with tools
            print("[2] AI analyzing form with Playwright tools...")
            form_structure = await self._run_agent(tools)

            await browser.close()

        print(f"\n[3] Discovery complete!")
        print(f"    Total AI calls: {self.cost_tracker.calls}")
        print(f"    Total cost: ${self.cost_tracker.total_cost:.4f}")

        return form_structure

    async def _run_agent(self, tools: PlaywrightTools) -> dict:
        """Run the AI agent with tool access"""

        system_prompt = """You are a form analysis expert. Analyze the web form using available tools.

STRATEGY:
1. Call get_all_form_fields ONCE to get overview of all fields
2. For EVERY dropdown/select field (including Select2 and ant-design), call get_dropdown_options to get ALL available options
3. For cascading dropdowns: select a parent option, wait, then get child options
4. Call complete_discovery with full structure including ALL options and sample_data with REAL values

CRITICAL REQUIREMENTS:
- You MUST call get_dropdown_options for EVERY select/dropdown field - Problem, Area, Ward, Category, Zone, etc.
- The tool handles both Select2 (jQuery) and Ant-Design dropdowns automatically
- DO NOT skip any dropdown field - ALL dropdown options must be captured
- DO NOT put empty options arrays - fetch the real options using the tool!
- Include sample_data with ACTUAL values that exist in the dropdowns

DROPDOWN CONTEXT IS CRITICAL:
- For each dropdown, include ALL options in the "options" array with their text values
- This data will be saved to context files for the scraper to use
- The scraper NEEDS this data to know what values are valid

OUTPUT STRUCTURE for complete_discovery:
{
  "form_url": "url",
  "form_title": "title",
  "ui_framework": "select2|ant_design|native",
  "fields": [
    {"name": "Field Name", "type": "select|searchable_select|text|textarea|file", "selector": "#id", "required": true, "visible": true, "searchable": true, "options": ["REAL_OPT1", "REAL_OPT2", "REAL_OPT3", ...], "cascades_to": "child_field_name"}
  ],
  "dropdown_context": {
    "field_name": {"selector": "#selector", "options": {"Option Text": "option_value", ...}}
  },
  "cascading_relationships": [{"parent": "#parent_id", "child": "#child_id", "parent_field": "field_name", "child_field": "child_field_name"}],
  "submit_button": "selector",
  "sample_data": {
    "problem": "ActualProblemFromOptions",
    "area": "ActualAreaFromOptions",
    "category": "ActualCategoryFromOptions",
    "zone": "ActualZoneFromOptions"
  }
}

WORKFLOW:
1. get_all_form_fields - understand structure, identify all dropdowns
2. For EACH dropdown field found:
   - Call get_dropdown_options with the field's selector
   - Record ALL options returned (text and value)
3. For cascading dropdowns (where selecting parent loads child options):
   - select_dropdown_option on parent with first available value
   - Wait, then get_dropdown_options on child
4. Call complete_discovery with:
   - ALL fields including their options
   - dropdown_context with full option mappings
   - sample_data with real values from options

IMPORTANT: Do not stop until you have fetched options from ALL dropdown fields. Each dropdown must have its options populated."""

        messages = [{"role": "user", "content": "Analyze this form completely. Follow the WORKFLOW exactly - get fields, get dropdown options, select parents to load children, then call complete_discovery. Do NOT over-explore."}]

        max_iterations = 20
        form_structure = None

        for i in range(max_iterations):
            print(f"    AI call {i+1}...", end=" ")

            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                system=system_prompt,
                tools=self._build_tools(),
                messages=messages
            )

            cost = self.cost_tracker.add(
                "claude-sonnet-4-5-20250929",
                response.usage.input_tokens,
                response.usage.output_tokens
            )
            print(f"${cost:.4f}")

            # Process response
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            # Check for tool use
            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    print(f"      -> {tool_name}({json.dumps(tool_input)[:50]}...)")

                    # Execute tool
                    if tool_name == "get_all_form_fields":
                        result = await tools.get_all_form_fields()
                    elif tool_name == "get_dropdown_options":
                        result = await tools.get_dropdown_options(tool_input["selector"])
                    elif tool_name == "select_dropdown_option":
                        result = await tools.select_dropdown_option(
                            tool_input["selector"],
                            tool_input["value"]
                        )
                    elif tool_name == "check_cascading_dependency":
                        result = await tools.check_cascading_dependency(
                            tool_input["parent_selector"],
                            tool_input["child_selector"]
                        )
                    elif tool_name == "complete_discovery":
                        form_structure = tool_input["form_structure"]
                        print("      -> Discovery complete!")
                        return form_structure
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            elif response.stop_reason == "end_turn":
                # AI finished without calling complete_discovery
                print("      -> AI ended without complete_discovery")
                break

        return form_structure or {"error": "Discovery did not complete"}

    def generate_scraper(self, form_structure: dict, portal_name: str) -> str:
        """Generate Playwright scraper from discovered structure using pattern library"""

        print("\n[4] Generating scraper code...")

        # Try to get templates from pattern library
        templates_section = ""
        try:
            from knowledge.pattern_library import PatternLibrary
            pl = PatternLibrary(enable_vector_store=False)  # Skip vector store for speed
            template_info = pl.get_templates_for_schema(form_structure)

            if template_info.get("ui_framework") != "unknown":
                print(f"   Detected UI framework: {template_info['ui_framework']}")

            if template_info.get("recommendations"):
                templates_section = "\n**RECOMMENDATIONS FROM PATTERN LIBRARY:**\n"
                for rec in template_info["recommendations"]:
                    templates_section += f"- {rec}\n"

            if template_info.get("cascade_recommendations"):
                templates_section += "\n**CASCADE PATTERNS:**\n"
                for cascade in template_info["cascade_recommendations"]:
                    templates_section += f"- {cascade['parent']} → {cascade['child']}: wait {cascade['wait_time']}s\n"

        except Exception as e:
            print(f"   Note: Pattern library not available ({e})")

        prompt = f"""Generate a production-ready async Playwright Python scraper for this form:
{templates_section}
```json
{json.dumps(form_structure, indent=2)}
```

CRITICAL - Use this EXACT dropdown pattern (tested and working):

```python
async def _fill_searchable_select(self, selector: str, value: str, field_name: str):
    \"\"\"Fill ant-design searchable dropdown - TESTED WORKING PATTERN\"\"\"
    element = self.page.locator(selector)
    await element.scroll_into_view_if_needed()
    await asyncio.sleep(0.3)

    # Click the wrapper (ancestor div with ant-select class) to open dropdown
    wrapper = element.locator("xpath=ancestor::div[contains(@class,'ant-select')]").first
    await wrapper.click(force=True)
    await asyncio.sleep(0.8)  # Wait for dropdown to fully open

    # Find the visible dropdown (there may be multiple hidden ones)
    all_dropdowns = self.page.locator(".ant-select-dropdown")
    dropdown = None
    for i in range(await all_dropdowns.count()):
        dd = all_dropdowns.nth(i)
        if await dd.is_visible():
            dropdown = dd
            break

    if dropdown is None:
        logger.warning(f"{{field_name}}: No visible dropdown found")
        await self.page.keyboard.press("Escape")
        return

    options = dropdown.locator(".ant-select-item-option")
    count = await options.count()
    logger.info(f"{{field_name}}: found {{count}} options in dropdown")

    # Try to find matching option directly (without typing first)
    for i in range(count):
        opt = options.nth(i)
        try:
            text = await opt.text_content()
            if text and value.lower() in text.lower():
                await opt.click()
                logger.info(f"Selected {{field_name}}: {{text}}")
                return
        except:
            continue

    # Fallback: first available option
    if count > 0:
        first = options.first
        text = await first.text_content()
        await first.click()
        logger.info(f"Selected {{field_name}} (fallback): {{text}}")
    else:
        logger.warning(f"{{field_name}}: No options found, closing dropdown")
        await self.page.keyboard.press("Escape")
```

Requirements:
1. Class: `{portal_name.title().replace('_', '')}FormFiller`
2. Use the EXACT dropdown pattern above (it works!)
3. Handle cascading dropdowns - wait 1 second after parent selection before filling child
4. CRITICAL: DO NOT include fields where "visible": false in the JSON structure. These are hidden fields that should NOT be filled. Only generate code for fields where visible is true or not specified.
5. Methods: __init__(headless), start(), fill_form(data: dict), submit(), close(), run(data, submit=False)
6. CRITICAL: Use sample_data from the JSON if available. Use REAL option values from the "options" arrays. DO NOT make up values like "Zone 1" or "Ward 5" - use actual values from the discovered options!
7. Proper error handling and logging
8. For text/textarea fields, check visibility before filling
9. For dropdowns, look in .ant-select-dropdown:visible for options (not all page options)

Generate ONLY the Python code."""

        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        self.cost_tracker.add(
            "claude-sonnet-4-5-20250929",
            response.usage.input_tokens,
            response.usage.output_tokens
        )

        code = response.content[0].text
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]

        return code.strip()

    def save(self, code: str, form_structure: dict, portal_name: str, state: str = "unknown", district: str = "unknown") -> Path:
        """
        Save scraper and metadata using portal manager

        Args:
            code: Generated scraper code
            form_structure: Discovered form structure
            portal_name: Name of the portal
            state: State name (for directory structure)
            district: District name (for directory structure)

        Returns:
            Path to saved scraper
        """
        # Also save to old location for backwards compatibility
        portal_dir = self.output_dir / portal_name
        portal_dir.mkdir(exist_ok=True)

        # Save scraper to old location
        scraper_path = portal_dir / f"{portal_name}_scraper.py"
        with open(scraper_path, 'w') as f:
            f.write(code)

        # Save structure to old location
        with open(portal_dir / f"{portal_name}_structure.json", 'w') as f:
            json.dump(form_structure, f, indent=2)

        # Try to use portal manager for unified structure
        try:
            from utils.portal_manager import PortalManager

            pm = PortalManager()

            # Save to unified structure
            pm.save_scraper(state, district, portal_name, code)
            pm.save_structure(state, district, portal_name, form_structure)

            # Extract and save dropdown context
            dropdowns = {}
            cascades = {}
            field_mappings = {}

            # First check if AI provided dropdown_context directly (preferred)
            if "dropdown_context" in form_structure and form_structure["dropdown_context"]:
                dropdowns = form_structure["dropdown_context"]
                print(f"   Using AI-provided dropdown_context with {len(dropdowns)} dropdowns")

            # Extract cascading relationships if provided
            if "cascading_relationships" in form_structure:
                for rel in form_structure.get("cascading_relationships", []):
                    parent_field = rel.get("parent_field", "parent")
                    child_field = rel.get("child_field", "child")
                    cascades[f"{parent_field}_to_{child_field}"] = {
                        "parent": rel.get("parent", ""),
                        "child": rel.get("child", ""),
                        "parent_field": parent_field,
                        "child_field": child_field
                    }

            # Also extract from fields array
            fields = form_structure.get("fields", [])
            for field in fields:
                field_name = field.get("name", "")
                options = field.get("options", [])

                if options and field.get("type") in ["select", "dropdown", "searchable_select"]:
                    # Build dropdown context with options (if not already in dropdown_context)
                    if field_name not in dropdowns:
                        # Handle both list of strings and list of dicts
                        if options and isinstance(options[0], dict):
                            opt_mapping = {opt.get("text", ""): opt.get("value", opt.get("text", "")) for opt in options}
                        else:
                            opt_mapping = {opt: opt for opt in options}

                        dropdowns[field_name] = {
                            "selector": field.get("selector", ""),
                            "searchable": field.get("searchable", False),
                            "options": opt_mapping
                        }

                    # Track field mappings
                    field_mappings[field_name] = {
                        "selector": field.get("selector", ""),
                        "type": field.get("type", ""),
                        "required": field.get("required", False)
                    }

                # Track cascade relationships from fields
                if field.get("cascades_to"):
                    cascade_key = f"{field_name}_to_{field['cascades_to']}"
                    if cascade_key not in cascades:
                        cascades[cascade_key] = {
                            "parent": field.get("selector", ""),
                            "child": f"#{field['cascades_to']}",  # Assume ID selector
                            "parent_field": field_name,
                            "child_field": field["cascades_to"]
                        }

            # Save context files
            if dropdowns or cascades or field_mappings:
                pm.save_context(
                    state, district, portal_name,
                    dropdowns=dropdowns if dropdowns else None,
                    cascades=cascades if cascades else None,
                    field_mappings=field_mappings if field_mappings else None
                )

            # Save metadata with cost info
            pm.save_metadata(
                state, district, portal_name,
                url=form_structure.get("form_url", ""),
                training_cost=self.cost_tracker.total_cost,
                api_calls=self.cost_tracker.calls,
                input_tokens=self.cost_tracker.total_input_tokens,
                output_tokens=self.cost_tracker.total_output_tokens
            )

            print(f"   Saved to unified structure: portals/{state}/{district}/{portal_name}/")

        except ImportError:
            print("   PortalManager not available, using legacy structure only")
        except Exception as e:
            print(f"   Warning: Could not save to unified structure: {e}")

        # Also save metadata to old location
        with open(portal_dir / "metadata.json", 'w') as f:
            json.dump({
                "portal_name": portal_name,
                "state": state,
                "district": district,
                "generated_at": datetime.now().isoformat(),
                "cost": {
                    "total": self.cost_tracker.total_cost,
                    "calls": self.cost_tracker.calls,
                    "input_tokens": self.cost_tracker.total_input_tokens,
                    "output_tokens": self.cost_tracker.total_output_tokens
                }
            }, f, indent=2)

        return scraper_path

    async def run(
        self,
        url: str,
        portal_name: str,
        headless: bool = True,
        state: str = "unknown",
        district: str = "unknown"
    ) -> Path:
        """
        Full pipeline: discover + generate + save

        Args:
            url: URL of the form to discover
            portal_name: Name identifier for the portal
            headless: Run browser in headless mode
            state: State name for directory structure
            district: District name for directory structure

        Returns:
            Path to generated scraper
        """

        # Discover
        form_structure = await self.discover(url, headless=headless)

        if "error" in form_structure:
            raise Exception(f"Discovery failed: {form_structure['error']}")

        # Generate
        code = self.generate_scraper(form_structure, portal_name)

        # Save with state/district context
        scraper_path = self.save(code, form_structure, portal_name, state=state, district=district)

        print(f"\n{'='*60}")
        print("COMPLETE!")
        print(f"{'='*60}")
        print(f"Scraper: {scraper_path}")
        print(f"Portal: {state}/{district}/{portal_name}")
        print(f"Total cost: ${self.cost_tracker.total_cost:.4f}")
        print(f"AI calls: {self.cost_tracker.calls}")

        return scraper_path


async def main():
    discovery = HybridFormDiscovery()

    url = "https://mcd.everythingcivic.com/citizen/createissue?app_id=U2FsdGVkX180J3mGnJmT5QpgtPjhfjtzyXAAccBUxGU%3D&api_key=e34ba86d3943bd6db9120313da011937189e6a9625170905750f649395bcd68312cf10d264c9305d57c23688cc2e5120"

    scraper_path = await discovery.run(
        url=url,
        portal_name="mcd_delhi_hybrid",
        headless=True
    )

    print(f"\nGenerated: {scraper_path}")


if __name__ == "__main__":
    asyncio.run(main())
