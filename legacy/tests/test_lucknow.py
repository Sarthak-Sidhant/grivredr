#!/usr/bin/env python3
"""
Direct training script for Lucknow portal testing
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings, BrowserType, AIProvider
from config.multi_provider_client import ai_client
from agents.orchestrator import Orchestrator


async def test_lucknow_portal():
    """Test training on Lucknow portal"""

    print("=" * 70)
    print("Grivredr - Testing New Features")
    print("=" * 70)
    print()

    # Display configuration
    print("📋 Configuration:")
    print(f"  Portal: lucknow_civic")
    print(f"  District: lucknow")
    print(
        f"  URL: https://lucknow.everythingcivic.com/citizen/createissue?app_id=U2FsdGVkX19DXfobm%2FotGurZKmAQkKPuX%2FzqxfvVbww%3D&amp;api_key=48bfcdd83a901e08200a687ded15432f7da69f73a5f429d0cd536d77107b6b24a3dcec0e7b33418490d6d19a2b58a367"
    )
    print(f"  Browser: {settings.browser.browser_type}")
    print(f"  Headless: {settings.browser.headless}")
    print()

    # Show AI providers
    print("🤖 AI Providers:")
    providers = ai_client.list_available_providers()
    for provider in providers:
        print(f"  • {provider.value}")
    print()

    # Show model configuration
    print("⚙️  Task Models:")
    from config.settings import TaskType

    for task in TaskType:
        model_config = settings.get_model_for_task(task)
        print(
            f"  {task.value:25s} → {model_config.provider.value:12s} {model_config.model_name}"
        )
    print()

    print("=" * 70)
    print("Starting Training...")
    print("=" * 70)
    print()

    try:
        # Create orchestrator with browser from settings
        orchestrator = Orchestrator(
            browser_type=settings.browser.browser_type.value,
            headless=settings.browser.headless,
        )

        # Callback for progress
        def on_progress(message: str, progress: float = 0.0):
            print(f"  [{progress:5.1f}%] {message}")

        # Train portal
        result = await orchestrator.train_municipality(
            municipality="lucknow",
            url="https://lucknow.everythingcivic.com/citizen/createissue?app_id=U2FsdGVkX19DXfobm%2FotGurZKmAQkKPuX%2FzqxfvVbww%3D&amp;api_key=48bfcdd83a901e08200a687ded15432f7da69f73a5f429d0cd536d77107b6b24a3dcec0e7b33418490d6d19a2b58a367",
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

        # Show cost breakdown
        cost = result.get("total_cost", 0)
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
        result = asyncio.run(test_lucknow_portal())

        if result and result.get("success"):
            print("\n🎉 Success! Check outputs/generated_scrapers/ for the scraper.")
            sys.exit(0)
        else:
            print("\n⚠️  Training completed but may have issues.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Training cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
