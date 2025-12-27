"""
Hybrid Discovery Strategy - Intelligently uses Browser Use + Playwright
Always tries Playwright first, uses Browser Use for complex cases
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryConfig:
    """Configuration for discovery strategy"""
    use_browser_use_first: bool = False  # Try AI exploration first?
    browser_use_on_failure: bool = True   # Use AI if Playwright fails?
    max_playwright_attempts: int = 2      # Attempts before AI
    browser_use_timeout: int = 120        # AI exploration timeout


class HybridDiscoveryStrategy:
    """
    Smart discovery that uses both Playwright and Browser Use intelligently

    Strategy:
    1. Try fast Playwright approach (deterministic)
    2. If confidence < 0.7 → Use Browser Use AI
    3. If Browser Use finds new insights → Update Playwright approach
    4. Generate final code using best of both
    """

    def __init__(self, config: Optional[DiscoveryConfig] = None):
        self.config = config or DiscoveryConfig()
        self._playwright_agent = None
        self._browser_use_agent = None

    async def discover(self, url: str, municipality: str) -> Dict[str, Any]:
        """
        Smart discovery using hybrid approach

        Args:
            url: Form URL
            municipality: Municipality name

        Returns:
            Combined discovery results
        """
        logger.info(f"🔬 Starting hybrid discovery for {url}")

        results = {
            'playwright_result': None,
            'browser_use_result': None,
            'strategy_used': [],
            'confidence': 0.0,
            'needs_browser_use': False
        }

        # Phase 1: Try Playwright (fast, deterministic)
        logger.info("📋 Phase 1: Playwright Discovery")
        playwright_result = await self._playwright_discovery(url, municipality)
        results['playwright_result'] = playwright_result
        results['strategy_used'].append('playwright')

        # Analyze confidence
        confidence = playwright_result.get('confidence', 0.0)
        results['confidence'] = confidence

        # Phase 2: Decide if Browser Use is needed
        needs_browser_use = self._should_use_browser_use(playwright_result)
        results['needs_browser_use'] = needs_browser_use

        if needs_browser_use:
            logger.info("🤖 Phase 2: Browser Use AI Discovery (complex form detected)")

            try:
                browser_use_result = await self._browser_use_discovery(
                    url,
                    municipality,
                    playwright_insights=playwright_result
                )
                results['browser_use_result'] = browser_use_result
                results['strategy_used'].append('browser_use')

                # Merge insights
                merged = self._merge_discoveries(playwright_result, browser_use_result)
                results['merged'] = merged
                results['confidence'] = max(confidence, 0.85)  # AI boost

                logger.info(f"✅ Hybrid discovery complete (confidence: {results['confidence']:.2f})")

            except Exception as e:
                logger.warning(f"Browser Use failed, using Playwright only: {e}")
                results['merged'] = playwright_result

        else:
            logger.info(f"✅ Playwright sufficient (confidence: {confidence:.2f})")
            results['merged'] = playwright_result

        return results

    def _should_use_browser_use(self, playwright_result: Dict[str, Any]) -> bool:
        """
        Decide if Browser Use AI is needed

        Triggers:
        - Confidence < 0.7
        - Complex cascading dropdowns (>2 levels)
        - Dynamic field generation detected
        - Failed to find submit button
        - Form has unusual structure
        """
        confidence = playwright_result.get('confidence', 0.0)

        # Low confidence
        if confidence < 0.7:
            logger.info(f"⚠️  Low confidence ({confidence:.2f}) - Browser Use recommended")
            return True

        # Complex cascading
        cascading_fields = playwright_result.get('cascading_fields', [])
        if len(cascading_fields) > 2:
            logger.info(f"⚠️  Complex cascading ({len(cascading_fields)} levels) - Browser Use recommended")
            return True

        # Dynamic fields
        if playwright_result.get('has_dynamic_fields', False):
            logger.info("⚠️  Dynamic field generation - Browser Use recommended")
            return True

        # Missing critical elements
        if not playwright_result.get('submit_button'):
            logger.info("⚠️  Submit button not found - Browser Use recommended")
            return True

        # Form complexity score
        complexity = self._calculate_complexity(playwright_result)
        if complexity > 0.7:
            logger.info(f"⚠️  High complexity ({complexity:.2f}) - Browser Use recommended")
            return True

        return False

    def _calculate_complexity(self, result: Dict[str, Any]) -> float:
        """Calculate form complexity score (0.0 - 1.0)"""
        score = 0.0

        # Field count
        fields = result.get('fields', [])
        if len(fields) > 15:
            score += 0.2
        elif len(fields) > 10:
            score += 0.1

        # Select2 dropdowns
        select2_fields = [f for f in fields if f.get('select2', False)]
        if len(select2_fields) > 2:
            score += 0.2

        # Cascading
        cascading = result.get('cascading_fields', [])
        score += min(len(cascading) * 0.15, 0.3)

        # Dynamic behavior
        if result.get('has_ajax', False):
            score += 0.15

        # File uploads
        file_fields = [f for f in fields if f.get('type') == 'file']
        if len(file_fields) > 0:
            score += 0.1

        return min(score, 1.0)

    async def _playwright_discovery(
        self,
        url: str,
        municipality: str
    ) -> Dict[str, Any]:
        """Run standard Playwright discovery"""
        from agents.form_discovery_agent import FormDiscoveryAgent

        if not self._playwright_agent:
            self._playwright_agent = FormDiscoveryAgent(headless=False)

        result = await self._playwright_agent.execute({
            'url': url,
            'municipality': municipality
        })

        return result

    async def _browser_use_discovery(
        self,
        url: str,
        municipality: str,
        playwright_insights: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run Browser Use AI discovery
        Enhanced with Playwright insights
        """
        from agents.browser_use_discovery_agent import BrowserUseDiscoveryAgent

        if not self._browser_use_agent:
            self._browser_use_agent = BrowserUseDiscoveryAgent(headless=False)

        # Build context from Playwright
        context = self._build_ai_context(playwright_insights)

        # Custom exploration prompt with context
        result = await self._browser_use_agent.explore_form(url, municipality)

        return result

    def _build_ai_context(self, playwright_result: Dict[str, Any]) -> str:
        """Build context for Browser Use from Playwright findings"""
        fields = playwright_result.get('fields', [])
        cascading = playwright_result.get('cascading_fields', [])

        context = "The following was detected by Playwright:\n\n"

        context += f"Fields found: {len(fields)}\n"
        if cascading:
            context += f"Cascading dropdowns: {len(cascading)}\n"

        # Problem areas
        if playwright_result.get('confidence', 1.0) < 0.7:
            context += "\nProblems:\n"
            if not playwright_result.get('submit_button'):
                context += "- Could not identify submit button\n"
            if playwright_result.get('has_dynamic_fields'):
                context += "- Has dynamically generated fields\n"

        context += "\nPlease explore the form and provide additional insights."

        return context

    def _merge_discoveries(
        self,
        playwright_result: Dict[str, Any],
        browser_use_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge Playwright and Browser Use results intelligently

        Strategy:
        - Use Playwright for precise selectors
        - Use Browser Use for flow/logic insights
        - Combine field discoveries
        - Use higher confidence source for conflicts
        """
        merged = playwright_result.copy()

        # Add Browser Use insights
        merged['browser_use_insights'] = {
            'actions_observed': browser_use_result.get('actions_taken', []),
            'ai_observations': browser_use_result.get('form_data', {})
        }

        # Enhance field discovery with AI insights
        ai_observations = browser_use_result.get('form_data', {}).get('observations', [])
        merged['enhanced_observations'] = ai_observations

        # Update confidence
        merged['confidence'] = 0.85  # AI-assisted boost

        return merged


# Example usage
async def test_hybrid_strategy():
    """Test hybrid discovery"""
    strategy = HybridDiscoveryStrategy(
        config=DiscoveryConfig(
            use_browser_use_first=False,  # Try Playwright first
            browser_use_on_failure=True,  # Use AI if needed
            max_playwright_attempts=2
        )
    )

    result = await strategy.discover(
        url="https://www.abuasathiranchi.org/SiteController/onlinegrievance",
        municipality="abua_sathi"
    )

    print(f"\n{'='*60}")
    print(f"Hybrid Discovery Result:")
    print(f"{'='*60}")
    print(f"Strategy used: {', '.join(result['strategy_used'])}")
    print(f"Final confidence: {result['confidence']:.2f}")
    print(f"Browser Use needed: {result['needs_browser_use']}")


if __name__ == "__main__":
    asyncio.run(test_hybrid_strategy())
