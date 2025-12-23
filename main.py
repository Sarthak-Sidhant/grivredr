"""
FastAPI Backend for AI-Powered Grievance Automation System
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from website_learner.learner import WebsiteLearner
from scraper_generator.generator import ScraperGenerator
from executor.runner import ScraperExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Grivredr - AI Grievance Automation",
    description="Automatically learn, generate scrapers, and submit grievances to municipal portals",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
scraper_executor = ScraperExecutor()
scraper_generator = ScraperGenerator()


# ============================================================================
# Pydantic Models
# ============================================================================

class WebsiteInfo(BaseModel):
    url: str
    type: str = Field(default="complaint_form", description="Type of website (complaint_form, status_checker, etc.)")
    description: Optional[str] = None


class LearnWebsiteRequest(BaseModel):
    municipality_name: str
    websites: List[WebsiteInfo]
    headless: bool = Field(default=True, description="Run browser in headless mode")
    generate_scrapers: bool = Field(default=True, description="Auto-generate scrapers after learning")


class SubmitGrievanceRequest(BaseModel):
    municipality: str
    website_type: str = "complaint_form"
    grievance_data: Dict[str, Any] = Field(
        ...,
        example={
            "name": "John Doe",
            "phone": "9876543210",
            "email": "john@example.com",
            "complaint": "Street light not working",
            "category": "Electricity",
            "address": "Sector 5"
        }
    )


class CheckStatusRequest(BaseModel):
    municipality: str
    tracking_id: str


class BatchSubmitRequest(BaseModel):
    submissions: List[Dict[str, Any]]


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "service": "Grivredr AI Grievance Automation",
        "status": "operational",
        "version": "1.0.0",
        "endpoints": {
            "learn": "/api/learn",
            "submit": "/api/submit",
            "status": "/api/status",
            "scrapers": "/api/scrapers"
        }
    }


@app.post("/api/learn")
async def learn_websites(
    request: LearnWebsiteRequest,
    background_tasks: BackgroundTasks
):
    """
    Learn new municipality websites and generate scrapers

    This is the core AI learning endpoint. It:
    1. Explores the provided websites using Playwright + Claude Vision
    2. Analyzes form structure and navigation
    3. Generates reusable scraper code
    4. Saves scrapers for future use

    Use this when onboarding a new municipality.
    """
    logger.info(f"Learning request for {request.municipality_name}: {len(request.websites)} websites")

    try:
        # Convert Pydantic models to dicts
        websites_list = [
            {
                "url": w.url,
                "type": w.type,
                "description": w.description or f"{request.municipality_name} {w.type}"
            }
            for w in request.websites
        ]

        # Start learning in background
        background_tasks.add_task(
            _learn_and_generate_task,
            request.municipality_name,
            websites_list,
            request.headless,
            request.generate_scrapers
        )

        return {
            "success": True,
            "message": f"Learning started for {request.municipality_name}",
            "municipality": request.municipality_name,
            "websites_count": len(request.websites),
            "status": "Learning in progress. Check /api/scrapers to see when complete."
        }

    except Exception as e:
        logger.error(f"Learning request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _learn_and_generate_task(
    municipality_name: str,
    websites: List[Dict[str, str]],
    headless: bool,
    generate_scrapers: bool
):
    """Background task for learning and generating scrapers"""
    try:
        logger.info(f"Starting learning task for {municipality_name}")

        # Learn websites
        async with WebsiteLearner(headless=headless) as learner:
            learning_results = await learner.learn_multiple_websites(
                websites=websites,
                municipality_name=municipality_name
            )

        # Save learning results
        results_file = Path(f"website_learner/results_{municipality_name}.json")
        with open(results_file, "w") as f:
            json.dump(learning_results, f, indent=2, default=str)

        logger.info(f"Learning completed. Results saved to {results_file}")

        # Generate scrapers if requested
        if generate_scrapers:
            logger.info(f"Generating scrapers for {municipality_name}")
            generation_result = scraper_generator.generate_scrapers_for_municipality(
                learning_results=learning_results,
                municipality_name=municipality_name
            )

            logger.info(f"Scraper generation complete: {generation_result['generated_count']} generated")

            # Update municipalities.json
            _update_municipalities_config(municipality_name, generation_result)

    except Exception as e:
        logger.error(f"Background learning task failed: {e}")


@app.post("/api/submit")
async def submit_grievance(request: SubmitGrievanceRequest):
    """
    Submit a grievance using a generated scraper

    This executes the pre-generated scraper for the specified municipality.
    Fast and cheap - no AI calls needed!
    """
    logger.info(f"Submitting grievance to {request.municipality}")

    try:
        result = await scraper_executor.execute_scraper(
            municipality_name=request.municipality,
            website_type=request.website_type,
            grievance_data=request.grievance_data
        )

        if result.get("success"):
            return {
                "success": True,
                "tracking_id": result.get("tracking_id"),
                "message": "Grievance submitted successfully",
                "municipality": request.municipality,
                "execution_time": result.get("execution_time"),
                "screenshots": result.get("screenshots", [])
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Submission failed: {result.get('error')}"
            )

    except Exception as e:
        logger.error(f"Submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/submit/batch")
async def submit_batch(request: BatchSubmitRequest):
    """
    Submit multiple grievances in batch

    Useful for bulk submissions to different municipalities
    """
    logger.info(f"Batch submission: {len(request.submissions)} grievances")

    try:
        results = await scraper_executor.execute_batch(request.submissions)

        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful

        return {
            "success": True,
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "results": results
        }

    except Exception as e:
        logger.error(f"Batch submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/status")
async def check_grievance_status(request: CheckStatusRequest):
    """
    Check status of a submitted grievance

    Uses the status checker scraper if available
    """
    logger.info(f"Checking status for {request.tracking_id} in {request.municipality}")

    try:
        result = await scraper_executor.check_grievance_status(
            municipality_name=request.municipality,
            tracking_id=request.tracking_id
        )

        return result

    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scrapers")
async def list_scrapers():
    """
    List all available scrapers

    Shows which municipalities have scrapers ready to use
    """
    try:
        scrapers = scraper_executor.list_available_scrapers()

        return {
            "success": True,
            "municipalities": scrapers,
            "total_municipalities": len(scrapers),
            "total_scrapers": sum(len(s) for s in scrapers.values())
        }

    except Exception as e:
        logger.error(f"Failed to list scrapers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/municipalities")
async def list_municipalities():
    """
    List all configured municipalities

    Returns info about each municipality's websites and scrapers
    """
    try:
        config_file = Path("config/municipalities.json")
        if not config_file.exists():
            return {"municipalities": {}}

        with open(config_file) as f:
            config = json.load(f)

        return {
            "success": True,
            "municipalities": config
        }

    except Exception as e:
        logger.error(f"Failed to load municipalities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/municipality/{name}")
async def get_municipality_info(name: str):
    """Get detailed info about a specific municipality"""
    try:
        config_file = Path("config/municipalities.json")
        with open(config_file) as f:
            config = json.load(f)

        if name not in config:
            raise HTTPException(status_code=404, detail=f"Municipality '{name}' not found")

        return {
            "success": True,
            "municipality": config[name]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get municipality info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Utility Functions
# ============================================================================

def _update_municipalities_config(municipality_name: str, generation_result: Dict[str, Any]):
    """Update municipalities.json with generated scraper info"""
    try:
        config_file = Path("config/municipalities.json")

        with open(config_file) as f:
            config = json.load(f)

        if municipality_name not in config:
            config[municipality_name] = {
                "name": municipality_name,
                "websites": [],
                "generated_scrapers": []
            }

        # Add scraper info
        config[municipality_name]["generated_scrapers"] = [
            {
                "file_path": s["file_path"],
                "metadata": s["metadata"]
            }
            for s in generation_result.get("generated", [])
        ]

        config[municipality_name]["last_updated"] = datetime.now().isoformat()

        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Updated municipalities config for {municipality_name}")

    except Exception as e:
        logger.error(f"Failed to update config: {e}")


# ============================================================================
# Startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("🚀 Grivredr AI Grievance Automation System starting...")

    # Create necessary directories
    Path("generated_scrapers").mkdir(exist_ok=True)
    Path("website_learner/screenshots").mkdir(exist_ok=True, parents=True)
    Path("executor/results").mkdir(exist_ok=True, parents=True)

    logger.info("✅ System ready!")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
