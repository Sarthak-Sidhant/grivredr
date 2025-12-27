#!/usr/bin/env python3
"""
Factory CLI - Command-line interface for the scraper factory

Commands:
    discover    - Discover and analyze a portal form
    validate    - Validate a scraper with self-healing fixes
    improve     - Continuously improve a scraper until satisfactory
    test        - Run dry-run test on a scraper
    list        - List all portals and their status
    patterns    - Show available patterns in the library
    context     - Show context for a portal
    detect      - Detect UI framework from URL
    migrate     - Migrate old scrapers to new structure
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def cmd_discover(args):
    """Discover a portal form"""
    from agents.hybrid_form_discovery import HybridFormDiscovery

    print(f"\n{'='*60}")
    print(f"GRIVREDR SCRAPER FACTORY - Discovery")
    print(f"{'='*60}")
    print(f"URL: {args.url}")
    print(f"Portal: {args.state}/{args.district}/{args.portal}")
    print(f"{'='*60}\n")

    async def run_discovery():
        discovery = HybridFormDiscovery()
        scraper_path = await discovery.run(
            url=args.url,
            portal_name=args.portal,
            headless=not args.visible,
            state=args.state,
            district=args.district
        )
        return scraper_path

    try:
        scraper_path = asyncio.run(run_discovery())
        print(f"\n✅ Scraper generated: {scraper_path}")
        return 0
    except Exception as e:
        print(f"\n❌ Discovery failed: {e}")
        return 1


def cmd_list(args):
    """List all portals"""
    from utils.portal_manager import PortalManager

    pm = PortalManager()
    portals = pm.list_portals(state=args.state)

    if not portals:
        print("No portals found.")
        if args.state:
            print(f"  (filtered by state: {args.state})")
        return 0

    print(f"\n{'='*60}")
    print(f"PORTALS ({len(portals)} total)")
    print(f"{'='*60}\n")

    # Group by state
    by_state = {}
    for p in portals:
        state = p["state"]
        if state not in by_state:
            by_state[state] = []
        by_state[state].append(p)

    for state, state_portals in sorted(by_state.items()):
        print(f"📍 {state.upper()}")
        for p in state_portals:
            scraper_exists = (Path(p["path"]) / "scraper.py").exists()
            status = "✅" if scraper_exists else "⚠️"
            print(f"   {status} {p['district']}/{p['portal']}")
        print()

    return 0


def cmd_patterns(args):
    """Show available patterns"""
    from knowledge.pattern_library import PatternLibrary

    print(f"\n{'='*60}")
    print(f"PATTERN LIBRARY")
    print(f"{'='*60}\n")

    try:
        pl = PatternLibrary(enable_vector_store=False)
        stats = pl.get_statistics()

        print(f"Total patterns: {stats['total_patterns']}")
        print(f"Avg confidence: {stats['avg_confidence']:.0%}")
        print(f"Avg success rate: {stats['avg_success_rate']:.0%}")
        print(f"Vector store: {'enabled' if stats['vector_store_enabled'] else 'disabled'}")

        # Show available templates
        print(f"\n{'='*60}")
        print(f"CODE TEMPLATES")
        print(f"{'='*60}\n")

        try:
            from knowledge.code_templates import TEMPLATE_REGISTRY, UIFramework

            for framework, templates in TEMPLATE_REGISTRY.items():
                print(f"📦 {framework.value}")
                for name, template in templates.items():
                    print(f"   • {name}: {template.description[:50]}...")
                print()
        except ImportError:
            print("Code templates module not available")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def cmd_migrate(args):
    """Migrate old scrapers to new structure"""
    from utils.portal_manager import PortalManager

    print(f"\n{'='*60}")
    print(f"MIGRATING OLD STRUCTURE")
    print(f"{'='*60}\n")

    if not args.yes:
        confirm = input("This will copy scrapers to new structure. Continue? [y/N] ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return 0

    pm = PortalManager()
    report = pm.migrate_old_structure()

    print(f"\nMigration complete!")
    print(f"  Migrated: {len(report['migrated'])}")
    print(f"  Errors: {len(report['errors'])}")
    print(f"  Skipped: {len(report['skipped'])}")

    if report['errors']:
        print("\nErrors:")
        for err in report['errors'][:5]:
            print(f"  ❌ {err}")

    return 0


def cmd_context(args):
    """Show context for a portal"""
    from utils.portal_manager import PortalManager

    pm = PortalManager()
    context = pm.load_context(args.state, args.district, args.portal)

    if not context:
        print(f"No context found for {args.state}/{args.district}/{args.portal}")
        return 1

    print(f"\n{'='*60}")
    print(f"CONTEXT: {args.state}/{args.district}/{args.portal}")
    print(f"{'='*60}\n")

    if "structure" in context:
        fields = context["structure"].get("fields", [])
        print(f"📋 Fields: {len(fields)}")
        for f in fields[:10]:
            req = "✓" if f.get("required") else " "
            print(f"   [{req}] {f.get('name', 'unnamed')} ({f.get('type', 'text')})")
        if len(fields) > 10:
            print(f"   ... and {len(fields) - 10} more")
        print()

    if "dropdowns" in context:
        print(f"🔽 Dropdowns: {len(context['dropdowns'])}")
        for name, dropdown in list(context["dropdowns"].items())[:5]:
            options = dropdown.get("options", {})
            print(f"   • {name}: {len(options)} options")
        print()

    if "cascades" in context:
        print(f"🔗 Cascades: {len(context['cascades'])}")
        for name, cascade in context["cascades"].items():
            print(f"   • {cascade.get('parent_field', '?')} → {cascade.get('child_field', '?')}")
        print()

    return 0


def cmd_validate(args):
    """Validate a scraper with self-healing loop"""
    from agents.scraper_validator import ScraperValidator
    from utils.portal_manager import PortalManager

    print(f"\n{'='*60}")
    print(f"SCRAPER VALIDATION")
    print(f"{'='*60}")
    print(f"Scraper: {args.scraper}")
    print(f"Max attempts: {args.max_attempts}")
    print(f"{'='*60}\n")

    # Load portal context if available
    portal_context = None
    if args.state and args.district and args.portal:
        try:
            pm = PortalManager()
            portal_context = pm.load_context(args.state, args.district, args.portal)
        except:
            pass

    # Build test data
    test_data = {}
    if args.test_data:
        try:
            test_data = json.loads(args.test_data)
        except:
            print(f"Warning: Could not parse test data JSON")

    # Use default test data if none provided
    if not test_data:
        test_data = {
            "name": "Test User",
            "mobile": "9876543210",
            "email": "test@example.com",
            "address": "123 Test Street"
        }

        # Add dropdown values from context
        if portal_context and "dropdowns" in portal_context:
            for field_name, dropdown_info in portal_context["dropdowns"].items():
                options = dropdown_info.get("options", {})
                for opt_text in options.keys():
                    if opt_text not in ["--Select--", "--Not Set--", ""]:
                        test_data[field_name.lower().replace(" ", "_")] = opt_text
                        break

    async def run_validation():
        validator = ScraperValidator(
            max_attempts=args.max_attempts,
            headless=not args.visible
        )

        success, final_path, history = await validator.validate_scraper(
            scraper_path=args.scraper,
            test_data=test_data,
            portal_context=portal_context,
            dry_run=not args.submit
        )

        print(validator.get_summary())
        return success, final_path

    try:
        success, final_path = asyncio.run(run_validation())
        return 0 if success else 1
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_improve(args):
    """Continuously improve a scraper"""
    from agents.continuous_improvement_agent import ContinuousImprovementAgent, TestCase
    from utils.portal_manager import PortalManager

    print(f"\n{'='*60}")
    print(f"CONTINUOUS IMPROVEMENT")
    print(f"{'='*60}")
    print(f"Scraper: {args.scraper}")
    print(f"Target success rate: {args.target}%")
    print(f"Max cycles: {args.max_cycles}")
    print(f"Max cost: ${args.max_cost}")
    print(f"{'='*60}\n")

    # Load portal context
    portal_context = None
    if args.state and args.district and args.portal:
        try:
            pm = PortalManager()
            portal_context = pm.load_context(args.state, args.district, args.portal)
        except:
            pass

    async def run_improvement():
        agent = ContinuousImprovementAgent(
            max_cycles=args.max_cycles,
            target_success_rate=args.target / 100.0,
            max_cost=args.max_cost,
            headless=not args.visible
        )

        # Generate test cases from context
        if portal_context:
            test_cases = agent.generate_test_cases(portal_context)
        else:
            test_cases = [
                TestCase(
                    name="Basic test",
                    data={
                        "name": "Test User",
                        "mobile": "9876543210",
                        "email": "test@example.com"
                    },
                    priority=1
                )
            ]

        success, final_path, metrics = await agent.improve_scraper(
            scraper_path=args.scraper,
            test_cases=test_cases,
            portal_context=portal_context
        )

        # Save report
        report = agent.get_report()
        report_path = Path(args.scraper).parent / "improvement_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {report_path}")

        return success

    try:
        success = asyncio.run(run_improvement())
        return 0 if success else 1
    except Exception as e:
        print(f"\n❌ Improvement failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_test(args):
    """Run dry-run test on a scraper"""
    from agents.scraper_validator import ScraperValidator
    from utils.portal_manager import PortalManager

    print(f"\n{'='*60}")
    print(f"DRY RUN TEST")
    print(f"{'='*60}")
    print(f"Scraper: {args.scraper}")
    print(f"{'='*60}\n")

    # Load portal context
    portal_context = None
    if args.state and args.district and args.portal:
        try:
            pm = PortalManager()
            portal_context = pm.load_context(args.state, args.district, args.portal)
        except:
            pass

    # Build test data
    test_data = {}
    if args.test_data:
        try:
            test_data = json.loads(args.test_data)
        except:
            print(f"Warning: Could not parse test data JSON")

    if not test_data:
        test_data = {
            "name": "Test User",
            "mobile": "9876543210",
            "email": "test@example.com",
            "address": "123 Test Street"
        }

        if portal_context and "dropdowns" in portal_context:
            for field_name, dropdown_info in portal_context["dropdowns"].items():
                options = dropdown_info.get("options", {})
                for opt_text in options.keys():
                    if opt_text not in ["--Select--", "--Not Set--", ""]:
                        test_data[field_name.lower().replace(" ", "_")] = opt_text
                        break

    async def run_test():
        validator = ScraperValidator(
            max_attempts=1,  # Just one attempt for dry run
            headless=not args.visible
        )

        report = await validator.dry_run(
            scraper_path=args.scraper,
            test_data=test_data
        )

        print(f"\n{'='*60}")
        print("TEST RESULTS")
        print(f"{'='*60}")
        print(f"Success: {'✅ PASSED' if report['success'] else '❌ FAILED'}")
        print(f"Cost: ${report['total_cost']:.4f}")

        if not report['success'] and report['validation_history']:
            last = report['validation_history'][-1]
            if last.get('error'):
                print(f"Error: {last['error'][:100]}")
            if last.get('screenshot'):
                print(f"Screenshot: {last['screenshot']}")

        return report['success']

    try:
        success = asyncio.run(run_test())
        return 0 if success else 1
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_detect(args):
    """Detect UI framework from URL"""
    print(f"\n{'='*60}")
    print(f"FRAMEWORK DETECTION")
    print(f"{'='*60}\n")
    print(f"URL: {args.url}")

    async def run_detection():
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            print("Loading page...")
            await page.goto(args.url, wait_until="networkidle", timeout=30000)

            html = await page.content()
            await browser.close()

            return html

    try:
        html = asyncio.run(run_detection())

        from knowledge.framework_detector import detect_framework

        result = detect_framework(html_content=html)

        print(f"\n✅ Primary framework: {result.primary_framework.value}")
        print(f"   Confidence: {result.confidence:.0%}")

        if result.detected_frameworks:
            print(f"\n   All detected: {', '.join(f.value for f in result.detected_frameworks)}")

        if result.recommendations:
            print(f"\n📋 Recommendations:")
            for rec in result.recommendations[:5]:
                print(f"   • {rec}")

        if result.evidence:
            print(f"\n🔍 Evidence:")
            for framework, evidence in list(result.evidence.items())[:3]:
                print(f"   {framework}: {', '.join(evidence[:3])}")

    except Exception as e:
        print(f"\n❌ Detection failed: {e}")
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Grivredr Scraper Factory CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover and generate scraper for a new portal
  python factory_cli.py discover --url "https://portal.example.com/form" \\
      --portal my_portal --state jharkhand --district ranchi

  # Validate a scraper with self-healing (fix errors automatically)
  python factory_cli.py validate --scraper scrapers/my_portal/my_portal_scraper.py \\
      --state jharkhand --district ranchi --portal my_portal

  # Continuously improve a scraper until 90% success rate
  python factory_cli.py improve --scraper scrapers/my_portal/my_portal_scraper.py \\
      --target 90 --max-cycles 5 --max-cost 2.0

  # Run a dry-run test (fill form but don't submit)
  python factory_cli.py test --scraper scrapers/my_portal/my_portal_scraper.py --visible

  # List all portals
  python factory_cli.py list

  # Show portal context (dropdown options, cascades)
  python factory_cli.py context --state jharkhand --district ranchi --portal ranchi_smart

  # Detect UI framework for a URL
  python factory_cli.py detect --url "https://portal.example.com"

  # Migrate old scrapers to new structure
  python factory_cli.py migrate --yes
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # discover command
    discover_parser = subparsers.add_parser("discover", help="Discover a portal form")
    discover_parser.add_argument("--url", required=True, help="URL of the form")
    discover_parser.add_argument("--portal", required=True, help="Portal name")
    discover_parser.add_argument("--state", default="unknown", help="State name")
    discover_parser.add_argument("--district", default="unknown", help="District name")
    discover_parser.add_argument("--visible", action="store_true", help="Show browser window")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a scraper with self-healing")
    validate_parser.add_argument("--scraper", required=True, help="Path to scraper file")
    validate_parser.add_argument("--max-attempts", type=int, default=3, help="Max fix attempts (default: 3)")
    validate_parser.add_argument("--state", help="State name (for context)")
    validate_parser.add_argument("--district", help="District name (for context)")
    validate_parser.add_argument("--portal", help="Portal name (for context)")
    validate_parser.add_argument("--test-data", help="JSON test data")
    validate_parser.add_argument("--visible", action="store_true", help="Show browser window")
    validate_parser.add_argument("--submit", action="store_true", help="Actually submit form (not dry-run)")

    # improve command
    improve_parser = subparsers.add_parser("improve", help="Continuously improve a scraper")
    improve_parser.add_argument("--scraper", required=True, help="Path to scraper file")
    improve_parser.add_argument("--target", type=int, default=90, help="Target success rate %% (default: 90)")
    improve_parser.add_argument("--max-cycles", type=int, default=5, help="Max improvement cycles (default: 5)")
    improve_parser.add_argument("--max-cost", type=float, default=2.0, help="Max cost in $ (default: 2.0)")
    improve_parser.add_argument("--state", help="State name (for context)")
    improve_parser.add_argument("--district", help="District name (for context)")
    improve_parser.add_argument("--portal", help="Portal name (for context)")
    improve_parser.add_argument("--visible", action="store_true", help="Show browser window")

    # test command (dry-run)
    test_parser = subparsers.add_parser("test", help="Run dry-run test on a scraper")
    test_parser.add_argument("--scraper", required=True, help="Path to scraper file")
    test_parser.add_argument("--state", help="State name (for context)")
    test_parser.add_argument("--district", help="District name (for context)")
    test_parser.add_argument("--portal", help="Portal name (for context)")
    test_parser.add_argument("--test-data", help="JSON test data")
    test_parser.add_argument("--visible", action="store_true", help="Show browser window")

    # list command
    list_parser = subparsers.add_parser("list", help="List all portals")
    list_parser.add_argument("--state", help="Filter by state")

    # patterns command
    patterns_parser = subparsers.add_parser("patterns", help="Show available patterns")

    # migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate old structure")
    migrate_parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    # context command
    context_parser = subparsers.add_parser("context", help="Show portal context")
    context_parser.add_argument("--state", required=True, help="State name")
    context_parser.add_argument("--district", required=True, help="District name")
    context_parser.add_argument("--portal", required=True, help="Portal name")

    # detect command
    detect_parser = subparsers.add_parser("detect", help="Detect UI framework")
    detect_parser.add_argument("--url", required=True, help="URL to analyze")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Route to command handler
    commands = {
        "discover": cmd_discover,
        "validate": cmd_validate,
        "improve": cmd_improve,
        "test": cmd_test,
        "list": cmd_list,
        "patterns": cmd_patterns,
        "migrate": cmd_migrate,
        "context": cmd_context,
        "detect": cmd_detect,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
