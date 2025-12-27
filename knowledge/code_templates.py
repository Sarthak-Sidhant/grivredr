"""
Code Templates - Proven reusable code patterns for scraper generation

This module contains tested, working code snippets that can be directly
injected into generated scrapers. Organized by:
- UI Framework (ant-design, select2, bootstrap, asp-net)
- Pattern Type (dropdown, cascade, validation, submission)
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class UIFramework(Enum):
    """Detected UI frameworks"""
    ANT_DESIGN = "ant_design"
    SELECT2 = "select2"
    BOOTSTRAP = "bootstrap"
    ASP_NET_WEBFORMS = "asp_net_webforms"
    MATERIAL_UI = "material_ui"
    PLAIN_HTML = "plain_html"
    UNKNOWN = "unknown"


@dataclass
class CodeTemplate:
    """A reusable code template"""
    name: str
    framework: UIFramework
    pattern_type: str  # dropdown, cascade, text_input, file_upload, submit
    code: str
    description: str
    dependencies: List[str]  # Required imports
    tested_on: List[str]  # List of portals where this worked


# =============================================================================
# ANT-DESIGN TEMPLATES (Proven working on MCD Delhi)
# =============================================================================

ANT_DESIGN_SEARCHABLE_SELECT = CodeTemplate(
    name="ant_design_searchable_select",
    framework=UIFramework.ANT_DESIGN,
    pattern_type="dropdown",
    description="Handles ant-design searchable select dropdowns. Opens dropdown, finds visible options, selects by text match.",
    dependencies=["asyncio", "logging"],
    tested_on=["mcd_delhi_hybrid"],
    code='''
async def _fill_searchable_select(self, selector: str, value: str, field_name: str):
    """
    Fill an ant-design searchable select dropdown

    Args:
        selector: CSS selector for the hidden input
        value: Text value to select (will match against option text)
        field_name: Name for logging
    """
    try:
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
            logger.warning(f"{field_name}: No visible dropdown found")
            await self.page.keyboard.press("Escape")
            return

        options = dropdown.locator(".ant-select-item-option")
        count = await options.count()
        logger.info(f"{field_name}: found {count} options in dropdown")

        # Try to find matching option directly (without typing first)
        for i in range(count):
            opt = options.nth(i)
            try:
                text = await opt.text_content()
                if text and value.lower() in text.lower():
                    await opt.click()
                    logger.info(f"Selected {field_name}: {text}")
                    return
            except:
                continue

        # Fallback: first available option
        if count > 0:
            first = options.first
            text = await first.text_content()
            await first.click()
            logger.info(f"Selected {field_name} (fallback): {text}")
        else:
            logger.warning(f"{field_name}: No options found, closing dropdown")
            await self.page.keyboard.press("Escape")

    except Exception as e:
        logger.error(f"Failed to fill {field_name}: {e}")
        raise
'''
)

ANT_DESIGN_READONLY_SELECT = CodeTemplate(
    name="ant_design_readonly_select",
    framework=UIFramework.ANT_DESIGN,
    pattern_type="dropdown",
    description="Handles ant-design readonly (non-searchable) select dropdowns.",
    dependencies=["asyncio", "logging"],
    tested_on=["mcd_delhi_hybrid"],
    code='''
async def _fill_readonly_select(self, selector: str, value: str, field_name: str):
    """
    Fill an ant-design readonly select dropdown (no search capability)

    Args:
        selector: CSS selector for the select element
        value: Text value to select
        field_name: Name for logging
    """
    try:
        element = self.page.locator(selector)
        await element.scroll_into_view_if_needed()

        # Click to open dropdown
        wrapper = element.locator("xpath=ancestor::div[contains(@class,'ant-select')]").first
        await wrapper.click(force=True)
        await asyncio.sleep(0.8)

        # Find visible dropdown
        all_dropdowns = self.page.locator(".ant-select-dropdown")
        dropdown = None
        for i in range(await all_dropdowns.count()):
            dd = all_dropdowns.nth(i)
            if await dd.is_visible():
                dropdown = dd
                break

        if not dropdown:
            logger.warning(f"{field_name}: No dropdown appeared")
            return

        # Click matching option
        options = dropdown.locator(".ant-select-item-option")
        count = await options.count()

        for i in range(count):
            opt = options.nth(i)
            text = await opt.text_content()
            if text and value.lower() in text.lower():
                await opt.click()
                logger.info(f"Selected {field_name}: {text}")
                return

        # Fallback to first option
        if count > 0:
            first = options.first
            text = await first.text_content()
            await first.click()
            logger.info(f"Selected {field_name} (fallback): {text}")

    except Exception as e:
        logger.error(f"Failed to fill {field_name}: {e}")
        raise
'''
)

ANT_DESIGN_CASCADE = CodeTemplate(
    name="ant_design_cascade",
    framework=UIFramework.ANT_DESIGN,
    pattern_type="cascade",
    description="Handles cascading ant-design dropdowns where child options load after parent selection.",
    dependencies=["asyncio", "logging"],
    tested_on=["mcd_delhi_hybrid"],
    code='''
async def _fill_cascading_dropdown(
    self,
    parent_selector: str,
    parent_value: str,
    child_selector: str,
    child_value: str,
    parent_name: str = "Parent",
    child_name: str = "Child",
    wait_time: float = 1.5
):
    """
    Fill cascading ant-design dropdowns

    Args:
        parent_selector: CSS selector for parent dropdown
        parent_value: Value to select in parent
        child_selector: CSS selector for child dropdown
        child_value: Value to select in child
        parent_name: Name for logging
        child_name: Name for logging
        wait_time: Time to wait for child options to load after parent selection
    """
    # Fill parent dropdown
    await self._fill_searchable_select(parent_selector, parent_value, parent_name)

    # Wait for child dropdown to populate
    logger.info(f"Waiting {wait_time}s for {child_name} to load...")
    await asyncio.sleep(wait_time)

    # Fill child dropdown
    await self._fill_searchable_select(child_selector, child_value, child_name)
'''
)


# =============================================================================
# SELECT2 TEMPLATES (jQuery-based dropdowns)
# =============================================================================

SELECT2_DROPDOWN = CodeTemplate(
    name="select2_dropdown",
    framework=UIFramework.SELECT2,
    pattern_type="dropdown",
    description="Handles Select2 jQuery dropdowns using JavaScript evaluation.",
    dependencies=["asyncio", "logging"],
    tested_on=["ranchi_smart"],
    code='''
async def _fill_select2_dropdown(self, selector: str, value: str, field_name: str, wait_after: float = 1.5):
    """
    Fill a Select2 jQuery dropdown

    IMPORTANT: Regular Playwright select_option() will NOT work with Select2!
    Must use jQuery to set value and trigger change event.

    Args:
        selector: CSS selector (e.g., "#field_id")
        value: The option VALUE (not text) to select
        field_name: Name for logging
        wait_after: Time to wait after selection (for cascading)
    """
    try:
        # Use jQuery to set value and trigger change
        js_code = """
            (args) => {
                const select = document.querySelector(args.selector);
                if (select && typeof $ !== 'undefined') {
                    $(select).val(args.value);
                    $(select).trigger('change');
                    return true;
                }
                return false;
            }
        """

        result = await self.page.evaluate(js_code, {"selector": selector, "value": value})

        if result:
            logger.info(f"Selected {field_name}: {value}")
            await asyncio.sleep(wait_after)  # Wait for cascading
            return True
        else:
            logger.warning(f"{field_name}: Select2 selection failed")
            return False

    except Exception as e:
        logger.error(f"Select2 error for {field_name}: {e}")
        return False
'''
)

SELECT2_SEARCHABLE = CodeTemplate(
    name="select2_searchable",
    framework=UIFramework.SELECT2,
    pattern_type="dropdown",
    description="Handles Select2 searchable dropdowns by typing to filter.",
    dependencies=["asyncio", "logging"],
    tested_on=["ranchi_smart"],
    code='''
async def _fill_select2_searchable(self, selector: str, search_text: str, field_name: str):
    """
    Fill a Select2 searchable dropdown by typing to filter

    Args:
        selector: CSS selector for the hidden select
        search_text: Text to type in search field
        field_name: Name for logging
    """
    try:
        # Click Select2 container to open
        container = self.page.locator(f"span.select2-container").filter(
            has=self.page.locator(selector)
        ).first

        # If container not found, try by ID
        if await container.count() == 0:
            select_id = selector.lstrip("#")
            container = self.page.locator(f"#{select_id}_container, span[data-select2-id='{select_id}']").first

        await container.click()
        await asyncio.sleep(0.5)

        # Type in search field
        search_input = self.page.locator(".select2-search__field, .select2-search input")
        await search_input.fill(search_text)
        await asyncio.sleep(0.8)

        # Click first matching result
        result = self.page.locator(".select2-results__option--highlighted, .select2-results li:first-child")
        if await result.count() > 0:
            await result.first.click()
            logger.info(f"Selected {field_name}: {search_text}")
        else:
            logger.warning(f"{field_name}: No search results for '{search_text}'")
            await self.page.keyboard.press("Escape")

    except Exception as e:
        logger.error(f"Select2 search error for {field_name}: {e}")
'''
)


# =============================================================================
# ASP.NET WEBFORMS TEMPLATES
# =============================================================================

ASP_NET_DROPDOWN = CodeTemplate(
    name="asp_net_dropdown",
    framework=UIFramework.ASP_NET_WEBFORMS,
    pattern_type="dropdown",
    description="Handles standard ASP.NET DropDownList controls.",
    dependencies=["asyncio", "logging"],
    tested_on=["ranchi_smart"],
    code='''
async def _fill_asp_net_dropdown(self, selector: str, value: str, field_name: str):
    """
    Fill an ASP.NET DropDownList

    ASP.NET uses standard <select> elements, but may have __doPostBack for cascading.

    Args:
        selector: CSS selector (often #ctl00_ContentPlaceHolder1_ddlField)
        value: Value attribute of option to select
        field_name: Name for logging
    """
    try:
        # Try by value first
        try:
            await self.page.select_option(selector, value=value)
            logger.info(f"Selected {field_name} by value: {value}")
            return
        except:
            pass

        # Try by label
        try:
            await self.page.select_option(selector, label=value)
            logger.info(f"Selected {field_name} by label: {value}")
            return
        except:
            pass

        # Fallback: click option directly
        option = self.page.locator(f"{selector} option").filter(has_text=value).first
        if await option.count() > 0:
            option_value = await option.get_attribute("value")
            await self.page.select_option(selector, value=option_value)
            logger.info(f"Selected {field_name}: {value}")
        else:
            logger.warning(f"{field_name}: Option '{value}' not found")

    except Exception as e:
        logger.error(f"ASP.NET dropdown error for {field_name}: {e}")
'''
)

ASP_NET_VIEWSTATE = CodeTemplate(
    name="asp_net_viewstate",
    framework=UIFramework.ASP_NET_WEBFORMS,
    pattern_type="submission",
    description="Extracts and includes __VIEWSTATE and __EVENTVALIDATION for ASP.NET forms.",
    dependencies=["asyncio", "logging"],
    tested_on=["ranchi_smart"],
    code='''
async def _get_asp_net_hidden_fields(self) -> Dict[str, str]:
    """
    Extract ASP.NET hidden fields required for form submission

    Returns:
        Dictionary with __VIEWSTATE, __VIEWSTATEGENERATOR, __EVENTVALIDATION, etc.
    """
    hidden_fields = {}

    asp_fields = [
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
        "__EVENTVALIDATION",
        "__EVENTTARGET",
        "__EVENTARGUMENT"
    ]

    for field in asp_fields:
        try:
            element = self.page.locator(f"input[name='{field}']")
            if await element.count() > 0:
                value = await element.get_attribute("value")
                hidden_fields[field] = value or ""
        except:
            pass

    logger.info(f"Extracted {len(hidden_fields)} ASP.NET hidden fields")
    return hidden_fields
'''
)


# =============================================================================
# COMMON PATTERNS (Framework-independent)
# =============================================================================

TEXT_INPUT_WITH_VALIDATION = CodeTemplate(
    name="text_input_with_validation",
    framework=UIFramework.PLAIN_HTML,
    pattern_type="text_input",
    description="Fills text input with proper focus/blur events to trigger validation.",
    dependencies=["asyncio", "logging"],
    tested_on=["mcd_delhi_hybrid", "ranchi_smart"],
    code='''
async def _fill_text_with_validation(self, selector: str, value: str, field_name: str):
    """
    Fill a text input that has validation on blur

    Args:
        selector: CSS selector
        value: Text to fill
        field_name: Name for logging
    """
    try:
        element = self.page.locator(selector)

        # Check visibility
        if not await element.is_visible():
            logger.warning(f"{field_name}: Element not visible, skipping")
            return

        await element.scroll_into_view_if_needed()

        # Focus first
        await element.focus()
        await asyncio.sleep(0.1)

        # Clear and fill
        await element.fill("")  # Clear first
        await element.fill(value)

        # Trigger blur to fire validation
        await element.blur()
        await asyncio.sleep(0.3)  # Wait for validation

        logger.info(f"Filled {field_name}: {value[:20]}...")

    except Exception as e:
        logger.error(f"Failed to fill {field_name}: {e}")
'''
)

FILE_UPLOAD = CodeTemplate(
    name="file_upload",
    framework=UIFramework.PLAIN_HTML,
    pattern_type="file_upload",
    description="Handles file upload inputs.",
    dependencies=["asyncio", "logging", "Path"],
    tested_on=["ranchi_smart"],
    code='''
async def _upload_file(self, selector: str, file_path: str, field_name: str):
    """
    Upload a file to a file input

    Args:
        selector: CSS selector for file input
        file_path: Path to file to upload
        field_name: Name for logging
    """
    try:
        from pathlib import Path

        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"{field_name}: File not found: {file_path}")
            return False

        # Set file input
        await self.page.set_input_files(selector, str(file_path))
        logger.info(f"Uploaded {field_name}: {file_path.name}")
        return True

    except Exception as e:
        logger.error(f"File upload error for {field_name}: {e}")
        return False
'''
)

RETRY_WITH_BACKOFF = CodeTemplate(
    name="retry_with_backoff",
    framework=UIFramework.PLAIN_HTML,
    pattern_type="utility",
    description="Retry decorator with exponential backoff for flaky operations.",
    dependencies=["asyncio", "logging", "functools"],
    tested_on=["mcd_delhi_hybrid", "ranchi_smart"],
    code='''
import functools

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """
    Decorator for retrying async functions with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (doubles each retry)
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"{func.__name__} failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")

            raise last_exception
        return wrapper
    return decorator
