#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

async def check_cascade():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto('https://www.abuasathiranchi.org/SiteController/onlinegrievance')
        await page.wait_for_load_state('networkidle')

        print('Selecting Ranchi Municipal Corporation...')
        # Use JavaScript to select block
        await page.evaluate('''
            () => {
                const select = document.querySelector('#block_id');
                $(select).val('500107');
                $(select).trigger('change');
            }
        ''')

        print('Waiting for cascade...')
        await asyncio.sleep(3)

        print('\nGP/Ward options for Ranchi Municipal Corporation:')
        ward_options = await page.locator('#jurisdiction_id option').all()
        for i, option in enumerate(ward_options):
            value = await option.get_attribute('value')
            text = await option.text_content()
            if value:
                print(f'   [{i}] value={repr(value)} text={repr(text.strip())}')

        await asyncio.sleep(30)
        await browser.close()

asyncio.run(check_cascade())
