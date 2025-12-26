#!/usr/bin/env python3
"""
End-to-End Test Script for Ranchi Municipality
Tests the complete workflow on a real website
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.orchestrator import Orchestrator
from knowledge.pattern_library import PatternLibrary


async def test_ranchi_training():
    """
    Test complete training workflow on Ranchi Smart City portal
    This is a real-world E2E test
    """

    print("\n" + "="*80)
    print("🎯 RANCHI SMART CITY - END-TO-END TEST")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # Configuration
    ranchi_url = "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online"
    municipality_name = "ranchi_e2e_test"

    print(f"\n📍 Municipality: {municipality_name}")
    print(f"🌐 URL: {ranchi_url}")
    print(f"🔧 Headless: False (visible browser for debugging)")
    print(f"📊 Dashboard: False (CLI output only)")

    # Initialize orchestrator
    orchestrator = Orchestrator(
        headless=False,  # Show browser for debugging
        dashboard_enabled=False  # CLI output only
    )

    print("\n" + "="*80)
    print("PHASE 1: FORM DISCOVERY")
    print("="*80)

    try:
        # Run training
        result = await orchestrator.train_municipality(
            url=ranchi_url,
            municipality=municipality_name
        )

        print("\n" + "="*80)
        print("TRAINING RESULT")
        print("="*80)

        if result["success"]:
            print("✅ Training completed successfully!")
            print(f"\n📋 Details:")
            print(f"   Session ID: {result['session_id']}")
            print(f"   Municipality: {result['municipality']}")
            print(f"   Scraper Path: {result['scraper_path']}")
            print(f"   Total Cost: ${result['total_cost']:.4f}")
            print(f"   Human Interventions: {result['human_interventions']}")

            # Get session details
            session = orchestrator.sessions.get(result['session_id'])
            if session:
                print(f"\n📊 Agent Attempts:")
                for agent, attempts in session.agent_attempts.items():
                    print(f"   {agent:20s}: {attempts} attempts")

                print(f"\n🔍 Discovery Results:")
                if session.discovery_result:
                    schema = session.discovery_result.get('schema', {})
                    fields = schema.get('fields', [])
                    print(f"   Fields discovered: {len(fields)}")
                    for i, field in enumerate(fields[:5], 1):  # Show first 5
                        print(f"   {i}. {field.get('label', 'N/A'):20s} ({field.get('type', 'unknown')})")
                    if len(fields) > 5:
                        print(f"   ... and {len(fields) - 5} more")

                print(f"\n🧪 Test Results:")
                if session.test_result:
                    confidence = session.test_result.get('confidence_score', 0) * 100
                    print(f"   Confidence: {confidence:.1f}%")

                print(f"\n💻 Code Generation:")
                if session.code_gen_result:
                    scraper = session.code_gen_result.get('scraper', {})
                    print(f"   Validation Passed: {scraper.get('validation_passed', False)}")
                    print(f"   Validation Attempts: {scraper.get('validation_attempts', 0)}")
                    print(f"   Confidence Score: {scraper.get('confidence_score', 0):.2f}")

            # Check pattern library
            print(f"\n📚 Pattern Library:")
            pattern_lib = PatternLibrary()
            stats = pattern_lib.get_statistics()
            print(f"   Total patterns: {stats.get('total_patterns', 0)}")
            print(f"   Avg confidence: {stats.get('avg_confidence', 0):.2f}")
            print(f"   Avg success rate: {stats.get('avg_success_rate', 0):.2f}")

            # Cost breakdown
            print(f"\n💰 Cost Breakdown:")
            cost_breakdown = orchestrator.get_cost_breakdown()
            print(f"   Total cost: ${cost_breakdown['total_cost']:.4f}")
            if cost_breakdown.get('by_model'):
                for model, cost in cost_breakdown['by_model'].items():
                    print(f"   {model:20s}: ${cost:.4f}")

            print("\n" + "="*80)
            print("NEXT STEPS")
            print("="*80)
            print(f"1. Test the generated scraper:")
            print(f"   python scripts/test_scraper.py {result['scraper_path']}")
            print(f"\n2. View the code:")
            print(f"   cat {result['scraper_path']}")
            print(f"\n3. Check session details:")
            print(f"   cat {result['session_file']}")

            return True

        else:
            print("❌ Training failed!")
            print(f"\nError: {result.get('error', 'Unknown error')}")
            if result.get('phase_failed'):
                print(f"Failed at phase: {result['phase_failed']}")
            if result.get('reason'):
                print(f"Reason: {result['reason']}")

            return False

    except KeyboardInterrupt:
        print("\n\n⚠️ Training interrupted by user")
        return False

    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        print(f"\n⏱️  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)


async def test_generated_scraper(scraper_path: str):
    """
    Test a generated scraper with dummy data
    """
    print("\n" + "="*80)
    print("🧪 TESTING GENERATED SCRAPER")
    print("="*80)

    scraper_path = Path(scraper_path)
    if not scraper_path.exists():
        print(f"❌ Scraper file not found: {scraper_path}")
        return False

    print(f"📄 Scraper: {scraper_path}")

    # Dynamically import the scraper
    import importlib.util
    spec = importlib.util.spec_from_file_location("test_scraper", scraper_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find scraper class
    scraper_class = None
    for name in dir(module):
        if name.endswith('Scraper') and not name.startswith('_'):
            scraper_class = getattr(module, name)
            break

    if not scraper_class:
        print("❌ Could not find scraper class in module")
        return False

    print(f"✅ Found scraper class: {scraper_class.__name__}")

    # Test data
    test_data = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "9876543210",
        "address": "Test Address, Ranchi",
        "complaint": "This is a test complaint for validation purposes.",
        "category": "Street Light"
    }

    print(f"\n🧪 Running test mode...")
    print(f"Test data: {json.dumps(test_data, indent=2)}")

    try:
        scraper = scraper_class()

        # Run in test mode
        result = await scraper.run_test_mode(test_data)

        print(f"\n📊 Test Result:")
        print(json.dumps(result, indent=2))

        if result.get("success"):
            print(f"\n✅ Scraper test PASSED")
            return True
        else:
            print(f"\n❌ Scraper test FAILED")
            print(f"Errors: {result.get('errors', [])}")
            return False

    except Exception as e:
        print(f"\n❌ Error running scraper: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test Ranchi municipality training")
    parser.add_argument(
        "--test-scraper",
        type=str,
        help="Path to scraper to test (instead of training)"
    )
    args = parser.parse_args()

    if args.test_scraper:
        # Test existing scraper
        success = await test_generated_scraper(args.test_scraper)
    else:
        # Run training
        success = await test_ranchi_training()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