'''
)


# =============================================================================
# TEMPLATE REGISTRY
# =============================================================================

# All templates indexed by framework and type
TEMPLATE_REGISTRY: Dict[UIFramework, Dict[str, CodeTemplate]] = {
    UIFramework.ANT_DESIGN: {
        "searchable_select": ANT_DESIGN_SEARCHABLE_SELECT,
        "readonly_select": ANT_DESIGN_READONLY_SELECT,
        "cascade": ANT_DESIGN_CASCADE,
    },
    UIFramework.SELECT2: {
        "dropdown": SELECT2_DROPDOWN,
        "searchable": SELECT2_SEARCHABLE,
    },
    UIFramework.ASP_NET_WEBFORMS: {
        "dropdown": ASP_NET_DROPDOWN,
        "viewstate": ASP_NET_VIEWSTATE,
    },
    UIFramework.PLAIN_HTML: {
        "text_input": TEXT_INPUT_WITH_VALIDATION,
        "file_upload": FILE_UPLOAD,
        "retry": RETRY_WITH_BACKOFF,
    },
}


def get_templates_for_framework(framework: UIFramework) -> Dict[str, CodeTemplate]:
    """Get all templates for a specific UI framework"""
    return TEMPLATE_REGISTRY.get(framework, {})


def get_template(framework: UIFramework, pattern_type: str) -> Optional[CodeTemplate]:
    """Get a specific template by framework and type"""
    framework_templates = TEMPLATE_REGISTRY.get(framework, {})
    return framework_templates.get(pattern_type)


def get_all_dropdown_templates() -> List[CodeTemplate]:
    """Get all dropdown-related templates across frameworks"""
    templates = []
    for framework_templates in TEMPLATE_REGISTRY.values():
        for template in framework_templates.values():
            if template.pattern_type in ["dropdown", "cascade"]:
                templates.append(template)
    return templates


def get_template_code_for_prompt(framework: UIFramework) -> str:
    """
    Get formatted template code for inclusion in AI prompts

    Returns code templates as formatted string for prompt injection
    """
    templates = get_templates_for_framework(framework)
    if not templates:
        return ""

    lines = [f"\n**PROVEN CODE TEMPLATES FOR {framework.value.upper()}:**\n"]

    for name, template in templates.items():
        lines.append(f"### {template.name}")
        lines.append(f"# {template.description}")
        lines.append(f"# Tested on: {', '.join(template.tested_on)}")
        lines.append("```python")
        lines.append(template.code.strip())
        lines.append("```\n")

    return "\n".join(lines)


# =============================================================================
# CASCADE PATTERN TEMPLATES
# =============================================================================

# Common cascade patterns seen in Indian government portals
CASCADE_PATTERNS = {
    "zone_ward": {
        "description": "Zone → Ward cascade (common in municipal portals)",
        "parent_field": "zone",
        "child_field": "ward",
        "wait_time": 1.5,
        "example_portals": ["mcd_delhi", "bmc_mumbai"],
    },
    "category_subcategory": {
        "description": "Category → Subcategory cascade (universal)",
        "parent_field": "category",
        "child_field": "sub_category",
        "wait_time": 1.5,
        "example_portals": ["mcd_delhi", "ranchi_smart"],
    },
    "state_district": {
        "description": "State → District cascade",
        "parent_field": "state",
        "child_field": "district",
        "wait_time": 1.0,
        "example_portals": ["cpgrams"],
    },
    "district_block": {
        "description": "District → Block cascade",
        "parent_field": "district",
        "child_field": "block",
        "wait_time": 1.0,
        "example_portals": ["jharkhand_portals"],
    },
    "department_officer": {
        "description": "Department → Officer cascade",
        "parent_field": "department",
        "child_field": "officer",
        "wait_time": 2.0,  # Often slower to load
        "example_portals": ["cpgrams", "pgportal"],
    },
}


def get_cascade_pattern(parent_field: str, child_field: str) -> Optional[Dict[str, Any]]:
    """
    Find a known cascade pattern by field names

    Args:
        parent_field: Name of parent field (e.g., "zone")
        child_field: Name of child field (e.g., "ward")

    Returns:
        Cascade pattern dict or None
    """
    parent_lower = parent_field.lower()
    child_lower = child_field.lower()

    for pattern_name, pattern in CASCADE_PATTERNS.items():
        if (pattern["parent_field"] in parent_lower and
            pattern["child_field"] in child_lower):
            return pattern

    return None


def get_recommended_wait_time(parent_field: str, child_field: str) -> float:
    """Get recommended wait time for cascade based on known patterns"""
    pattern = get_cascade_pattern(parent_field, child_field)
    return pattern["wait_time"] if pattern else 1.5  # Default
