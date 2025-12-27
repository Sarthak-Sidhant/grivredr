#!/usr/bin/env python3
"""
CLI Tool for Automatic Form Filling using Browser Use AI
"""
import asyncio
import sys
import argparse
import json
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from browser_use import Agent, Browser, ChatAnthropic
from browser_use.browser import BrowserProfile
from dotenv import load_dotenv

load_dotenv()


async def fill_form(url: str, data: dict, headless: bool = True, max_steps: int = 30):
    """Fill a grievance form automatically using browser-use AI"""

    api_key = os.getenv("api_key")
    if not api_key:
        print("Error: api_key not found in environment variables")
        sys.exit(1)

    llm = ChatAnthropic(
        model='claude-sonnet-4-5-20250929',
        temperature=0.0,
        api_key=api_key,
        base_url="https://ai.megallm.io"
    )

    profile = BrowserProfile(
        headless=headless,
        enable_default_extensions=False,
        wait_for_network_idle_page_load_time=3.0,
        minimum_wait_page_load_time=1.0,
    )

    browser = Browser(browser_profile=profile)

    initial_actions = [
        {"navigate": {"url": url}},
    ]

    # Build dynamic task based on provided data
    field_list = "\n".join([f"- {k}: {v}" for k, v in data.items()])

    task = f"""You are an AI assistant that fills out grievance/complaint forms automatically.

The form is now loaded. Your task is to fill ALL fields with the following data:

{field_list}

**Instructions:**
1. Wait for the page to fully load
2. For dropdown fields, click on them and search/select the appropriate option
3. For text fields, click and type the value
4. Fill ALL fields in order from top to bottom
5. After filling all fields, DO NOT submit the form - just report that filling is complete
6. If a field doesn't accept the exact value, choose the closest matching option
7. Report which fields were successfully filled and any issues encountered."""

    print("Starting form filling...")
    print(f"URL: {url}")
    print(f"Headless: {headless}")
    print(f"Max steps: {max_steps}")
    print()

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        initial_actions=initial_actions,
    )

    result = await agent.run(max_steps=max_steps)
    return result


async def main():
    """Main CLI interface"""
    print("="*80)
    print("Grivredr Form Filler")
    print("="*80)
    print()

    parser = argparse.ArgumentParser(
        description="Automatically fill grievance forms using AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fill form with JSON data file
  python cli/fill_cli.py --url https://example.com/form --data grievance.json

  # Fill form with inline data
  python cli/fill_cli.py --url https://example.com/form \\
    --field "name=John Doe" \\
    --field "email=john@example.com" \\
    --field "complaint=Street light not working"

  # Use predefined portal with sample data
  python cli/fill_cli.py --portal mcd_delhi --sample
        """
    )

    parser.add_argument('--url', '-u', help='Form URL to fill')
    parser.add_argument('--portal', '-p', help='Use predefined portal URL')
    parser.add_argument('--data', '-d', help='JSON file with form data')
    parser.add_argument('--field', '-f', action='append', help='Field in format "name=value"')
    parser.add_argument('--sample', '-s', action='store_true', help='Use sample grievance data')
    parser.add_argument('--headless', action='store_true', default=True, help='Run in headless mode (default)')
    parser.add_argument('--no-headless', action='store_true', help='Run with visible browser')
    parser.add_argument('--max-steps', type=int, default=30, help='Maximum AI steps (default: 30)')
    parser.add_argument('--submit', action='store_true', help='Submit the form after filling (use with caution)')

    args = parser.parse_args()

    # Predefined portals
    known_portals = {
        "mcd_delhi": "https://mcd.everythingcivic.com/citizen/createissue?app_id=U2FsdGVkX180J3mGnJmT5QpgtPjhfjtzyXAAccBUxGU%3D&api_key=e34ba86d3943bd6db9120313da011937189e6a9625170905750f649395bcd68312cf10d264c9305d57c23688cc2e5120",
        "jharkhand": "https://jharkhandegovernance.com/grievance/main",
    }

    # Sample data
    sample_data = {
        "category": "Garbage",
        "sub_category": "Garbage Not Lifted",
        "subject": "Garbage accumulation near residential area",
        "description": "There is a large pile of garbage that has been accumulating near the main road for the past 5 days. It is causing a foul smell and attracting stray animals. Please arrange for immediate clearance.",
        "address": "123 Main Street, Near Metro Station, Sector 5",
        "zone": "Central Zone",
        "ward": "Ward 10",
        "landmark": "Opposite City Mall",
        "first_name": "Rahul",
        "last_name": "Sharma",
        "mobile": "9876543210",
        "email": "rahul.sharma@example.com"
    }

    # Determine URL
    if args.url:
        url = args.url
    elif args.portal:
        if args.portal in known_portals:
            url = known_portals[args.portal]
        else:
            print(f"Unknown portal: {args.portal}")
            print("Known portals:")
            for name in known_portals.keys():
                print(f"  - {name}")
            sys.exit(1)
    else:
        print("Error: Please provide --url or --portal")
        parser.print_help()
        sys.exit(1)

    # Determine form data
    form_data = {}

    if args.sample:
        form_data = sample_data
        print("Using sample grievance data")
    elif args.data:
        with open(args.data, 'r') as f:
            form_data = json.load(f)
        print(f"Loaded data from {args.data}")
    elif args.field:
        for field in args.field:
            if '=' in field:
                key, value = field.split('=', 1)
                form_data[key.strip()] = value.strip()
            else:
                print(f"Invalid field format: {field}")
                print("Use format: --field 'name=value'")
                sys.exit(1)
    else:
        print("Error: Please provide form data via --data, --field, or --sample")
        parser.print_help()
        sys.exit(1)

    if not form_data:
        print("Error: No form data provided")
        sys.exit(1)

    # Determine headless mode
    headless = not args.no_headless

    print()
    print("Form Data:")
    print(json.dumps(form_data, indent=2))
    print()

    # Run form filler
    try:
        result = await fill_form(
            url=url,
            data=form_data,
            headless=headless,
            max_steps=args.max_steps
        )

        print()
        print("="*80)
        print("Form filling completed!")
        print("="*80)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
