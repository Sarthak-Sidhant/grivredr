#!/usr/bin/env python3
"""
Form Scraper Generator - Uses Browser-use AI to discover form fields,
then generates a reusable Playwright scraper that runs without AI.
"""
import asyncio
import os
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from browser_use import Agent, Browser, ChatAnthropic
from browser_use.browser import BrowserProfile
import anthropic

load_dotenv()


class FormScraperGenerator:
    """Generates reusable Playwright scrapers from AI-discovered form structures"""

    def __init__(self, output_dir: str = "scrapers"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.api_key = os.getenv("api_key")
        self.anthropic_client = anthropic.Anthropic(
            api_key=self.api_key,
            base_url="https://ai.megallm.io"
        )

    async def discover_form(self, url: str, headless: bool = True) -> dict:
        """Use Browser-use AI to discover all form fields and their selectors"""

        llm = ChatAnthropic(
            model='claude-sonnet-4-5-20250929',
            temperature=0.0,
            api_key=self.api_key,
            base_url="https://ai.megallm.io"
        )

        profile = BrowserProfile(
            headless=headless,
            enable_default_extensions=False,
            wait_for_network_idle_page_load_time=3.0,
            minimum_wait_page_load_time=1.0,
        )

        browser = Browser(browser_profile=profile)

        initial_actions = [
            {"navigate": {"url": url}},
        ]

        discovery_task = """You are a form analysis expert. Analyze this page and extract COMPLETE form field information.

Your task:
1. Wait for the page to fully load
2. Identify ALL form fields on the page
3. For EACH field, extract:
   - field_name: Human readable name (e.g., "First Name", "Category")
   - field_type: One of [text, textarea, select, radio, checkbox, file, email, phone, number, date, password]
   - css_selector: The most reliable CSS selector (prefer #id, then name attribute, then class)
   - xpath: XPath selector as backup
   - is_required: true/false
   - placeholder: Any placeholder text
   - options: For select/dropdown fields, list all available options if visible
   - is_searchable: true if it's a searchable dropdown/autocomplete
   - parent_section: Which section of the form this belongs to

4. For dropdown/select fields:
   - Click on them to reveal options
   - Record all available options
   - Note if they're searchable/autocomplete style

5. Scroll through the entire form to find all fields

6. Return your findings as a JSON object with this structure:
{
  "form_url": "the url",
  "form_title": "title if visible",
  "total_fields": number,
  "sections": [
    {
      "name": "Section Name",
      "fields": [
        {
          "field_name": "Field Label",
          "field_type": "text|select|textarea|etc",
          "css_selector": "#field_id or [name='field'] or .class",
          "xpath": "//input[@id='field']",
          "is_required": true,
          "placeholder": "placeholder text",
          "options": ["option1", "option2"] // for select fields
          "is_searchable": false
        }
      ]
    }
  ],
  "submit_button": {
    "text": "Submit",
    "css_selector": "button[type='submit']"
  },
  "notes": "any important notes about form behavior"
}

Be thorough - missing a field means the generated scraper will fail!"""

        print("Discovering form structure with AI...")

        agent = Agent(
            task=discovery_task,
            llm=llm,
            browser=browser,
            initial_actions=initial_actions,
        )

        result = await agent.run(max_steps=20)

        # Extract the JSON from the result
        # The result object has different attributes depending on version
        final_text = None
        if hasattr(result, 'final_result'):
            fr = result.final_result
            if callable(fr):
                fr = fr()
            if isinstance(fr, str):
                final_text = fr
            elif hasattr(fr, 'text'):
                final_text = fr.text

        # Try to get from history if final_result didn't work
        if not final_text and hasattr(result, 'history'):
            for item in reversed(result.history):
                if hasattr(item, 'result') and item.result:
                    for r in item.result:
                        if hasattr(r, 'extracted_content') and r.extracted_content:
                            final_text = r.extracted_content
                            break
                    if final_text:
                        break

        if final_text:
            return self._parse_discovery_result(final_text)
        return None

    def _parse_discovery_result(self, result_text: str) -> dict:
        """Parse the discovery result and extract JSON"""
        # Try to find JSON in the result
        import re

        # Look for JSON block
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Return as structured dict if parsing fails
        return {"raw_result": result_text}

    def generate_scraper(self, form_structure: dict, portal_name: str) -> str:
        """Use Opus to generate a Playwright scraper from the discovered form structure"""

        print("Generating Playwright scraper with Opus...")

        prompt = f"""You are an expert Python developer. Generate a complete, production-ready Playwright scraper based on this discovered form structure:

```json
{json.dumps(form_structure, indent=2)}
```

Requirements:
1. Create a Python class called `{portal_name.title().replace('_', '')}FormFiller`
2. Use async Playwright for browser automation
3. Include methods:
   - `__init__(self, headless=True)`: Initialize browser
   - `async start(self)`: Start browser session
   - `async fill_form(self, data: dict)`: Fill the form with provided data
   - `async submit(self)`: Submit the form (optional, controlled by parameter)
   - `async close(self)`: Close browser
   - `async run(self, data: dict, submit=False)`: Main entry point

4. For each field type, use appropriate Playwright methods:
   - text/email/phone/number: `fill()` or `type()`
   - textarea: `fill()`
   - select (regular): `select_option()`
   - select (searchable/autocomplete): click, type to search, wait for options, click option
   - checkbox: `check()` or `uncheck()`
   - radio: `click()`
   - file: `set_input_files()`

5. Include proper waits and error handling:
   - Wait for page load
   - Wait for elements to be visible/enabled
   - Handle dropdowns that load dynamically
   - Retry logic for flaky elements

6. Add logging for each step

7. Include a `if __name__ == "__main__":` block with sample usage

8. Add docstrings and type hints

Generate ONLY the Python code, no explanations. The code should be complete and runnable."""

        response = self.anthropic_client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        code = response.content[0].text

        # Clean up code block markers if present
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]

        return code.strip()

    def save_scraper(self, code: str, portal_name: str, form_structure: dict) -> Path:
        """Save the generated scraper and its metadata"""

        # Create portal directory
        portal_dir = self.output_dir / portal_name
        portal_dir.mkdir(exist_ok=True)

        # Save scraper code
        scraper_path = portal_dir / f"{portal_name}_scraper.py"
        with open(scraper_path, 'w') as f:
            f.write(code)

        # Save form structure for reference
        structure_path = portal_dir / f"{portal_name}_structure.json"
        with open(structure_path, 'w') as f:
            json.dump(form_structure, f, indent=2)

        # Save metadata
        metadata = {
            "portal_name": portal_name,
            "generated_at": datetime.now().isoformat(),
            "form_url": form_structure.get("form_url", "unknown"),
            "total_fields": form_structure.get("total_fields", 0),
            "scraper_file": str(scraper_path),
            "structure_file": str(structure_path)
        }
        metadata_path = portal_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"Scraper saved to: {scraper_path}")
        print(f"Structure saved to: {structure_path}")

        return scraper_path

    async def generate_from_url(self, url: str, portal_name: str, headless: bool = True) -> Path:
        """Complete pipeline: discover form and generate scraper"""

        print(f"\n{'='*60}")
        print(f"Generating scraper for: {portal_name}")
        print(f"URL: {url}")
        print(f"{'='*60}\n")

        # Step 1: Discover form structure
        print("[1/3] Discovering form structure...")
        form_structure = await self.discover_form(url, headless=headless)

        if not form_structure:
            raise Exception("Failed to discover form structure")

        print(f"Discovered {form_structure.get('total_fields', 'unknown')} fields\n")

        # Step 2: Generate scraper code
        print("[2/3] Generating Playwright scraper...")
        scraper_code = self.generate_scraper(form_structure, portal_name)

        # Step 3: Save everything
        print("[3/3] Saving scraper...")
        scraper_path = self.save_scraper(scraper_code, portal_name, form_structure)

        print(f"\n{'='*60}")
        print("Generation complete!")
        print(f"{'='*60}")
        print(f"\nTo use the scraper:")
        print(f"  from scrapers.{portal_name}.{portal_name}_scraper import {portal_name.title().replace('_', '')}FormFiller")
        print(f"\n  async with {portal_name.title().replace('_', '')}FormFiller() as filler:")
        print(f"      await filler.run(data={{'field': 'value'}})")

        return scraper_path


async def main():
    """Test the generator"""
    generator = FormScraperGenerator()

    # Test with MCD Delhi
    url = "https://mcd.everythingcivic.com/citizen/createissue?app_id=U2FsdGVkX180J3mGnJmT5QpgtPjhfjtzyXAAccBUxGU%3D&api_key=e34ba86d3943bd6db9120313da011937189e6a9625170905750f649395bcd68312cf10d264c9305d57c23688cc2e5120"

    scraper_path = await generator.generate_from_url(
        url=url,
        portal_name="mcd_delhi",
        headless=True
    )

    print(f"\nGenerated scraper: {scraper_path}")


if __name__ == "__main__":
    asyncio.run(main())
