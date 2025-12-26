#!/usr/bin/env python3
"""
System Validation Script
Runs comprehensive tests to validate Grivredr system is working correctly
"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class SystemValidator:
    """Validates all components of the Grivredr system"""

    def __init__(self):
        self.results = {
            "unit_tests": {"status": "pending", "details": {}},
            "integration_tests": {"status": "pending", "details": {}},
            "component_checks": {"status": "pending", "details": {}},
            "dependencies": {"status": "pending", "details": {}}
        }

    def check_dependencies(self) -> bool:
        """Check that all required dependencies are installed"""
        print("\n" + "="*80)
        print("CHECKING DEPENDENCIES")
        print("="*80)

        required_packages = {
            "playwright": "Browser automation",
            "flask": "Dashboard backend",
            "flask_socketio": "Real-time updates",
            "pytest": "Testing framework",
            "openai": "AI client",
            "python-dotenv": "Environment variables"
        }

        all_installed = True
        for package, description in required_packages.items():
            try:
                __import__(package)
                print(f"✅ {package:20s} - {description}")
                self.results["dependencies"]["details"][package] = True
            except ImportError:
                print(f"❌ {package:20s} - MISSING - {description}")
                self.results["dependencies"]["details"][package] = False
                all_installed = False

        if all_installed:
            self.results["dependencies"]["status"] = "passed"
            print("\n✅ All dependencies installed")
        else:
            self.results["dependencies"]["status"] = "failed"
            print("\n❌ Some dependencies missing - run: pip install -r requirements.txt")

        return all_installed

    def check_components(self) -> bool:
        """Check that all components are properly configured"""
        print("\n" + "="*80)
        print("CHECKING COMPONENTS")
        print("="*80)

        components = {
            "agents/base_agent.py": "Base agent with reflection",
            "agents/form_discovery_agent.py": "Form discovery + JS monitoring",
            "agents/code_generator_agent.py": "Code generation + validation",
            "utils/scraper_validator.py": "Scraper validation",
            "utils/js_runtime_monitor.py": "JS runtime monitoring",
            "knowledge/pattern_library.py": "Pattern library",
            "dashboard/app.py": "Dashboard application",
            "config/ai_client.py": "AI client with enhanced prompts"
        }

        all_exist = True
        project_root = Path(__file__).parent.parent

        for component, description in components.items():
            component_path = project_root / component
            if component_path.exists():
                print(f"✅ {component:40s} - {description}")
                self.results["component_checks"]["details"][component] = True
            else:
                print(f"❌ {component:40s} - MISSING - {description}")
                self.results["component_checks"]["details"][component] = False
                all_exist = False

        if all_exist:
            self.results["component_checks"]["status"] = "passed"
            print("\n✅ All components present")
        else:
            self.results["component_checks"]["status"] = "failed"
            print("\n❌ Some components missing")

        return all_exist

    async def run_unit_tests(self) -> bool:
        """Run unit tests"""
        print("\n" + "="*80)
        print("RUNNING UNIT TESTS")
        print("="*80)

        try:
            import pytest
            exit_code = pytest.main([
                "tests/unit/",
                "-v",
                "--tb=short",
                "-x"  # Stop on first failure
            ])

            if exit_code == 0:
                print("\n✅ All unit tests passed")
                self.results["unit_tests"]["status"] = "passed"
                return True
            else:
                print(f"\n❌ Unit tests failed with exit code {exit_code}")
                self.results["unit_tests"]["status"] = "failed"
                return False

        except Exception as e:
            print(f"\n❌ Error running unit tests: {e}")
            self.results["unit_tests"]["status"] = "error"
            self.results["unit_tests"]["details"]["error"] = str(e)
            return False

    async def run_integration_tests(self) -> bool:
        """Run integration tests"""
        print("\n" + "="*80)
        print("RUNNING INTEGRATION TESTS")
        print("="*80)

        try:
            import pytest
            exit_code = pytest.main([
                "tests/integration/",
                "-v",
                "--tb=short",
                "-x"
            ])

            if exit_code == 0:
                print("\n✅ All integration tests passed")
                self.results["integration_tests"]["status"] = "passed"
                return True
            else:
                print(f"\n❌ Integration tests failed with exit code {exit_code}")
                self.results["integration_tests"]["status"] = "failed"
                return False

        except Exception as e:
            print(f"\n❌ Error running integration tests: {e}")
            self.results["integration_tests"]["status"] = "error"
            self.results["integration_tests"]["details"]["error"] = str(e)
            return False

    def print_summary(self):
        """Print validation summary"""
        print("\n" + "="*80)
        print("VALIDATION SUMMARY")
        print("="*80)

        categories = [
            ("Dependencies", self.results["dependencies"]["status"]),
            ("Components", self.results["component_checks"]["status"]),
            ("Unit Tests", self.results["unit_tests"]["status"]),
            ("Integration Tests", self.results["integration_tests"]["status"])
        ]

        all_passed = True
        for category, status in categories:
            icon = "✅" if status == "passed" else "❌" if status == "failed" else "⚠️"
            print(f"{icon} {category:20s}: {status.upper()}")
            if status != "passed":
                all_passed = False

        print("="*80)

        if all_passed:
            print("\n🎉 SYSTEM VALIDATION COMPLETE - ALL CHECKS PASSED!")
            print("\nNext steps:")
            print("1. Test on real municipality: python scripts/test_ranchi.py")
            print("2. Start dashboard: python dashboard/app.py")
            print("3. Run orchestrator: python agents/orchestrator.py")
        else:
            print("\n⚠️ SYSTEM VALIDATION INCOMPLETE - Some checks failed")
            print("\nPlease address the issues above before proceeding.")

        return all_passed

    async def validate(self) -> bool:
        """Run complete system validation"""
        print("\n" + "="*80)
        print("🔍 GRIVREDR SYSTEM VALIDATION")
        print("="*80)

        # Step 1: Check dependencies
        deps_ok = self.check_dependencies()
        if not deps_ok:
            print("\n⚠️ Skipping tests due to missing dependencies")
            self.print_summary()
            return False

        # Step 2: Check components
        components_ok = self.check_components()
        if not components_ok:
            print("\n⚠️ Skipping tests due to missing components")
            self.print_summary()
            return False

        # Step 3: Run unit tests
        await self.run_unit_tests()

        # Step 4: Run integration tests
        await self.run_integration_tests()

        # Print summary
        return self.print_summary()


async def main():
    """Main entry point"""
    validator = SystemValidator()
    success = await validator.validate()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
