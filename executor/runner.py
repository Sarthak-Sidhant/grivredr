"""
Executor - Runs generated scrapers with user data
"""
import asyncio
import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScraperExecutor:
    """
    Executes generated scrapers and handles retries/errors
    """

    def __init__(self, scrapers_dir: str = "generated_scrapers"):
        self.scrapers_dir = Path(scrapers_dir)
        self.results_dir = Path("executor/results")
        self.results_dir.mkdir(exist_ok=True, parents=True)

    async def execute_scraper(
        self,
        municipality_name: str,
        website_type: str,
        grievance_data: Dict[str, Any],
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Execute a scraper with the provided grievance data

        Args:
            municipality_name: e.g., "ranchi"
            website_type: e.g., "complaint_form"
            grievance_data: User's grievance data
            max_retries: Number of retry attempts

        Returns:
            {
                "success": bool,
                "tracking_id": str,
                "screenshots": list,
                "error": str,
                "execution_time": float,
                "metadata": dict
            }
        """
        start_time = datetime.now()
        scraper_file = f"{municipality_name}_{website_type}_scraper.py"
        scraper_path = self.scrapers_dir / municipality_name / scraper_file

        if not scraper_path.exists():
            return {
                "success": False,
                "error": f"Scraper not found: {scraper_path}",
                "municipality": municipality_name,
                "website_type": website_type
            }

        logger.info(f"Executing scraper: {scraper_path}")

        for attempt in range(max_retries + 1):
            try:
                # Dynamically load the scraper module
                scraper_class = self._load_scraper_class(scraper_path, municipality_name)

                # Initialize scraper
                scraper_instance = scraper_class()

                # Execute
                logger.info(f"Attempt {attempt + 1}/{max_retries + 1}")
                result = await scraper_instance.submit_grievance(grievance_data)

                execution_time = (datetime.now() - start_time).total_seconds()

                # Save result
                self._save_execution_result(
                    municipality_name,
                    website_type,
                    result,
                    grievance_data
                )

                result["execution_time"] = execution_time
                result["attempts"] = attempt + 1

                if result.get("success"):
                    logger.info(f"Scraper executed successfully: {result.get('tracking_id')}")
                    return result
                else:
                    logger.warning(f"Scraper failed: {result.get('error')}")
                    if attempt < max_retries:
                        await asyncio.sleep(2)  # Wait before retry
                        continue
                    return result

            except Exception as e:
                logger.error(f"Execution error (attempt {attempt + 1}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2)
                    continue

                return {
                    "success": False,
                    "error": str(e),
                    "municipality": municipality_name,
                    "website_type": website_type,
                    "execution_time": (datetime.now() - start_time).total_seconds(),
                    "attempts": attempt + 1
                }

    def _load_scraper_class(self, scraper_path: Path, municipality_name: str):
        """Dynamically load scraper class from file"""
        spec = importlib.util.spec_from_file_location(
            f"{municipality_name}_scraper",
            scraper_path
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        # Find the scraper class (usually named like RanchiScraper)
        class_name = f"{municipality_name.title().replace('_', '')}Scraper"

        if hasattr(module, class_name):
            return getattr(module, class_name)

        # If not found, try to find any class that ends with "Scraper"
        for attr_name in dir(module):
            if attr_name.endswith("Scraper"):
                return getattr(module, attr_name)

        raise AttributeError(f"No scraper class found in {scraper_path}")

    def _save_execution_result(
        self,
        municipality: str,
        website_type: str,
        result: Dict[str, Any],
        input_data: Dict[str, Any]
    ):
        """Save execution result to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = self.results_dir / f"{municipality}_{website_type}_{timestamp}.json"

        result_data = {
            "timestamp": timestamp,
            "municipality": municipality,
            "website_type": website_type,
            "input_data": input_data,
            "result": result
        }

        with open(result_file, "w") as f:
            json.dump(result_data, f, indent=2, default=str)

        logger.info(f"Result saved: {result_file}")

    async def check_grievance_status(
        self,
        municipality_name: str,
        tracking_id: str
    ) -> Dict[str, Any]:
        """
        Check status of a submitted grievance

        Args:
            municipality_name: Municipality name
            tracking_id: Tracking ID from submission

        Returns:
            Status information
        """
        # Try to find status checker scraper
        status_scraper_file = f"{municipality_name}_status_checker_scraper.py"
        scraper_path = self.scrapers_dir / municipality_name / status_scraper_file

        if not scraper_path.exists():
            return {
                "success": False,
                "error": "Status checker not available for this municipality"
            }

        try:
            scraper_class = self._load_scraper_class(scraper_path, municipality_name)
            scraper_instance = scraper_class()

            result = await scraper_instance.check_status({"tracking_id": tracking_id})
            return result

        except Exception as e:
            logger.error(f"Failed to check status: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def execute_batch(
        self,
        batch_data: list[Dict[str, Any]]
    ) -> list[Dict[str, Any]]:
        """
        Execute multiple scrapers in batch

        Args:
            batch_data: List of {municipality, website_type, grievance_data}

        Returns:
            List of results
        """
        tasks = []

        for item in batch_data:
            task = self.execute_scraper(
                municipality_name=item["municipality"],
                website_type=item["website_type"],
                grievance_data=item["grievance_data"]
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "input": batch_data[i]
                })
            else:
                processed_results.append(result)

        return processed_results

    def list_available_scrapers(self) -> Dict[str, list]:
        """List all available scrapers by municipality"""
        scrapers_by_municipality = {}

        for municipality_dir in self.scrapers_dir.iterdir():
            if municipality_dir.is_dir() and not municipality_dir.name.startswith("__"):
                scrapers = []
                for scraper_file in municipality_dir.glob("*_scraper.py"):
                    scraper_name = scraper_file.stem
                    scrapers.append(scraper_name)

                if scrapers:
                    scrapers_by_municipality[municipality_dir.name] = scrapers

        return scrapers_by_municipality


async def test_executor():
    """Test the executor"""
    executor = ScraperExecutor()

    # List available scrapers
    available = executor.list_available_scrapers()
    print("\nAvailable scrapers:")
    print(json.dumps(available, indent=2))

    # Test data
    test_data = {
        "name": "John Doe",
        "phone": "9876543210",
        "email": "john@example.com",
        "complaint": "Street light not working in Sector 5",
        "category": "Electricity",
        "address": "Sector 5, Ranchi"
    }

    # Try to execute (will fail if no scrapers exist yet)
    if available:
        municipality = list(available.keys())[0]
        website_type = available[municipality][0].replace(f"{municipality}_", "").replace("_scraper", "")

        result = await executor.execute_scraper(
            municipality_name=municipality,
            website_type=website_type,
            grievance_data=test_data
        )

        print("\nExecution result:")
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(test_executor())
