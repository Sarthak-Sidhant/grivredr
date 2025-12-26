"""
Batch Processor - Process multiple municipalities in parallel
Handles resource pooling, rate limiting, and progress tracking
"""
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

from agents.orchestrator import Orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BatchJob:
    """Single batch job"""
    job_id: str
    municipality: str
    url: str
    priority: int = 0
    hints: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class BatchProgress:
    """Batch processing progress"""
    total_jobs: int
    completed: int = 0
    failed: int = 0
    running: int = 0
    pending: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.completed == 0:
            return 0.0
        return self.completed / (self.completed + self.failed)

    @property
    def duration(self) -> float:
        """Get duration in seconds"""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def estimated_time_remaining(self) -> Optional[float]:
        """Estimate time remaining in seconds"""
        if self.completed == 0:
            return None

        avg_time_per_job = self.duration / self.completed
        remaining_jobs = self.total_jobs - self.completed - self.failed
        return avg_time_per_job * remaining_jobs


class BatchProcessor:
    """
    Process multiple municipalities in parallel with resource management
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        headless: bool = True,
        dashboard_enabled: bool = False,
        retry_failed: bool = True,
        max_retries: int = 2
    ):
        self.max_concurrent = max_concurrent
        self.headless = headless
        self.dashboard_enabled = dashboard_enabled
        self.retry_failed = retry_failed
        self.max_retries = max_retries

        self.progress: Optional[BatchProgress] = None
        self.jobs: List[BatchJob] = []

        # Results directory
        self.results_dir = Path("batch_results")
        self.results_dir.mkdir(exist_ok=True)

    async def process_batch(
        self,
        municipalities: List[Dict[str, Any]],
        batch_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process multiple municipalities in parallel

        Args:
            municipalities: List of dicts with 'municipality' and 'url' keys
            batch_name: Optional name for this batch

        Returns:
            Batch results summary
        """
        batch_name = batch_name or f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"\n{'='*80}")
        logger.info(f"BATCH PROCESSING: {batch_name}")
        logger.info(f"{'='*80}")
        logger.info(f"Total municipalities: {len(municipalities)}")
        logger.info(f"Max concurrent: {self.max_concurrent}")
        logger.info(f"Headless mode: {self.headless}")
        logger.info(f"{'='*80}\n")

        # Create jobs
        self.jobs = []
        for i, muni in enumerate(municipalities):
            job = BatchJob(
                job_id=f"{batch_name}_{i+1}",
                municipality=muni["municipality"],
                url=muni["url"],
                priority=muni.get("priority", 0),
                hints=muni.get("hints")
            )
            self.jobs.append(job)

        # Sort by priority (highest first)
        self.jobs.sort(key=lambda j: j.priority, reverse=True)

        # Initialize progress
        self.progress = BatchProgress(total_jobs=len(self.jobs))
        self.progress.pending = len(self.jobs)

        # Process with concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_job_with_semaphore(job: BatchJob):
            async with semaphore:
                return await self._process_single_job(job)

        # Run all jobs
        tasks = [process_job_with_semaphore(job) for job in self.jobs]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Finalize
        self.progress.end_time = datetime.now()

        # Save results
        result = self._save_batch_results(batch_name)

        # Print summary
        self._print_summary()

        return result

    async def _process_single_job(self, job: BatchJob):
        """Process a single municipality"""
        attempt = 0

        while attempt <= self.max_retries:
            try:
                # Update status
                job.status = "running"
                job.start_time = datetime.now()
                self.progress.running += 1
                self.progress.pending -= 1

                logger.info(f"\n🔄 [{job.job_id}] Starting: {job.municipality}")
                logger.info(f"   URL: {job.url}")
                logger.info(f"   Attempt: {attempt + 1}/{self.max_retries + 1}")
                logger.info(f"   Progress: {self.progress.completed + self.progress.failed}/{self.progress.total_jobs}")

                # Create orchestrator
                orchestrator = Orchestrator(
                    headless=self.headless,
                    dashboard_enabled=self.dashboard_enabled
                )

                # Run training
                result = await orchestrator.train_municipality(
                    url=job.url,
                    municipality=job.municipality,
                    hints=job.hints
                )

                # Update job
                job.result = result
                job.end_time = datetime.now()

                if result.get("success"):
                    job.status = "completed"
                    self.progress.completed += 1
                    logger.info(f"✅ [{job.job_id}] Completed: {job.municipality}")
                    logger.info(f"   Cost: ${result.get('total_cost', 0):.4f}")
                    logger.info(f"   Scraper: {result.get('scraper_path')}")
                    break  # Success, don't retry
                else:
                    raise Exception(result.get("error", "Training failed"))

            except Exception as e:
                logger.error(f"❌ [{job.job_id}] Failed: {e}")

                if attempt < self.max_retries and self.retry_failed:
                    attempt += 1
                    logger.info(f"🔁 [{job.job_id}] Retrying... (attempt {attempt + 1})")
                    await asyncio.sleep(5)  # Wait before retry
                else:
                    # Final failure
                    job.status = "failed"
                    job.error = str(e)
                    job.end_time = datetime.now()
                    self.progress.failed += 1
                    logger.error(f"❌ [{job.job_id}] FINAL FAILURE: {job.municipality}")
                    break

            finally:
                self.progress.running -= 1

    def _save_batch_results(self, batch_name: str) -> Dict[str, Any]:
        """Save batch results to file"""
        result_file = self.results_dir / f"{batch_name}.json"

        summary = {
            "batch_name": batch_name,
            "total_jobs": self.progress.total_jobs,
            "completed": self.progress.completed,
            "failed": self.progress.failed,
            "success_rate": self.progress.success_rate,
            "duration": self.progress.duration,
            "start_time": str(self.progress.start_time),
            "end_time": str(self.progress.end_time),
            "jobs": []
        }

        for job in self.jobs:
            job_data = {
                "job_id": job.job_id,
                "municipality": job.municipality,
                "url": job.url,
                "status": job.status,
                "error": job.error
            }

            if job.result:
                job_data["scraper_path"] = job.result.get("scraper_path")
                job_data["total_cost"] = job.result.get("total_cost")
                job_data["human_interventions"] = job.result.get("human_interventions")

            if job.start_time and job.end_time:
                job_data["duration"] = (job.end_time - job.start_time).total_seconds()

            summary["jobs"].append(job_data)

        # Calculate total cost
        total_cost = sum(
            job.result.get("total_cost", 0)
            for job in self.jobs
            if job.result
        )
        summary["total_cost"] = total_cost

        # Save to file
        with open(result_file, "w") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"\n💾 Batch results saved: {result_file}")

        return summary

    def _print_summary(self):
        """Print batch processing summary"""
        logger.info(f"\n{'='*80}")
        logger.info(f"BATCH PROCESSING COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"Total Jobs: {self.progress.total_jobs}")
        logger.info(f"✅ Completed: {self.progress.completed}")
        logger.info(f"❌ Failed: {self.progress.failed}")
        logger.info(f"📊 Success Rate: {self.progress.success_rate*100:.1f}%")
        logger.info(f"⏱️  Duration: {self.progress.duration:.1f}s ({self.progress.duration/60:.1f} minutes)")

        if self.progress.completed > 0:
            avg_time = self.progress.duration / self.progress.completed
            logger.info(f"⚡ Avg Time per Job: {avg_time:.1f}s")

        # List failed jobs
        if self.progress.failed > 0:
            logger.info(f"\n❌ Failed Jobs:")
            for job in self.jobs:
                if job.status == "failed":
                    logger.info(f"   - {job.municipality}: {job.error}")

        logger.info(f"{'='*80}\n")


# For testing
async def test_batch_processing():
    """Test batch processor with sample municipalities"""

    # Sample municipalities
    municipalities = [
        {
            "municipality": "ranchi",
            "url": "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online",
            "priority": 1
        },
        # Add more municipalities here for real batch testing
    ]

    # Create batch processor
    processor = BatchProcessor(
        max_concurrent=3,
        headless=True,
        retry_failed=True
    )

    # Process batch
    result = await processor.process_batch(
        municipalities,
        batch_name="test_batch"
    )

    print(f"\n{'='*80}")
    print("BATCH RESULT")
    print(f"{'='*80}")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(test_batch_processing())
