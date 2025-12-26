#!/usr/bin/env python3
"""
Inspect form structure to identify all required fields
"""
import asyncio
from playwright.async_api import async_playwright

async def check_form():
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()

    print("Loading form...")
    await page.goto('https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online', wait_until='networkidle')
    await asyncio.sleep(3)

    # Check all input fields
    inputs = await page.evaluate("""() => {
        const fields = [];
        document.querySelectorAll('input, textarea, select').forEach(el => {
            if (el.type !== 'hidden' && el.offsetParent !== null) {
                fields.push({
                    id: el.id,
                    name: el.name,
                    type: el.type || el.tagName.toLowerCase(),
                    required: el.required,
                    placeholder: el.placeholder || ''
                });
            }
        });
        return fields;
    }""")

    print('\nVisible form fields:')
    for field in inputs:
        req = "✓ REQUIRED" if field.get('required') else ""
        print(f"  - {field['id'] or field['name']} ({field['type']}) {req}")

    # Check submit buttons
    buttons = await page.evaluate("""() => {
        const btns = [];
        document.querySelectorAll('button, input[type=submit], input[type=button]').forEach(el => {
            if (el.offsetParent !== null) {
                btns.push({
                    id: el.id,
                    type: el.type,
                    text: el.innerText || el.value,
                    selector: el.tagName + (el.id ? '#' + el.id : '')
                });
            }
        });
        return btns;
    }""")

    print('\nVisible buttons:')
    for btn in buttons:
        print(f"  - {btn['selector']}: '{btn['text']}' (type={btn['type']})")

    await browser.close()
    await playwright.stop()

if __name__ == "__main__":
    asyncio.run(check_form())
