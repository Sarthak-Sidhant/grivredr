#!/usr/bin/env python3
"""
Interactive script to explore the Abua Sathi form and find dropdown options.
"""
import asyncio
from playwright.async_api import async_playwright


async def explore_form():
    """Explore the form and print all dropdown options"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        print("Navigating to Abua Sathi form...")
        await page.goto("https://www.abuasathiranchi.org/SiteController/onlinegrievance")
        await page.wait_for_load_state('networkidle')

        print("\n" + "="*80)
        print("EXPLORING DROPDOWN OPTIONS")
        print("="*80)

        # Find Block dropdown
        print("\n1. BLOCK / MUNICIPALITY DROPDOWN (#block_id):")
        try:
            block_options = await page.locator("#block_id option").all()
            for i, option in enumerate(block_options):
                value = await option.get_attribute('value')
                text = await option.text_content()
                print(f"   [{i}] value='{value}' text='{text.strip()}'")
        except Exception as e:
            print(f"   Error: {e}")

        # Find GP/Ward dropdown
        print("\n2. GP / WARD DROPDOWN (#jurisdiction_id):")
        try:
            ward_options = await page.locator("#jurisdiction_id option").all()
            for i, option in enumerate(ward_options):
                value = await option.get_attribute('value')
                text = await option.text_content()
                print(f"   [{i}] value='{value}' text='{text.strip()}'")
        except Exception as e:
            print(f"   Error: {e}")

        # Find Department dropdown
        print("\n3. DEPARTMENT DROPDOWN (#department_id):")
        try:
            dept_options = await page.locator("#department_id option").all()
            for i, option in enumerate(dept_options):
                value = await option.get_attribute('value')
                text = await option.text_content()
                print(f"   [{i}] value='{value}' text='{text.strip()}'")
        except Exception as e:
            print(f"   Error: {e}")

        # Test cascading: select a block and see if ward options change
        print("\n" + "="*80)
        print("TESTING CASCADING DROPDOWNS")
        print("="*80)

        # Get first non-empty block option
        block_options = await page.locator("#block_id option").all()
        for option in block_options[1:]:  # Skip first option (usually empty)
            block_value = await option.get_attribute('value')
            block_text = await option.text_content()
            if block_value:
                print(f"\nSelecting Block: '{block_text.strip()}' (value={block_value})")
                await page.select_option("#block_id", value=block_value)

                # Wait for AJAX to populate ward dropdown
                print("Waiting for cascading dropdown to populate...")
                await asyncio.sleep(3)

                # Check ward options again
                print("\nGP/Ward options after selecting block:")
                ward_options = await page.locator("#jurisdiction_id option").all()
                for i, option in enumerate(ward_options):
                    value = await option.get_attribute('value')
                    text = await option.text_content()
                    print(f"   [{i}] value='{value}' text='{text.strip()}'")

                break

        print("\n" + "="*80)
        print("Press Enter to close the browser...")
        await asyncio.sleep(60)  # Give time to inspect

        await browser.close()


if __name__ == "__main__":
    asyncio.run(explore_form())
