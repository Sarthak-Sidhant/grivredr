#!/usr/bin/env python3
"""
Test Lucknow portal using browser-use AI discovery
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings, BrowserType, AIProvider
from config.multi_provider_client import ai_client
from agents.orchestrator import Orchestrator
from agents.hybrid_discovery_strategy import DiscoveryConfig


async def test_with_browser_use():
    """Test training using browser-use first"""

    print("=" * 70)
    print("Grivredr - Browser-First Discovery Test")
    print("=" * 70)
    print()

    # Configure browser-use FIRST (skip Playwright)
    hybrid_config = DiscoveryConfig(
        use_browser_use_first=True,  # Use AI first
        browser_use_on_failure=True,
        max_playwright_attempts=0,  # Skip Playwright entirely
    )

    print("📋 Configuration:")
    print(f"  Portal: lucknow_civic")
    print(f"  District: lucknow")
    print(f"  URL: https://lucknow.everythingcivic.com/citizen/createissue")
    print(f"  Discovery: Browser-Use AI (Playwright skipped)")
    print()

    print("🤖 AI Providers:")
    providers = ai_client.list_available_providers()
    for provider in providers:
        print(f"  • {provider.value}")
    print()

    print("=" * 70)
    print("Starting Training with Browser-Use AI...")
    print("=" * 70)
    print()

    try:
        # Create orchestrator with browser-use first config
        orchestrator = Orchestrator(
            browser_type="chromium",
            headless=True,
            enable_hybrid_discovery=True,
            hybrid_config=hybrid_config
        )

        # Train using browser-use
        result = await orchestrator.train_municipality(
            municipality="lucknow",
            url="https://lucknow.everythingcivic.com/citizen/createissue?app_id=U2FsdGVkX19DXfobm%2FotGurZKmAQkKPuX%2FzqxfvVbww%3D&amp;api_key=48bfcdd83a901e08200a687ded15432f7da69f73a5f429d0cd536d77107b6b24a3dcec0e7b33418490d6d19a2b58a367"
        )

        print()
        print("=" * 70)
        print("✅ Training Completed!")
        print("=" * 70)
        print()
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Confidence: {result.get('confidence', 0):.2f}")
        print(f"Output: {result.get('output_path', 'N/A')}")
        print()

        cost = result.get('total_cost', 0)
        print(f"💰 Total Cost: ${cost:.2f}")
        print()

        return result

    except Exception as e:
        print()
        print("=" * 70)
        print("❌ Training Failed!")
        print("=" * 70)
        print()
        print(f"Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    try:
        result = asyncio.run(test_with_browser_use())

        if result and result.get('success'):
            print("\n🎉 Success! Check outputs/generated_scrapers/ for scraper.")
            sys.exit(0)
        elif result:
            print(f"\n⚠️  Training completed with status: {result.get('status')}")
            sys.exit(0)
        else:
            print("\n❌ Training failed.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Training cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
