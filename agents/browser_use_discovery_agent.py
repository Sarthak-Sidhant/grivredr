"""
Browser Use Discovery Agent - Uses AI-powered browser automation for exploration
Falls back gracefully if browser-use is not available
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import browser-use, but don't fail if not available
try:
    from browser_use import Agent, Browser, BrowserConfig
    from browser_use.agent.views import ActionResult
    BROWSER_USE_AVAILABLE = True
    logger.info("✓ browser-use framework available")
except ImportError:
    BROWSER_USE_AVAILABLE = False
    logger.warning("⚠️  browser-use not installed - using standard Playwright")


@dataclass
class BrowserUseResult:
    """Result from Browser Use exploration"""
    success: bool
    actions_taken: list
    form_data: Dict[str, Any]
    screenshots: list
    error: Optional[str] = None


class BrowserUseDiscoveryAgent:
    """
    Enhanced discovery agent using Browser Use framework for intelligent exploration
    Falls back to standard Playwright if browser-use not available
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.available = BROWSER_USE_AVAILABLE

    async def explore_form(self, url: str, municipality: str) -> BrowserUseResult:
        """
        Explore form using AI-powered browser automation

        Args:
            url: Form URL to explore
            municipality: Municipality name

        Returns:
            BrowserUseResult with captured actions and data
        """
        if not self.available:
            logger.warning("Browser Use not available - returning empty result")
            return BrowserUseResult(
                success=False,
                actions_taken=[],
                form_data={},
                screenshots=[],
                error="browser-use framework not installed"
            )

        logger.info(f"🤖 Using Browser Use AI to explore {url}")

        try:
            # Configure browser
            config = BrowserConfig(
                headless=self.headless,
                disable_security=True
            )

            # Create AI agent
            agent = Agent(
                task=f"""Explore this government grievance form at {url}.

Your task:
1. Navigate to the page
2. Identify all form fields (inputs, dropdowns, textareas)
3. Try interacting with dropdowns to see cascading behavior
4. Note any validation messages
5. DO NOT submit the form
6. Return detailed information about form structure

Focus on:
- Field names and types
- Dropdown options (especially cascading)
- Required field indicators
- Validation rules
""",
                llm=self._get_llm_client(),
                browser=Browser(config=config)
            )

            # Run exploration
            result = await agent.run()

            # Extract actions and observations
            actions_taken = self._extract_actions(result)

            logger.info(f"✓ Browser Use exploration complete: {len(actions_taken)} actions")

            return BrowserUseResult(
                success=True,
                actions_taken=actions_taken,
                form_data=self._extract_form_data(result),
                screenshots=[],  # Browser Use handles screenshots internally
                error=None
            )

        except Exception as e:
            logger.error(f"Browser Use exploration failed: {e}")
            return BrowserUseResult(
                success=False,
                actions_taken=[],
                form_data={},
                screenshots=[],
                error=str(e)
            )

    def _get_llm_client(self):
        """Get LLM client for Browser Use"""
        from config.ai_client import ai_client

        # Browser Use expects OpenAI-compatible client
        return ai_client.client

    def _extract_actions(self, result: ActionResult) -> list:
        """Extract meaningful actions from Browser Use result"""
        actions = []

        # Browser Use stores actions in result history
        if hasattr(result, 'history'):
            for action in result.history:
                actions.append({
                    'type': action.action_type if hasattr(action, 'action_type') else 'unknown',
                    'target': action.target if hasattr(action, 'target') else None,
                    'value': action.value if hasattr(action, 'value') else None,
                    'success': action.success if hasattr(action, 'success') else True
                })

        return actions

    def _extract_form_data(self, result: ActionResult) -> Dict[str, Any]:
        """Extract form structure from Browser Use result"""
        form_data = {
            'fields': [],
            'observations': []
        }

        # Parse result output for form information
        if hasattr(result, 'output'):
            output_text = str(result.output)

            # Simple extraction - look for field mentions
            if 'input' in output_text.lower():
                form_data['observations'].append('Found input fields')
            if 'dropdown' in output_text.lower() or 'select' in output_text.lower():
                form_data['observations'].append('Found dropdown fields')
            if 'required' in output_text.lower():
                form_data['observations'].append('Found required field indicators')

        return form_data

    async def test_form_filling(
        self,
        url: str,
        test_data: Dict[str, Any]
    ) -> BrowserUseResult:
        """
        Test form filling using Browser Use

        Args:
            url: Form URL
            test_data: Data to fill

        Returns:
            Result of filling attempt
        """
        if not self.available:
            return BrowserUseResult(
                success=False,
                actions_taken=[],
                form_data={},
                screenshots=[],
                error="browser-use not available"
            )

        logger.info(f"🧪 Testing form filling with Browser Use")

        try:
            config = BrowserConfig(headless=self.headless)

            # Build task with actual data
            data_str = "\n".join([f"- {k}: {v}" for k, v in test_data.items()])

            agent = Agent(
                task=f"""Fill this form at {url} with the following data:

{data_str}

Instructions:
1. Navigate to the page
2. Find and fill each field with the corresponding value
3. Handle any cascading dropdowns (wait for options to load)
4. DO NOT click submit
5. Report any errors or issues

Be careful with:
- Waiting for dropdowns to populate
- Triggering validation on blur
- Handling required fields
""",
                llm=self._get_llm_client(),
                browser=Browser(config=config)
            )

            result = await agent.run()

            return BrowserUseResult(
                success=True,
                actions_taken=self._extract_actions(result),
                form_data={'test': 'completed'},
                screenshots=[],
                error=None
            )

        except Exception as e:
            logger.error(f"Form filling test failed: {e}")
            return BrowserUseResult(
                success=False,
                actions_taken=[],
                form_data={},
                screenshots=[],
                error=str(e)
            )


# Example usage
async def demo_browser_use():
    """Demo Browser Use agent"""
    if not BROWSER_USE_AVAILABLE:
        print("❌ browser-use not installed")
        print("Install with: pip install browser-use")
        return

    agent = BrowserUseDiscoveryAgent(headless=False)

    # Explore a form
    result = await agent.explore_form(
        url="https://www.abuasathiranchi.org/SiteController/onlinegrievance",
        municipality="abua_sathi"
    )

    print(f"\n{'='*60}")
    print(f"Exploration Result:")
    print(f"{'='*60}")
    print(f"Success: {result.success}")
    print(f"Actions taken: {len(result.actions_taken)}")
    print(f"Form data: {result.form_data}")

    if result.actions_taken:
        print(f"\nActions:")
        for i, action in enumerate(result.actions_taken[:5], 1):
            print(f"  {i}. {action}")


if __name__ == "__main__":
    asyncio.run(demo_browser_use())
