#!/usr/bin/env python3
"""Quick script to check department dropdown options"""
import asyncio
from playwright.async_api import async_playwright


async def check_departments():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await page.goto("https://www.abuasathiranchi.org/SiteController/onlinegrievance")
        await page.wait_for_load_state('networkidle')

        print("\nDEPARTMENT DROPDOWN OPTIONS:")
        try:
            dept_options = await page.locator("#department_id option").all()
            for i, option in enumerate(dept_options):
                value = await option.get_attribute('value')
                text = await option.text_content()
                print(f"   [{i}] value='{value}' text='{text.strip()}'")
        except Exception as e:
            print(f"   Error: {e}")

        await asyncio.sleep(30)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(check_departments())
