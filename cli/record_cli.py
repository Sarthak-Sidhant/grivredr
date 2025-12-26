#!/usr/bin/env python3
"""
CLI for recording human interactions with forms
"""
import asyncio
import sys
from agents.human_recorder_agent import HumanRecorderAgent


async def main():
    """Main CLI for recording"""
    print("=" * 80)
    print("🎬 Grivredr Human Recording System")
    print("=" * 80)
    print()

    if len(sys.argv) < 2:
        print("Usage: python record_cli.py <municipality_name> [url]")
        print()
        print("Known municipalities:")
        print("  ranchi_smart - https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online")
        print()
        print("Examples:")
        print("  python record_cli.py ranchi_smart")
        print("  python record_cli.py patna https://patna.gov.in/complaint")
        print()
        sys.exit(1)

    municipality = sys.argv[1]

    # Known URLs
    known_urls = {
        "ranchi_smart": "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online",
        "ranchi_main": "https://www.ranchimunicipal.com/",
        "jharkhand_state": "https://jharkhandegovernance.com/grievance/main"
    }

    if len(sys.argv) >= 3:
        url = sys.argv[2]
    elif municipality in known_urls:
        url = known_urls[municipality]
    else:
        print(f"❌ Unknown municipality: {municipality}")
        print(f"   Please provide URL: python record_cli.py {municipality} <url>")
        sys.exit(1)

    print(f"Municipality: {municipality}")
    print(f"URL: {url}")
    print()

    # Create recorder
    recorder = HumanRecorderAgent(headless=False)

    print("🎬 Starting recording session...")
    print()
    result = await recorder.start_recording(url, municipality)

    if result['success']:
        print()
        print("=" * 80)
        print("✅ RECORDING COMPLETE!")
        print("=" * 80)
        print(f"📊 Recorded {result['actions_count']} actions")
        print(f"💾 Saved to: {result['recording_file']}")
        if result.get('tracking_id'):
            print(f"🎫 Tracking ID: {result['tracking_id']}")
        print()

        # Ask if user wants to generate scraper now
        print("Generate scraper from this recording? (Y/n): ", end='')
        generate = input().strip().lower()

        if generate != 'n':
            print()
            print("🔧 Generating scraper...")
            scraper_file = recorder.generate_scraper_from_recording(result['recording_file'])
            print(f"✅ Scraper generated: {scraper_file}")
            print()
            print("Next steps:")
            print(f"  1. Review scraper: cat {scraper_file}")
            print(f"  2. Test scraper: python {scraper_file}")
            print()
    else:
        print()
        print("❌ Recording failed or was cancelled")


if __name__ == "__main__":
    asyncio.run(main())
