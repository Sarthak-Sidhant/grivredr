#!/usr/bin/env python3
"""
Continuous Improvement Agent - Iteratively improves scrapers until satisfactory

This agent runs a continuous loop of:
1. Test the scraper
2. Analyze failures
3. Generate improvements
4. Apply fixes
5. Repeat until quality threshold met or max iterations
"""
import asyncio
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import anthropic
from playwright.async_api import async_playwright
import base64

from dotenv import load_dotenv
load_dotenv()


class ImprovementType(Enum):
    """Types of improvements that can be made"""
    SELECTOR_FIX = "selector_fix"
    TIMING_FIX = "timing_fix"
    FRAMEWORK_FIX = "framework_fix"  # ant-design, select2, etc.
    LOGIC_FIX = "logic_fix"
    ERROR_HANDLING = "error_handling"
    WAIT_STRATEGY = "wait_strategy"
    CASCADE_FIX = "cascade_fix"
    VALIDATION_FIX = "validation_fix"


@dataclass
class TestCase:
    """A single test case for the scraper"""
    name: str
    data: Dict[str, Any]
    expected_outcome: str = "form_filled"  # form_filled, submitted, error_expected
    priority: int = 1  # 1 = highest


@dataclass
class TestResult:
    """Result of running a test case"""
    test_case: TestCase
    success: bool
    error: Optional[str] = None
    error_type: Optional[str] = None
    screenshot_base64: Optional[str] = None
    page_html: Optional[str] = None
    duration: float = 0.0
    fields_status: Dict[str, str] = field(default_factory=dict)  # field -> "filled" | "failed" | "skipped"


@dataclass
class ImprovementSuggestion:
    """A suggested improvement to the code"""
    improvement_type: ImprovementType
    description: str
    confidence: float
    code_location: str  # Where in the code to apply
    suggested_fix: str
    reasoning: str


@dataclass
class ImprovementCycle:
    """One cycle of the improvement loop"""
    cycle_number: int
    test_results: List[TestResult]
    improvements_made: List[ImprovementSuggestion]
    success_rate: float
    cost: float
    timestamp: datetime = field(default_factory=datetime.now)


class QualityMetrics:
    """Track quality metrics across improvement cycles"""

    def __init__(self):
        self.cycles: List[ImprovementCycle] = []
        self.best_success_rate = 0.0
        self.total_cost = 0.0

    def add_cycle(self, cycle: ImprovementCycle):
        self.cycles.append(cycle)
        self.total_cost += cycle.cost
        if cycle.success_rate > self.best_success_rate:
            self.best_success_rate = cycle.success_rate

    def get_trend(self) -> str:
        """Get improvement trend"""
        if len(self.cycles) < 2:
            return "insufficient_data"

        recent = self.cycles[-1].success_rate
        previous = self.cycles[-2].success_rate

        if recent > previous:
            return "improving"
        elif recent < previous:
            return "degrading"
        else:
            return "stable"

    def should_continue(self, target_success_rate: float = 0.9) -> bool:
        """Determine if we should continue improving"""
        if not self.cycles:
            return True

        latest = self.cycles[-1]

        # Stop if we hit target
        if latest.success_rate >= target_success_rate:
            return False

        # Stop if degrading for 2+ cycles
        if len(self.cycles) >= 3:
            recent_rates = [c.success_rate for c in self.cycles[-3:]]
            if recent_rates[-1] <= recent_rates[-2] <= recent_rates[-3]:
                return False

        return True


