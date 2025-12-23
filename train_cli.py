#!/usr/bin/env python3
"""
CLI Tool for Training AI Agents on Municipal Websites
"""
import asyncio
import sys
from agents.orchestrator import Orchestrator


async def main():
    """Main CLI interface"""
    print("="*80)
    print("🤖 Grivredr AI Training System")
    print("="*80)
    print()

    if len(sys.argv) < 2:
        print("Usage: python train_cli.py <municipality_name> [url]")
        print()
        print("Examples:")
        print("  python train_cli.py ranchi_smart")
        print("  python train_cli.py patna https://patna.gov.in/complaint")
        print()
        sys.exit(1)

    municipality = sys.argv[1]

    # Predefined URLs for known municipalities
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
        print(f"   Please provide URL: python train_cli.py {municipality} <url>")
        sys.exit(1)

    print(f"Municipality: {municipality}")
    print(f"URL: {url}")
    print()

    # Ask for headless mode
    headless_input = input("Run in headless mode? (y/N): ").strip().lower()
    headless = headless_input == 'y'

    print()
    print("🚀 Starting training...")
    print()

    # Create orchestrator
    orchestrator = Orchestrator(headless=headless)

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
