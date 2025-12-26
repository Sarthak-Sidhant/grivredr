#!/usr/bin/env python3
"""
Test the AI-generated abua_sathi_ai_tests scraper
"""
import asyncio
import sys
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent.parent / "outputs/generated_scrapers/_temp/abua_sathi_ai_tests"))

from abua_sathi_ai_tests_scraper import AbuaSathiAiTestsScraper


async def test_ai_scraper():
    print("="*80)
    print("🤖 TESTING AI-GENERATED SCRAPER (abua_sathi_ai_tests)")
    print("="*80)
    print()

    scraper = AbuaSathiAiTestsScraper(headless=False)

    print("📋 Test Data (with correct field names from schema):")
    test_data = {
        'name': 'AI Generated Test User',
        'contact': '9876543210',
        'village_name': 'AI Test Village, Ranchi, Jharkhand',
        'block_id': '500107',  # Ranchi Municipal Corporation
        'jurisdiction_id': '600624',  # Ward-1
        'department_id': '500107',  # Ranchi Municipal Corporation
        'description': 'This is testing the AI-generated scraper to verify it learned the correct field names and Select2 handling!'
    }

    for key, value in test_data.items():
        print(f"  {key}: {value}")
    print()

    print("🚀 Running AI-generated scraper...")
    print()

    result = await scraper.submit_grievance(test_data)

    print()
    print("="*80)
    print("📊 RESULT:")
    print("="*80)
    print(f"Success: {result.get('success')}")

    if result.get('success'):
        print("✅ AI-GENERATED SCRAPER WORKS!")
        print(f"🎯 Tracking ID: {result.get('tracking_id')}")
        print(f"💬 Message: {result.get('message')}")
        if result.get('screenshots'):
            print(f"📸 Screenshots: {len(result.get('screenshots'))} saved")
    else:
        print("❌ FAILED")
        print(f"Error: {result.get('error', result.get('message'))}")
        if result.get('errors'):
            print("\nErrors:")
            for err in result['errors']:
                print(f"  - {err}")

    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_ai_scraper())
