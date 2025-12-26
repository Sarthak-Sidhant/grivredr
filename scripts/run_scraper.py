#!/usr/bin/env python3
"""
Production Scraper Runner with Health Monitoring
Wraps scraper execution with automatic health tracking and alerting
"""
import asyncio
import sys
import json
import time
import importlib.util
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from monitoring.health_monitor import HealthMonitor
from monitoring.alerting import AlertManager


class ScraperRunner:
    """
    Production scraper runner with health monitoring
    """

    def __init__(
        self,
        scraper_path: str,
        enable_monitoring: bool = True,
        enable_alerting: bool = True
    ):
        self.scraper_path = Path(scraper_path)
        self.scraper_id = self.scraper_path.stem
        self.scraper_class = None

        # Monitoring
        self.enable_monitoring = enable_monitoring
        self.enable_alerting = enable_alerting

        if self.enable_monitoring:
            self.health_monitor = HealthMonitor()

        if self.enable_alerting:
            self.alert_manager = AlertManager()

        # Load scraper
        self._load_scraper()

    def _load_scraper(self):
        """Dynamically load scraper module"""
        if not self.scraper_path.exists():
            raise FileNotFoundError(f"Scraper not found: {self.scraper_path}")

        # Import scraper module
        spec = importlib.util.spec_from_file_location(
            self.scraper_id,
            self.scraper_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find scraper class
        for name in dir(module):
            if name.endswith('Scraper') and not name.startswith('_'):
                self.scraper_class = getattr(module, name)
                break

        if not self.scraper_class:
            raise ValueError(f"No scraper class found in {self.scraper_path}")

        print(f"✅ Loaded scraper: {self.scraper_class.__name__}")

    async def run(
        self,
        data: Dict[str, Any],
        test_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Run scraper with health monitoring

        Args:
            data: Input data for scraper
            test_mode: Whether to run in test mode (no actual submission)

        Returns:
            Scraper result with monitoring metadata
        """
        start_time = time.time()
        success = False
        error_type = None
        error_message = None
        result = None

        try:
            # Initialize scraper
            scraper = self.scraper_class()

            # Run scraper
            if test_mode:
                if hasattr(scraper, 'run_test_mode'):
                    result = await scraper.run_test_mode(data)
                else:
                    result = {
                        "success": False,
                        "error": "Test mode not supported by this scraper"
                    }
            else:
                result = await scraper.submit_grievance(data)

            # Check if successful
            success = result.get("success", False)

            if not success:
                error_type = result.get("error_type", "UnknownError")
                error_message = result.get("error", "Unknown error")

        except Exception as e:
            success = False
            error_type = type(e).__name__
            error_message = str(e)
            result = {
                "success": False,
                "error": error_message,
                "error_type": error_type
            }

        finally:
            duration = time.time() - start_time

            # Record execution in health monitor
            if self.enable_monitoring:
                self.health_monitor.record_execution(
                    scraper_id=self.scraper_id,
                    success=success,
                    duration=duration,
                    error_type=error_type,
                    error_message=error_message
                )

            # Add monitoring metadata to result
            if result is None:
                result = {}

            result["_monitoring"] = {
                "scraper_id": self.scraper_id,
                "duration": duration,
                "success": success,
                "timestamp": datetime.now().isoformat()
            }

        return result

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status for this scraper"""
        if not self.enable_monitoring:
            return {"monitoring_enabled": False}

        health = self.health_monitor.get_scraper_health(self.scraper_id)

        if not health:
            return {
                "monitoring_enabled": True,
                "status": "No data yet"
            }

        return {
            "monitoring_enabled": True,
            "scraper_id": health.scraper_id,
            "total_executions": health.total_executions,
            "success_rate": f"{health.success_rate*100:.1f}%",
            "health_score": f"{health.health_score:.2f}",
            "consecutive_failures": health.consecutive_failures,
            "needs_attention": health.needs_attention,
            "avg_duration": f"{health.avg_duration:.2f}s"
        }


async def main():
    """CLI interface for scraper runner"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run scraper with health monitoring"
    )
    parser.add_argument(
        "scraper_path",
        type=str,
        help="Path to scraper file"
    )
    parser.add_argument(
        "--data",
        type=str,
        help="JSON data to submit (or path to JSON file)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run in test mode (no actual submission)"
    )
    parser.add_argument(
        "--no-monitoring",
        action="store_true",
        help="Disable health monitoring"
    )
    parser.add_argument(
        "--no-alerting",
        action="store_true",
        help="Disable alerting"
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Show health status and exit"
    )

    args = parser.parse_args()

    # Initialize runner
    runner = ScraperRunner(
        scraper_path=args.scraper_path,
        enable_monitoring=not args.no_monitoring,
        enable_alerting=not args.no_alerting
    )

    # Show health status
    if args.health:
        print("\n" + "="*80)
        print("HEALTH STATUS")
        print("="*80)

        health = runner.get_health_status()
        for key, value in health.items():
            print(f"{key:25s}: {value}")

        print("="*80)
        return

    # Prepare data
    if not args.data:
        # Use default test data
        data = {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "9876543210",
            "address": "Test Address",
            "complaint": "Test complaint for monitoring",
            "category": "Test Category"
        }
        print("⚠️  No data provided, using default test data")
    else:
        # Load data from JSON string or file
        data_path = Path(args.data)
        if data_path.exists():
            with open(data_path) as f:
                data = json.load(f)
        else:
            data = json.loads(args.data)

    # Run scraper
    print("\n" + "="*80)
    print("RUNNING SCRAPER")
    print("="*80)
    print(f"Scraper: {args.scraper_path}")
    print(f"Mode: {'Test' if args.test else 'Production'}")
    print(f"Monitoring: {'Enabled' if not args.no_monitoring else 'Disabled'}")
    print(f"Alerting: {'Enabled' if not args.no_alerting else 'Disabled'}")
    print("="*80)

    result = await runner.run(data, test_mode=args.test)

    # Display result
    print("\n" + "="*80)
    print("RESULT")
    print("="*80)

    if result.get("success"):
        print("✅ SUCCESS")
    else:
        print("❌ FAILED")

    print(f"\nDetails:")
    for key, value in result.items():
        if key != "_monitoring":
            print(f"  {key}: {value}")

    # Display monitoring info
    if "_monitoring" in result:
        print(f"\nMonitoring:")
        for key, value in result["_monitoring"].items():
            print(f"  {key}: {value}")

    # Show health status
    if not args.no_monitoring:
        print("\n" + "="*80)
        print("HEALTH STATUS")
        print("="*80)

        health = runner.get_health_status()
        for key, value in health.items():
            if key != "monitoring_enabled":
                print(f"  {key}: {value}")

    print("="*80)

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    asyncio.run(main())