class CostTracker:
    """Track API costs"""
    PRICING = {
        "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
    }

    def __init__(self):
        self.total_cost = 0.0
        self.calls = 0

    def add(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = self.PRICING.get(model, {"input": 3.0, "output": 15.0})
        cost = (input_tokens * pricing["input"] / 1_000_000) + \
               (output_tokens * pricing["output"] / 1_000_000)
        self.total_cost += cost
        self.calls += 1
        return cost


class ContinuousImprovementAgent:
    """
    Agent that continuously improves a scraper through iterative testing and fixing
    """

    def __init__(
        self,
        max_cycles: int = 5,
        target_success_rate: float = 0.9,
        max_cost: float = 2.0,
        screenshot_dir: str = "screenshots/improvement",
        headless: bool = True
    ):
        self.max_cycles = max_cycles
        self.target_success_rate = target_success_rate
        self.max_cost = max_cost
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless

        self.api_key = os.getenv("api_key")
        self.client = anthropic.Anthropic(
            api_key=self.api_key,
            base_url="https://ai.megallm.io"
        )
        self.cost_tracker = CostTracker()
        self.quality_metrics = QualityMetrics()

    async def improve_scraper(
        self,
        scraper_path: str,
        test_cases: List[TestCase],
        portal_context: Optional[Dict] = None
    ) -> Tuple[bool, str, QualityMetrics]:
        """
        Run continuous improvement loop on a scraper

        Args:
            scraper_path: Path to the scraper file
            test_cases: List of test cases to run
            portal_context: Context from discovery (dropdowns, cascades)

        Returns:
            Tuple of (success, final_scraper_path, quality_metrics)
        """
        scraper_path = Path(scraper_path)
        original_code = scraper_path.read_text()

        print(f"\n{'='*60}")
        print("CONTINUOUS IMPROVEMENT AGENT")
        print(f"{'='*60}")
        print(f"Scraper: {scraper_path}")
        print(f"Test cases: {len(test_cases)}")
        print(f"Target success rate: {self.target_success_rate:.0%}")
        print(f"Max cycles: {self.max_cycles}")
        print(f"Max cost: ${self.max_cost:.2f}")
        print(f"{'='*60}\n")

        for cycle_num in range(1, self.max_cycles + 1):
            print(f"\n{'─'*40}")
            print(f"CYCLE {cycle_num}/{self.max_cycles}")
            print(f"{'─'*40}")

            # Check cost limit
            if self.cost_tracker.total_cost >= self.max_cost:
                print(f"⚠️ Cost limit reached: ${self.cost_tracker.total_cost:.2f}")
                break

            # Run all test cases
            test_results = await self._run_test_cases(scraper_path, test_cases, cycle_num)

            # Calculate success rate
            success_count = sum(1 for r in test_results if r.success)
            success_rate = success_count / len(test_results) if test_results else 0

            print(f"\n📊 Results: {success_count}/{len(test_results)} passed ({success_rate:.0%})")

            # Check if we've reached target
            if success_rate >= self.target_success_rate:
                cycle = ImprovementCycle(
                    cycle_number=cycle_num,
                    test_results=test_results,
                    improvements_made=[],
                    success_rate=success_rate,
                    cost=self.cost_tracker.total_cost - self.quality_metrics.total_cost
                )
                self.quality_metrics.add_cycle(cycle)

                print(f"\n✅ Target success rate achieved!")

                # Store successful pattern for future learning
                await self._store_successful_pattern(
                    scraper_path=scraper_path,
                    portal_context=portal_context,
                    success_rate=success_rate,
                    cycles_needed=cycle_num
                )

                return True, str(scraper_path), self.quality_metrics

            # Analyze failures and generate improvements
            failed_results = [r for r in test_results if not r.success]
            print(f"\n🔍 Analyzing {len(failed_results)} failures...")

            improvements = await self._analyze_and_suggest_improvements(
                scraper_path.read_text(),
                failed_results,
                portal_context
            )

            print(f"   Generated {len(improvements)} improvement suggestions")

            # Apply improvements
            if improvements:
                current_code = scraper_path.read_text()
                new_code = await self._apply_improvements(current_code, improvements, portal_context)

                if new_code and new_code != current_code:
                    scraper_path.write_text(new_code)
                    print(f"   Applied improvements to scraper")
                else:
                    print(f"   ⚠️ No code changes generated")

            # Record cycle
            cycle = ImprovementCycle(
                cycle_number=cycle_num,
                test_results=test_results,
                improvements_made=improvements,
                success_rate=success_rate,
                cost=self.cost_tracker.total_cost - self.quality_metrics.total_cost
            )
            self.quality_metrics.add_cycle(cycle)

            # Check if we should continue
            if not self.quality_metrics.should_continue(self.target_success_rate):
                print(f"\n⚠️ Stopping: {'degrading' if self.quality_metrics.get_trend() == 'degrading' else 'no progress'}")
                break

        # Final summary
        final_success = self.quality_metrics.best_success_rate >= self.target_success_rate
        print(f"\n{'='*60}")
        print("IMPROVEMENT COMPLETE")
        print(f"{'='*60}")
        print(f"Final success rate: {self.quality_metrics.cycles[-1].success_rate:.0%}")
        print(f"Best success rate: {self.quality_metrics.best_success_rate:.0%}")
        print(f"Total cycles: {len(self.quality_metrics.cycles)}")
        print(f"Total cost: ${self.quality_metrics.total_cost:.4f}")
        print(f"{'='*60}")

        return final_success, str(scraper_path), self.quality_metrics

    async def _run_test_cases(
        self,
        scraper_path: Path,
        test_cases: List[TestCase],
        cycle_num: int
    ) -> List[TestResult]:
        """Run all test cases against the scraper"""
        results = []

        # Sort by priority
        sorted_cases = sorted(test_cases, key=lambda x: x.priority)

        for i, test_case in enumerate(sorted_cases):
            print(f"   Test {i+1}/{len(test_cases)}: {test_case.name}...", end=" ")

            result = await self._run_single_test(scraper_path, test_case, cycle_num, i)
            results.append(result)

            status = "✅" if result.success else "❌"
            print(f"{status}")

            if not result.success and result.error:
                print(f"      Error: {result.error[:60]}...")

        return results

    async def _run_single_test(
        self,
        scraper_path: Path,
        test_case: TestCase,
        cycle_num: int,
        test_num: int
    ) -> TestResult:
        """Run a single test case"""
        start_time = datetime.now()
        result = TestResult(test_case=test_case, success=False)

        try:
            # Import scraper dynamically
            import importlib.util
            spec = importlib.util.spec_from_file_location("scraper", scraper_path)
            scraper_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(scraper_module)

            # Find FormFiller class
            filler_class = None
            for name, obj in vars(scraper_module).items():
                if name.endswith("FormFiller") and isinstance(obj, type):
                    filler_class = obj
                    break

            if not filler_class:
                result.error = "No FormFiller class found"
                result.error_type = "ImportError"
                return result

            # Run the scraper
            filler = filler_class(headless=self.headless)

            try:
                await filler.start()

                # Fill form
                await filler.fill_form(test_case.data)

                # Take screenshot
                screenshot_path = self.screenshot_dir / f"cycle{cycle_num}_test{test_num}.png"
                await filler.page.screenshot(path=str(screenshot_path))

                with open(screenshot_path, "rb") as f:
                    result.screenshot_base64 = base64.b64encode(f.read()).decode()

                # Get page HTML for analysis
                result.page_html = await filler.page.content()

                # Mark success
                result.success = True
                result.fields_status = {k: "filled" for k in test_case.data.keys()}

            finally:
                await filler.close()

        except Exception as e:
            result.error = str(e)
            result.error_type = type(e).__name__

        result.duration = (datetime.now() - start_time).total_seconds()
        return result

    async def _analyze_and_suggest_improvements(
        self,
        current_code: str,
        failed_results: List[TestResult],
        portal_context: Optional[Dict]
    ) -> List[ImprovementSuggestion]:
        """Analyze failures and suggest improvements"""

        # Build analysis prompt
        failures_summary = []
        for r in failed_results[:3]:  # Limit to first 3 failures for cost
            failures_summary.append({
                "test_name": r.test_case.name,
                "test_data": r.test_case.data,
                "error": r.error,
                "error_type": r.error_type
            })

        prompt = f"""You are a code improvement expert analyzing a Playwright web scraper.

## FAILURES TO ANALYZE
```json
{json.dumps(failures_summary, indent=2)}
```

## CURRENT CODE
```python
{current_code}
```

## PORTAL CONTEXT (dropdown options, etc.)
```json
{json.dumps(portal_context, indent=2)[:2000] if portal_context else "Not available"}
```

## YOUR TASK
Analyze the failures and suggest specific improvements. For each suggestion:
1. Identify the root cause
2. Suggest a specific code fix
3. Rate your confidence (0-1)

## COMMON ISSUES TO CHECK
- Selector issues: element ID changed, wrong selector format
- Timing issues: need more wait time, element not ready
- Framework issues: Select2/Ant-Design specific handling needed
- Cascade issues: child dropdown not populated after parent selection
- Validation: form validation preventing submission

## OUTPUT FORMAT
Return a JSON array of improvements:
```json
[
  {{
    "type": "selector_fix|timing_fix|framework_fix|logic_fix|error_handling|wait_strategy|cascade_fix|validation_fix",
    "description": "Brief description of the issue",
    "confidence": 0.8,
    "code_location": "method name or line reference",
    "suggested_fix": "The actual code change needed",
    "reasoning": "Why this fix should work"
  }}
]
```

Return ONLY the JSON array, no other text."""

        messages_content = []

        # Add screenshot from first failure if available
        if failed_results and failed_results[0].screenshot_base64:
            messages_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": failed_results[0].screenshot_base64
                }
            })

        messages_content.append({"type": "text", "text": prompt})

        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4000,
            messages=[{"role": "user", "content": messages_content}]
        )

        self.cost_tracker.add(
            "claude-sonnet-4-5-20250929",
            response.usage.input_tokens,
            response.usage.output_tokens
        )

        # Parse suggestions
        text = response.content[0].text
        suggestions = []

        try:
            # Extract JSON from response
            json_match = re.search(r'\[[\s\S]*\]', text)
            if json_match:
                raw_suggestions = json.loads(json_match.group())
                for s in raw_suggestions:
                    try:
                        improvement_type = ImprovementType(s.get("type", "logic_fix"))
                    except ValueError:
                        improvement_type = ImprovementType.LOGIC_FIX

                    suggestions.append(ImprovementSuggestion(
                        improvement_type=improvement_type,
                        description=s.get("description", ""),
                        confidence=s.get("confidence", 0.5),
                        code_location=s.get("code_location", ""),
                        suggested_fix=s.get("suggested_fix", ""),
                        reasoning=s.get("reasoning", "")
                    ))
        except json.JSONDecodeError:
            pass

        # Sort by confidence
        suggestions.sort(key=lambda x: x.confidence, reverse=True)

        return suggestions

    async def _apply_improvements(
        self,
        current_code: str,
        improvements: List[ImprovementSuggestion],
        portal_context: Optional[Dict]
    ) -> str:
        """Apply improvement suggestions to generate new code"""

        improvements_text = "\n".join([
            f"- [{i.improvement_type.value}] {i.description}\n  Fix: {i.suggested_fix}\n  Confidence: {i.confidence}"
            for i in improvements[:5]  # Limit to top 5
        ])

        prompt = f"""You are a code improvement expert. Apply the suggested improvements to fix the scraper.

## CURRENT CODE
```python
{current_code}
```

## IMPROVEMENTS TO APPLY
{improvements_text}

## PORTAL CONTEXT
```json
{json.dumps(portal_context, indent=2)[:1500] if portal_context else "Not available"}
```

## INSTRUCTIONS
1. Apply ALL the suggested improvements
2. Make sure the code remains complete and runnable
3. Do NOT remove any existing functionality
4. Add better error handling where appropriate
5. Ensure proper wait times for dynamic elements

## OUTPUT
Return ONLY the complete fixed Python code in a ```python block.
No explanations, just the code."""

        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )

        self.cost_tracker.add(
            "claude-sonnet-4-5-20250929",
            response.usage.input_tokens,
            response.usage.output_tokens
        )

        text = response.content[0].text

        # Extract code
        code_match = re.search(r'```python\s*(.*?)\s*```', text, re.DOTALL)
        if code_match:
            return code_match.group(1)

        return current_code  # Return original if no code found

    def generate_test_cases(self, portal_context: Dict) -> List[TestCase]:
        """Generate test cases from portal context"""
        test_cases = []

        dropdowns = portal_context.get("dropdowns", {})

        # Basic test case with first available options
        basic_data = {
            "name": "Test User",
            "mobile": "9876543210",
            "email": "test@example.com",
            "address": "123 Test Street"
        }

        # Add dropdown values from context
        for field_name, dropdown_info in dropdowns.items():
            options = dropdown_info.get("options", {})
            if options:
                # Get first non-empty option
                for opt_text, opt_value in options.items():
                    if opt_text and opt_text not in ["--Select--", "--Not Set--", ""]:
                        basic_data[field_name.lower().replace(" ", "_")] = opt_text
                        break

        test_cases.append(TestCase(
            name="Basic form fill",
            data=basic_data,
            priority=1
        ))

        # Test with different dropdown options
        for field_name, dropdown_info in list(dropdowns.items())[:2]:
            options = list(dropdown_info.get("options", {}).keys())
            valid_options = [o for o in options if o not in ["--Select--", "--Not Set--", ""]]

            if len(valid_options) >= 2:
                alt_data = basic_data.copy()
                alt_data[field_name.lower().replace(" ", "_")] = valid_options[1]

                test_cases.append(TestCase(
                    name=f"Alt {field_name}: {valid_options[1][:20]}",
                    data=alt_data,
                    priority=2
                ))

        return test_cases

    async def _store_successful_pattern(
        self,
        scraper_path: Path,
        portal_context: Optional[Dict],
        success_rate: float,
        cycles_needed: int
    ):
        """
        Store successful scraper pattern in the pattern library for future reuse.

        This completes the learning loop - improved scrapers contribute back
        to the pattern library, making future generations smarter.
        """
        try:
            from knowledge.pattern_library import PatternLibrary

            # Extract portal info
            portal_name = scraper_path.parent.name if scraper_path.parent.name != "scrapers" else scraper_path.stem
            form_url = portal_context.get("url", "") if portal_context else ""

            # Build form schema from context
            form_schema = {}
            if portal_context:
                form_schema = portal_context.get("structure", {})
                if not form_schema and "dropdowns" in portal_context:
                    form_schema = {
                        "fields": [
                            {"name": name, "type": "select", "options": list(info.get("options", {}).keys())}
                            for name, info in portal_context.get("dropdowns", {}).items()
                        ]
                    }

            if not form_schema.get("fields"):
                print("   ⚠️ No form schema available, skipping pattern storage")
                return

            # Read the improved code
            scraper_code = scraper_path.read_text()

            # Calculate confidence based on success rate and cycles needed
            # Higher success rate + fewer cycles = higher confidence
            confidence = success_rate * max(0.7, 1.0 - (cycles_needed - 1) * 0.1)

            # Store the pattern
            pl = PatternLibrary(enable_vector_store=False)
            success = pl.store_pattern(
                municipality_name=portal_name,
                form_url=form_url,
                form_schema=form_schema,
                generated_code=scraper_code,
                confidence_score=confidence,
                validation_attempts=cycles_needed,
                js_analysis=portal_context.get("js_analysis") if portal_context else None
            )

            if success:
                print(f"   📚 Improved pattern stored (confidence: {confidence:.0%}, success rate: {success_rate:.0%})")
            else:
                print(f"   ⚠️ Failed to store improved pattern")

        except ImportError:
            print("   ⚠️ Pattern library not available")
        except Exception as e:
            print(f"   ⚠️ Pattern storage error: {e}")

    def get_report(self) -> Dict[str, Any]:
        """Get comprehensive improvement report"""
        return {
            "total_cycles": len(self.quality_metrics.cycles),
            "best_success_rate": self.quality_metrics.best_success_rate,
            "final_success_rate": self.quality_metrics.cycles[-1].success_rate if self.quality_metrics.cycles else 0,
            "total_cost": self.quality_metrics.total_cost,
            "trend": self.quality_metrics.get_trend(),
            "cycles": [
                {
                    "cycle": c.cycle_number,
                    "success_rate": c.success_rate,
                    "tests_passed": sum(1 for r in c.test_results if r.success),
                    "tests_total": len(c.test_results),
                    "improvements_applied": len(c.improvements_made),
                    "cost": c.cost
                }
                for c in self.quality_metrics.cycles
            ]
        }


# CLI interface
async def main():
    """Test the continuous improvement agent"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python continuous_improvement_agent.py <scraper_path>")
        return

    scraper_path = sys.argv[1]

    # Load portal context if available
    portal_context = None
    context_path = Path(scraper_path).parent / "context"
    if context_path.exists():
        dropdowns_file = context_path / "dropdowns.json"
        if dropdowns_file.exists():
            with open(dropdowns_file) as f:
                portal_context = {"dropdowns": json.load(f)}

    agent = ContinuousImprovementAgent(
        max_cycles=3,
        target_success_rate=0.8,
        max_cost=1.0,
        headless=True
    )

    # Generate test cases from context or use defaults
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
        scraper_path=scraper_path,
        test_cases=test_cases,
        portal_context=portal_context
    )

    # Save report
    report = agent.get_report()
    report_path = Path("improvement_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
