"""
Website Learner - AI agent that explores and understands grievance websites
"""
import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser
from config.ai_client import ai_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebsiteLearner:
    """
    AI-powered website exploration and learning agent
    Analyzes grievance portals and extracts structure information
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.screenshots_dir = Path("website_learner/screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-web-security'
            ]
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        await self.playwright.stop()

    async def take_screenshot(self, page: Page, name: str) -> str:
        """Take screenshot and return base64 encoded string"""
        screenshot_path = self.screenshots_dir / f"{name}.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)

        with open(screenshot_path, "rb") as f:
            screenshot_base64 = base64.b64encode(f.read()).decode()

        return screenshot_base64

    async def extract_form_html(self, page: Page) -> str:
        """Extract relevant form HTML for analysis"""
        try:
            # Try to find form elements
            form_html = await page.evaluate("""
                () => {
                    const forms = document.querySelectorAll('form');
                    if (forms.length > 0) {
                        return forms[0].outerHTML;
                    }
                    // If no form tag, try to find form-like structures
                    const inputs = document.querySelectorAll('input, textarea, select');
                    if (inputs.length > 0) {
                        return inputs[0].closest('div')?.outerHTML || document.body.innerHTML;
                    }
                    return document.body.innerHTML;
                }
            """)
            return form_html[:5000]  # Limit size
        except Exception as e:
            logger.warning(f"Could not extract form HTML: {e}")
            return ""

    async def learn_website(
        self,
        url: str,
        municipality_name: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Main learning function - explores website and extracts structure

        Returns:
            {
                "success": bool,
                "url": str,
                "analysis": dict,  # Parsed JSON from AI
                "raw_analysis": str,  # Raw AI response
                "screenshots": [str],  # Paths to screenshots
                "metadata": dict
            }
        """
        logger.info(f"Starting website learning for: {url}")

        if not self.browser:
            raise RuntimeError("WebsiteLearner not initialized. Use 'async with' context.")

        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()

        try:
            # Step 1: Navigate to the website
            logger.info(f"Navigating to {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # Let page settle

            # Step 2: Take initial screenshot
            screenshot_base64 = await self.take_screenshot(
                page,
                f"{municipality_name}_initial"
            )

            # Step 3: Extract form HTML
            form_html = await self.extract_form_html(page)

            # Step 4: Look for complaint/grievance form links
            await self._explore_grievance_links(page)

            # Step 5: Take another screenshot after exploration
            screenshot_after_base64 = await self.take_screenshot(
                page,
                f"{municipality_name}_explored"
            )

            # Step 6: Get page HTML for context
            page_html = await page.content()

            # Step 7: Analyze with AI
            logger.info("Analyzing website structure with Claude Vision")
            raw_analysis = ai_client.analyze_website_structure(
                screenshot_base64=screenshot_after_base64,
                url=url,
                html_snippet=form_html
            )

            # Step 8: Parse AI response
            try:
                # Extract JSON from markdown code blocks if present
                analysis_json = self._extract_json_from_response(raw_analysis)
            except Exception as e:
                logger.error(f"Failed to parse AI analysis: {e}")
                analysis_json = {"error": "Failed to parse", "raw": raw_analysis}

            result = {
                "success": True,
                "url": url,
                "analysis": analysis_json,
                "raw_analysis": raw_analysis,
                "screenshots": [
                    f"outputs/screenshots/{municipality_name}_initial.png",
                    f"outputs/screenshots/{municipality_name}_explored.png"
                ],
                "metadata": {
                    "municipality": municipality_name,
                    "page_title": await page.title(),
                    "final_url": page.url,  # In case of redirects
                }
            }

            logger.info(f"Successfully learned website: {url}")
            return result

        except Exception as e:
            logger.error(f"Error learning website {url}: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "screenshots": []
            }

        finally:
            await context.close()

    async def _explore_grievance_links(self, page: Page):
        """Click on links that might lead to grievance forms"""
        keywords = [
            "complaint", "grievance", "register", "submit",
            "शिकायत", "रजिस्टर", "file complaint"
        ]

        for keyword in keywords:
            try:
                # Try to find and click relevant links
                link = page.locator(f"text=/{keyword}/i").first
                if await link.count() > 0:
                    logger.info(f"Found link with keyword: {keyword}")
                    await link.click(timeout=5000)
                    await asyncio.sleep(2)
                    break
            except Exception:
                continue

    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from AI response (handles markdown code blocks)"""
        # Try to find JSON in markdown code blocks
        import re

        # Look for ```json ... ``` blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # Try to find raw JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))

        # If no JSON found, return raw response
        return {"raw_response": response}

    async def learn_multiple_websites(
        self,
        websites: list[Dict[str, str]],
        municipality_name: str
    ) -> list[Dict[str, Any]]:
        """Learn multiple websites for a municipality"""
        results = []

        for site in websites:
            result = await self.learn_website(
                url=site["url"],
                municipality_name=f"{municipality_name}_{site['type']}"
            )
            result["website_type"] = site["type"]
            result["description"] = site["description"]
            results.append(result)

            # Brief pause between websites
            await asyncio.sleep(2)

        return results


async def test_learner():
    """Test the website learner"""
    async with WebsiteLearner(headless=False) as learner:
        result = await learner.learn_website(
            url="https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online",
            municipality_name="ranchi_smart_portal"
        )

        print("\n" + "="*80)
        print("LEARNING RESULT")
        print("="*80)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(test_learner())
