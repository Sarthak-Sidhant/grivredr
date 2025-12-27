#!/usr/bin/env python3
"""
CLI Tool for Training AI Agents on Municipal Websites
"""
import asyncio
import sys
import argparse
from agents.orchestrator import Orchestrator


async def main():
    """Main CLI interface"""
    print("="*80)
    print("🤖 Grivredr AI Training System")
    print("="*80)
    print()

    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Train AI to scrape government grievance portals",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli/train_cli.py abua_sathi --district ranchi
  python cli/train_cli.py ranchi_smart --district ranchi --headless
  python cli/train_cli.py mumbai_portal --district mumbai --url https://portal.mumbai.gov.in/complaint
        """
    )

    parser.add_argument('portal_name', help='Name of the portal to train')
    parser.add_argument('--district', '-d', help='District name (for organization)', default='default')
    parser.add_argument('--url', '-u', help='Portal URL (if not in known list)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--no-recording', action='store_true', help='Disable human recording fallback')

    # Hybrid Discovery Options
    parser.add_argument('--no-hybrid', action='store_true',
                       help='Disable hybrid discovery (use Playwright only)')
    parser.add_argument('--browser-use-first', action='store_true',
                       help='Try Browser Use AI first instead of Playwright')
    parser.add_argument('--no-browser-use-fallback', action='store_true',
                       help='Disable Browser Use fallback (Playwright only, even on failure)')

    args = parser.parse_args()

    municipality = args.portal_name
    district = args.district

    # Predefined URLs for known portals
    known_urls = {
        "abua_sathi": "https://www.abuasathiranchi.org/SiteController/onlinegrievance",
        "ranchi_smart": "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online",
        "ranchi_main": "https://www.ranchimunicipal.com/",
        "jharkhand_state": "https://jharkhandegovernance.com/grievance/main"
    }

    if args.url:
        url = args.url
    elif municipality in known_urls:
        url = known_urls[municipality]
    else:
        print(f"❌ Unknown portal: {municipality}")
        print(f"   Please provide URL: python cli/train_cli.py {municipality} --url <url>")
        print()
        print("Known portals:")
        for name in known_urls.keys():
            print(f"  • {name}")
        sys.exit(1)

    print(f"Portal: {municipality}")
    print(f"District: {district}")
    print(f"URL: {url}")
    print(f"Headless: {args.headless}")
    print()

    # Human recording fallback (enabled by default unless --no-recording)
    enable_recording = not args.no_recording

    # Hybrid discovery configuration
    enable_hybrid = not args.no_hybrid
    use_browser_use_first = args.browser_use_first
    browser_use_on_failure = not args.no_browser_use_fallback

    # Import DiscoveryConfig if hybrid is enabled
    hybrid_config = None
    if enable_hybrid:
        from agents.hybrid_discovery_strategy import DiscoveryConfig
        hybrid_config = DiscoveryConfig(
            use_browser_use_first=use_browser_use_first,
            browser_use_on_failure=browser_use_on_failure,
            max_playwright_attempts=2
        )

    print()
    print("🚀 Starting training...")
    if enable_recording:
        print("   (Human recording fallback enabled)")
    if enable_hybrid:
        strategy_desc = "Browser Use → Playwright" if use_browser_use_first else "Playwright → Browser Use"
        print(f"   (Hybrid discovery enabled: {strategy_desc})")
        if not browser_use_on_failure:
            print("   (Browser Use fallback disabled)")
    else:
        print("   (Playwright-only discovery)")
    print()

    # Create orchestrator
    orchestrator = Orchestrator(
        headless=args.headless,
        enable_human_recording=enable_recording,
        enable_hybrid_discovery=enable_hybrid,
        hybrid_config=hybrid_config
    )

    # Run training
    result = await orchestrator.train_municipality(
        url=url,
        municipality=municipality
    )

    # Display results
    print("\n" + "="*80)
    if result["success"]:
        print("✅ TRAINING SUCCESSFUL!")
    else:
        print("❌ TRAINING FAILED")
    print("="*80)
    print()

    print(f"Session ID: {result.get('session_id')}")
    print(f"Status: {result.get('status', 'unknown')}")

    if result["success"]:
        print(f"Scraper: {result.get('scraper_path')}")
        print(f"Total Cost: ${result.get('total_cost', 0):.4f}")
        print(f"Human Interventions: {result.get('human_interventions', 0)}")
        print(f"Session File: {result.get('session_file')}")
        print()
        print("Next steps:")
        print(f"  1. Review scraper: cat {result.get('scraper_path')}")
        print(f"  2. Run tests: pytest {result.get('scraper_path').replace('_scraper.py', '/tests/')}")
        print(f"  3. Use in production!")
    else:
        print(f"Error: {result.get('error', 'Unknown')}")
        print(f"Phase Failed: {result.get('phase_failed', 'Unknown')}")

    print()
    print("="*80)
    print("COST BREAKDOWN")
    print("="*80)

    costs = orchestrator.get_cost_breakdown()
    print(f"\nTotal Cost: ${costs['total_cost']:.4f}")

    print("\nBy Agent:")
    for agent, data in costs['by_agent'].items():
        print(f"  {agent}: ${data['cost']:.4f} ({data['count']} calls)")

    print("\nBy Model:")
    for model, data in costs['by_model'].items():
        model_short = model.split('-')[1] if '-' in model else model
        print(f"  {model_short}: ${data['cost']:.4f} ({data['count']} calls, {data['tokens']:,} tokens)")

    print()


if __name__ == "__main__":
    asyncio.run(main())
