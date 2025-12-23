"""
Test generated scrapers with sample data
"""
import asyncio
import json
from executor.runner import ScraperExecutor


async def main():
    """Test all available scrapers"""

    executor = ScraperExecutor()

    print("="*80)
    print("🧪 Testing Generated Scrapers")
    print("="*80)

    # List available scrapers
    scrapers = executor.list_available_scrapers()

    if not scrapers:
        print("\n❌ No scrapers found!")
        print("Run 'python learn_ranchi.py' first to generate scrapers.")
        return

    print(f"\nFound {len(scrapers)} municipalities with scrapers:\n")
    for municipality, scraper_list in scrapers.items():
        print(f"📍 {municipality.title()}")
        for scraper in scraper_list:
            print(f"   - {scraper}")
        print()

    # Sample test data
    test_data = {
        "name": "Rahul Kumar",
        "phone": "9876543210",
        "email": "rahul.kumar@example.com",
        "complaint": "Street light not working in my area for past 2 weeks. Causing safety issues at night.",
        "category": "Street Lights",
        "address": "HB Road, Sector 5, Doranda, Ranchi - 834002",
        "description": "The street light pole near house number 45 has been non-functional for 2 weeks."
    }

    print("="*80)
    print("📝 Test Grievance Data")
    print("="*80)
    print(json.dumps(test_data, indent=2))
    print()

    # Test each municipality
    for municipality in scrapers.keys():
        # Find complaint form scraper
        complaint_scrapers = [
            s for s in scrapers[municipality]
            if "complaint" in s or "grievance" in s
        ]

        if not complaint_scrapers:
            print(f"⚠️  No complaint scraper found for {municipality}")
            continue

        # Extract website type from scraper name
        scraper_name = complaint_scrapers[0]
        website_type = scraper_name.replace(f"{municipality}_", "").replace("_scraper", "")

        print("="*80)
        print(f"🚀 Testing {municipality.title()} - {website_type}")
        print("="*80)

        try:
            result = await executor.execute_scraper(
                municipality_name=municipality,
                website_type=website_type,
                grievance_data=test_data
            )

            print("\n✅ Execution completed!")
            print(f"Success: {result.get('success')}")
            print(f"Execution time: {result.get('execution_time', 0):.2f}s")
            print(f"Attempts: {result.get('attempts', 1)}")

            if result.get('success'):
                print(f"\n🎫 Tracking ID: {result.get('tracking_id', 'N/A')}")
                if result.get('screenshots'):
                    print(f"📸 Screenshots: {len(result.get('screenshots', []))}")
            else:
                print(f"\n❌ Error: {result.get('error')}")

            print(f"\nFull result:")
            print(json.dumps(result, indent=2, default=str))

        except Exception as e:
            print(f"\n❌ Test failed: {e}")

        print("\n")

    print("="*80)
    print("🏁 Testing Complete")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
