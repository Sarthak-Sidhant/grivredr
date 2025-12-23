"""
Quick script to learn Ranchi municipality websites
Run this to bootstrap the system with Ranchi scrapers
"""
import asyncio
import json
from website_learner.learner import WebsiteLearner
from scraper_generator.generator import ScraperGenerator


async def main():
    """Learn Ranchi websites and generate scrapers"""

    # Ranchi websites
    ranchi_websites = [
        {
            "url": "https://www.ranchimunicipal.com/",
            "type": "main_portal",
            "description": "Ranchi Municipal Corporation main website"
        },
        {
            "url": "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online",
            "type": "complaint_form",
            "description": "Smart Ranchi online complaint registration"
        },
        {
            "url": "https://jharkhandegovernance.com/grievance/main",
            "type": "state_grievance",
            "description": "Jharkhand e-Governance grievance portal"
        }
    ]

    print("="*80)
    print("🤖 AI-Powered Website Learning & Scraper Generation")
    print("="*80)
    print(f"\nMunicipality: Ranchi")
    print(f"Websites to learn: {len(ranchi_websites)}\n")

    for i, site in enumerate(ranchi_websites, 1):
        print(f"{i}. {site['description']}")
        print(f"   URL: {site['url']}")
        print(f"   Type: {site['type']}\n")

    print("Starting learning process...\n")

    # Initialize learner (headless=False to see the browser)
    async with WebsiteLearner(headless=False) as learner:
        learning_results = await learner.learn_multiple_websites(
            websites=ranchi_websites,
            municipality_name="ranchi"
        )

    # Print learning results
    print("\n" + "="*80)
    print("📊 Learning Results")
    print("="*80)

    for i, result in enumerate(learning_results, 1):
        print(f"\n{i}. {result.get('website_type', 'unknown')}")
        print(f"   URL: {result.get('url')}")
        print(f"   Success: {result.get('success')}")

        if result.get('success'):
            analysis = result.get('analysis', {})
            print(f"   Form fields found: {len(analysis.get('form_fields', []))}")
            print(f"   Screenshots: {len(result.get('screenshots', []))}")
        else:
            print(f"   Error: {result.get('error')}")

    # Generate scrapers
    print("\n" + "="*80)
    print("🔧 Generating Scrapers")
    print("="*80)

    generator = ScraperGenerator()
    generation_result = generator.generate_scrapers_for_municipality(
        learning_results=learning_results,
        municipality_name="ranchi"
    )

    print(f"\nGenerated: {generation_result['generated_count']} scrapers")
    print(f"Failed: {generation_result['failed_count']}\n")

    for i, generated in enumerate(generation_result['generated'], 1):
        print(f"{i}. {generated['metadata']['website_type']}")
        print(f"   File: {generated['file_path']}")

    if generation_result['failed']:
        print("\n⚠️  Failed scrapers:")
        for failed in generation_result['failed']:
            print(f"   - {failed['url']}: {failed['error']}")

    # Save complete results
    results_file = "learning_results_ranchi.json"
    with open(results_file, "w") as f:
        json.dump({
            "learning_results": learning_results,
            "generation_result": generation_result
        }, f, indent=2, default=str)

    print(f"\n✅ Complete results saved to: {results_file}")
    print("\n" + "="*80)
    print("🎉 Done! Your Ranchi scrapers are ready to use.")
    print("="*80)
    print("\nNext steps:")
    print("1. Test scrapers: python test_scrapers.py")
    print("2. Start API: python main.py")
    print("3. Submit grievance: POST /api/submit")


if __name__ == "__main__":
    asyncio.run(main())
