#!/usr/bin/env python3
"""
Smart Form Discovery - Uses Playwright directly for fast discovery,
then uses AI only for generating the scraper code.

This is 100x more efficient than using browser-use for discovery.
"""
import asyncio
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, Locator
import anthropic

load_dotenv()


class CostTracker:
    """Track API costs"""
    # Pricing per 1M tokens (as of Dec 2024)
    PRICING = {
        "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
        "claude-opus-4-5-20250929": {"input": 15.0, "output": 75.0},
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
    }

    def __init__(self):
        self.calls = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

    def add_call(self, model: str, input_tokens: int, output_tokens: int):
        pricing = self.PRICING.get(model, {"input": 3.0, "output": 15.0})
        cost = (input_tokens * pricing["input"] / 1_000_000) + \
               (output_tokens * pricing["output"] / 1_000_000)

        self.calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost
        })
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost

        print(f"  [Cost] {model}: {input_tokens} in, {output_tokens} out = ${cost:.4f}")

    def summary(self):
        return {
            "total_calls": len(self.calls),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": self.total_cost,
            "calls": self.calls
        }


class SmartFormDiscovery:
    """
    Discovers form structure using Playwright directly (fast, no AI tokens).
    Only uses AI for generating the final scraper code.
    """

    def __init__(self, output_dir: str = "scrapers"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.api_key = os.getenv("api_key")
        self.cost_tracker = CostTracker()
        self.anthropic_client = anthropic.Anthropic(
            api_key=self.api_key,
            base_url="https://ai.megallm.io"
        )

    async def discover_form(self, url: str, headless: bool = True) -> dict:
        """
        Use Playwright directly to discover form fields - NO AI TOKENS USED.
        This is fast and efficient.
        """
        print("\n[Discovery] Using Playwright (no AI) to analyze form...")

        form_structure = {
            "form_url": url,
            "form_title": "",
            "total_fields": 0,
            "sections": [],
            "submit_button": None,
            "notes": []
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

            try:
                print(f"  Navigating to {url[:60]}...")
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)  # Let JS render

                # Get page title
                form_structure["form_title"] = await page.title()

                # Find all form fields using JavaScript
                fields = await self._extract_fields_js(page)
                form_structure["sections"] = self._organize_into_sections(fields)
                form_structure["total_fields"] = len(fields)

                # Find submit button
                form_structure["submit_button"] = await self._find_submit_button(page)

                # Discover dropdown options for select fields
                await self._discover_dropdown_options(page, form_structure)

                print(f"  Found {len(fields)} fields")

            except Exception as e:
                form_structure["notes"].append(f"Discovery error: {str(e)}")
                print(f"  Error: {e}")

            finally:
                await browser.close()

        return form_structure

    async def _extract_fields_js(self, page: Page) -> list:
        """Extract all form fields using JavaScript - efficient single call"""

        js_code = """
        () => {
            const fields = [];

            // Helper to get label for an element
            function getLabel(el) {
                // Check for associated label
                if (el.id) {
                    const label = document.querySelector(`label[for="${el.id}"]`);
                    if (label) return label.textContent.trim();
                }
                // Check parent label
                const parentLabel = el.closest('label');
                if (parentLabel) return parentLabel.textContent.trim();
                // Check preceding label sibling
                const prev = el.previousElementSibling;
                if (prev && prev.tagName === 'LABEL') return prev.textContent.trim();
                // Check placeholder or aria-label
                return el.placeholder || el.getAttribute('aria-label') || el.name || el.id || '';
            }

            // Helper to determine field type
            function getFieldType(el) {
                if (el.tagName === 'SELECT') return 'select';
                if (el.tagName === 'TEXTAREA') return 'textarea';
                if (el.type === 'checkbox') return 'checkbox';
                if (el.type === 'radio') return 'radio';
                if (el.type === 'file') return 'file';
                if (el.type === 'email') return 'email';
                if (el.type === 'tel') return 'phone';
                if (el.type === 'number') return 'number';
                if (el.type === 'date') return 'date';
                if (el.type === 'password') return 'password';
                // Check for searchable dropdown (common pattern)
                if (el.getAttribute('role') === 'combobox' ||
                    el.classList.contains('ant-select') ||
                    el.closest('.ant-select')) return 'searchable_select';
                return 'text';
            }

            // Helper to get CSS selector
            function getSelector(el) {
                if (el.id) return '#' + el.id;
                if (el.name) return `[name="${el.name}"]`;
                // Build a unique selector
                let selector = el.tagName.toLowerCase();
                if (el.className) {
                    selector += '.' + el.className.split(' ').filter(c => c).join('.');
                }
                return selector;
            }

            // Get all input elements
            const inputs = document.querySelectorAll('input, textarea, select');

            inputs.forEach(el => {
                // Skip hidden and submit/button types
                if (el.type === 'hidden' || el.type === 'submit' || el.type === 'button') return;

                const field = {
                    field_name: getLabel(el),
                    field_type: getFieldType(el),
                    css_selector: getSelector(el),
                    id: el.id || null,
                    name: el.name || null,
                    is_required: el.required || el.getAttribute('aria-required') === 'true',
                    placeholder: el.placeholder || '',
                    is_searchable: el.getAttribute('role') === 'combobox' || el.type === 'search',
                    options: [],
                    accept: el.accept || null  // For file inputs
                };

                // Get options for regular select
                if (el.tagName === 'SELECT') {
                    field.options = Array.from(el.options).map(opt => ({
                        value: opt.value,
                        text: opt.textContent.trim()
                    }));
                }

                fields.push(field);
            });

            // Also look for ant-design style selects (common in React apps)
            document.querySelectorAll('.ant-select, [class*="select-wrapper"]').forEach(wrapper => {
                const input = wrapper.querySelector('input');
                if (input && !fields.find(f => f.id === input.id)) {
                    const label = getLabel(wrapper) || getLabel(input);
                    fields.push({
                        field_name: label,
                        field_type: 'searchable_select',
                        css_selector: getSelector(input),
                        id: input.id || null,
                        name: input.name || null,
                        is_required: input.required || wrapper.querySelector('[aria-required="true"]') !== null,
                        placeholder: input.placeholder || '',
                        is_searchable: true,
                        options: [],
                        wrapper_selector: getSelector(wrapper)
                    });
                }
            });

            return fields;
        }
        """

        return await page.evaluate(js_code)

    def _organize_into_sections(self, fields: list) -> list:
        """Organize fields into sections (simple grouping for now)"""
        # For now, just put all in one section
        # Could be enhanced to detect fieldsets, divs with headers, etc.
        return [{
            "name": "Form Fields",
            "fields": fields
        }]

    async def _find_submit_button(self, page: Page) -> dict:
        """Find the submit button"""
        js_code = """
        () => {
            const btn = document.querySelector('button[type="submit"], input[type="submit"], button:contains("Submit")');
            if (btn) {
                return {
                    text: btn.textContent?.trim() || btn.value || 'Submit',
                    css_selector: btn.id ? '#' + btn.id : 'button[type="submit"]'
                };
            }
            // Fallback - find any button with submit-like text
            const buttons = document.querySelectorAll('button');
            for (const b of buttons) {
                if (/submit|save|send/i.test(b.textContent)) {
                    return {
                        text: b.textContent.trim(),
                        css_selector: b.id ? '#' + b.id : `button:has-text("${b.textContent.trim()}")`
                    };
                }
            }
            return null;
        }
        """
        return await page.evaluate(js_code)

    async def _discover_dropdown_options(self, page: Page, form_structure: dict):
        """Discover options for dropdown fields by clicking them"""
        print("  Discovering dropdown options...")

        for section in form_structure["sections"]:
            for field in section["fields"]:
                if field["field_type"] in ["select", "searchable_select"] and not field["options"]:
                    try:
                        options = await self._get_dropdown_options(page, field)
                        field["options"] = options
                        if options:
                            print(f"    {field['field_name']}: {len(options)} options")
                    except Exception as e:
                        field["notes"] = f"Could not extract options: {str(e)}"

    async def _get_dropdown_options(self, page: Page, field: dict) -> list:
        """Get options for a single dropdown by clicking it"""
        options = []
        selector = field["css_selector"]

        try:
            # Click to open dropdown
            el = page.locator(selector).first
            await el.click()
            await page.wait_for_timeout(500)

            # Try to find dropdown options
            # Common patterns for dropdown options
            option_selectors = [
                ".ant-select-dropdown .ant-select-item",
                "[role='option']",
                ".dropdown-menu li",
                ".select-options li",
                "[class*='option']",
            ]

            for opt_selector in option_selectors:
                opts = await page.locator(opt_selector).all()
                if opts:
                    for opt in opts[:50]:  # Limit to 50 options
                        text = await opt.text_content()
                        if text and text.strip():
                            options.append(text.strip())
                    if options:
                        break

            # Close dropdown
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)

        except Exception:
            pass

        return options

    def generate_scraper(self, form_structure: dict, portal_name: str) -> str:
        """Use AI to generate a Playwright scraper from the discovered structure"""

        print("\n[Generation] Using Claude to generate scraper code...")

        prompt = f"""Generate a production-ready Playwright Python scraper for this form:

```json
{json.dumps(form_structure, indent=2)}
```

Requirements:
1. Class name: `{portal_name.title().replace('_', '')}FormFiller`
2. Async Playwright-based
3. Methods: `__init__(headless=True)`, `async start()`, `async fill_form(data: dict)`, `async submit()`, `async close()`, `async run(data: dict, submit=False)`
4. Handle searchable dropdowns: click, type to search, wait for options, click matching option
5. Handle cascading dropdowns (e.g., Sub Category depends on Category)
6. Proper waits and error handling
7. Logging for each step
8. Include `if __name__ == "__main__"` with sample usage

Generate ONLY Python code, no explanations."""

        response = self.anthropic_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        # Track cost
        self.cost_tracker.add_call(
            "claude-sonnet-4-5-20250929",
            response.usage.input_tokens,
            response.usage.output_tokens
        )

        code = response.content[0].text

        # Clean up code block markers
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]

        return code.strip()

    def save_scraper(self, code: str, portal_name: str, form_structure: dict) -> Path:
        """Save the generated scraper and metadata"""

        portal_dir = self.output_dir / portal_name
        portal_dir.mkdir(exist_ok=True)

        # Save scraper
        scraper_path = portal_dir / f"{portal_name}_scraper.py"
        with open(scraper_path, 'w') as f:
            f.write(code)

        # Save structure
        structure_path = portal_dir / f"{portal_name}_structure.json"
        with open(structure_path, 'w') as f:
            json.dump(form_structure, f, indent=2)

        # Save metadata with costs
        metadata = {
            "portal_name": portal_name,
            "generated_at": datetime.now().isoformat(),
            "form_url": form_structure.get("form_url"),
            "total_fields": form_structure.get("total_fields"),
            "costs": self.cost_tracker.summary()
        }
        metadata_path = portal_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        return scraper_path

    async def generate_from_url(self, url: str, portal_name: str, headless: bool = True) -> Path:
        """Complete pipeline: discover form and generate scraper"""

        print(f"\n{'='*60}")
        print(f"Smart Form Discovery & Scraper Generation")
        print(f"Portal: {portal_name}")
        print(f"{'='*60}")

        # Step 1: Discover (NO AI - uses Playwright directly)
        print("\n[1/3] Discovering form structure (Playwright - FREE)...")
        form_structure = await self.discover_form(url, headless=headless)
        print(f"  Found {form_structure['total_fields']} fields")

        # Step 2: Generate scraper (uses AI - costs tokens)
        print("\n[2/3] Generating scraper (Claude - costs tokens)...")
        scraper_code = self.generate_scraper(form_structure, portal_name)

        # Step 3: Save
        print("\n[3/3] Saving files...")
        scraper_path = self.save_scraper(scraper_code, portal_name, form_structure)

        # Summary
        costs = self.cost_tracker.summary()
        print(f"\n{'='*60}")
        print("COMPLETE!")
        print(f"{'='*60}")
        print(f"Scraper: {scraper_path}")
        print(f"Total API Cost: ${costs['total_cost']:.4f}")
        print(f"Tokens: {costs['total_input_tokens']} input, {costs['total_output_tokens']} output")

        return scraper_path


async def main():
    """Test the smart discovery"""
    discovery = SmartFormDiscovery()

    url = "https://mcd.everythingcivic.com/citizen/createissue?app_id=U2FsdGVkX180J3mGnJmT5QpgtPjhfjtzyXAAccBUxGU%3D&api_key=e34ba86d3943bd6db9120313da011937189e6a9625170905750f649395bcd68312cf10d264c9305d57c23688cc2e5120"

    scraper_path = await discovery.generate_from_url(
        url=url,
        portal_name="mcd_delhi",
        headless=True
    )

    print(f"\nGenerated: {scraper_path}")


if __name__ == "__main__":
    asyncio.run(main())
