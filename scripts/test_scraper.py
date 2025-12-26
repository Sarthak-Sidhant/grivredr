#!/usr/bin/env python3
"""
Test the generated scraper with real values
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the generated scraper
from outputs.generated_scrapers.ranchi_smart.ranchi_smart_scraper import Ranchi_SmartScraper


async def test_with_nlp_values():
    """Test scraper with values extracted from NLP"""

    print("=" * 60)
    print("Testing Ranchi Smart Scraper")
    print("=" * 60)
    print()

    # Test case 1: Air pollution in Anand Vihar Colony
    print("🧪 Test 1: Air pollution in Anand Vihar Colony")
    print("-" * 60)

    scraper = Ranchi_SmartScraper(headless=False)

    test_data = {
        'problem_type': '499',  # Air Pollution
        'area': '158',  # Anand Vihar Colony
        'name': 'Test Citizen',
        'mobile': '9876543210',
        'email': 'test@example.com',
        'contact': '9876543210',
        'address': 'Anand Vihar Colony, Ranchi',
        'remarks': 'There is severe air pollution in Anand Vihar Colony area. Smoke from nearby factories is causing breathing problems for residents.'
    }

    print(f"Input data:")
    print(f"  problem_type: 499 (Air Pollution)")
    print(f"  area: 158 (Anand Vihar Colony)")
    print()
    print("🚀 Starting scraper...")
    print()

    try:
        result = await scraper.submit_grievance(test_data)
        print()
        print("=" * 60)
        print("📊 Result:")
        print("=" * 60)
        print(f"Success: {result.get('success', False)}")
        if result.get('tracking_id'):
            print(f"Tracking ID: {result['tracking_id']}")
        if result.get('error'):
            print(f"Error: {result['error']}")
        if result.get('message'):
            print(f"Message: {result['message']}")
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Error: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()


async def test_multiple_cases():
    """Test multiple grievance types"""

    test_cases = [
        {
            'name': 'Air pollution in Anand Vihar',
            'data': {
                'problem_type': '499',  # Air Pollution
                'area': '158'  # Anand Vihar Colony
            }
        },
        {
            'name': 'Garbage on road in Doranda',
            'data': {
                'problem_type': '489',  # Dumping garbage on road
                'area': '497'  # Doranda
            }
        },
        {
            'name': 'Street light repair near Ranchi University',
            'data': {
                'problem_type': '362',  # Street Light Repairing
                'area': '259'  # Ranchi University
            }
        }
    ]

    print("=" * 60)
    print("Testing Multiple Grievance Types")
    print("=" * 60)
    print()

    for i, test_case in enumerate(test_cases, 1):
        print(f"🧪 Test {i}/{len(test_cases)}: {test_case['name']}")
        print("-" * 60)

        scraper = Ranchi_SmartScraper(headless=True)  # Headless for batch testing

        try:
            result = await scraper.submit_grievance(test_case['data'])

            if result.get('success'):
                print(f"✅ Success!")
                if result.get('tracking_id'):
                    print(f"   Tracking ID: {result['tracking_id']}")
            else:
                print(f"❌ Failed: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Exception: {e}")

        print()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--batch':
        # Run multiple tests
        asyncio.run(test_multiple_cases())
    else:
        # Run single test with visible browser
        asyncio.run(test_with_nlp_values())


if __name__ == "__main__":
    main()
