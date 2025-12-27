#!/usr/bin/env python3
"""
Scraper Validator - Self-healing validation loop for generated scrapers

Runs the generated scraper, captures errors, and uses AI to fix issues
until the scraper works correctly.
"""
import asyncio
import json
import os
import re
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
import anthropic
from playwright.async_api import async_playwright, Page, Browser, Error as PlaywrightError
import base64

from dotenv import load_dotenv
load_dotenv()


@dataclass
class ValidationResult:
    """Result of a single validation attempt"""
    success: bool
    attempt: int
    error: Optional[str] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None
    screenshot_base64: Optional[str] = None
    page_url: Optional[str] = None
    fields_filled: List[str] = field(default_factory=list)
    fields_failed: List[str] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class FixResult:
    """Result of an AI code fix attempt"""
    success: bool
    changes_made: List[str] = field(default_factory=list)
    reasoning: str = ""
    new_code: str = ""
    cost: float = 0.0


class CostTracker:
    """Track API costs"""
    PRICING = {
        "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
        "claude-opus-4-5-20250929": {"input": 15.0, "output": 75.0},
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


class ScreenshotVerifier:
    """Verify form state using screenshots and AI vision"""

    def __init__(self, client: anthropic.Anthropic, cost_tracker: CostTracker):
        self.client = client
        self.cost_tracker = cost_tracker

    async def verify_screenshot(
        self,
        screenshot_base64: str,
        verification_query: str,
        context: str = ""
    ) -> Dict[str, Any]:
        """
        Use AI vision to verify something about the screenshot

        Args:
            screenshot_base64: Base64 encoded screenshot
            verification_query: What to verify (e.g., "Is the dropdown open?")
            context: Additional context about what we're doing

        Returns:
            Dict with verification result
        """
        prompt = f"""Analyze this screenshot of a web form and answer the following question:

QUESTION: {verification_query}

CONTEXT: {context}

Respond with JSON:
{{
    "answer": "yes" | "no" | "unclear",
    "confidence": 0.0-1.0,
    "observation": "what you see in the screenshot",
    "issues_detected": ["list of any problems visible"],
    "suggestions": ["list of suggestions if issues found"]
}}"""

        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]
        )

        self.cost_tracker.add(
            "claude-sonnet-4-5-20250929",
            response.usage.input_tokens,
            response.usage.output_tokens
        )

        # Parse response
        text = response.content[0].text
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass

        return {
            "answer": "unclear",
            "confidence": 0.0,
            "observation": text,
            "issues_detected": [],
            "suggestions": []
        }

    async def verify_form_state(
        self,
        screenshot_base64: str,
        expected_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify the form is in the expected state

        Args:
            screenshot_base64: Screenshot of current form state
            expected_state: What we expect to see
                - fields_filled: List of field names that should be filled
                - dropdown_selected: Dict of dropdown -> expected value
                - no_errors: Whether there should be no validation errors
        """
        queries = []

        if expected_state.get("fields_filled"):
            fields = ", ".join(expected_state["fields_filled"])
            queries.append(f"Are these fields visibly filled with values: {fields}?")

        if expected_state.get("dropdown_selected"):
            for dropdown, value in expected_state["dropdown_selected"].items():
                queries.append(f"Does the {dropdown} dropdown show '{value}' as selected?")

        if expected_state.get("no_errors", True):
            queries.append("Are there any visible error messages or validation warnings on the form?")

        combined_query = "\n".join(f"{i+1}. {q}" for i, q in enumerate(queries))

        return await self.verify_screenshot(
            screenshot_base64,
            combined_query,
            "Verifying form state after filling fields"
        )


class CodeCorrectionAgent:
    """AI agent that fixes scraper code based on runtime errors"""

    def __init__(self, client: anthropic.Anthropic, cost_tracker: CostTracker):
        self.client = client
        self.cost_tracker = cost_tracker

    async def fix_code(
        self,
        current_code: str,
        error: str,
        error_type: str,
        stack_trace: str,
        screenshot_base64: Optional[str] = None,
        page_html: Optional[str] = None,
        previous_fixes: List[str] = None,
        dropdown_context: Optional[Dict] = None
    ) -> FixResult:
        """
        Analyze error and generate fixed code

        Args:
            current_code: Current scraper code
            error: Error message
            error_type: Type of error (e.g., "TimeoutError", "ElementNotFound")
            stack_trace: Full stack trace
            screenshot_base64: Screenshot when error occurred
            page_html: HTML of page when error occurred (truncated)
            previous_fixes: List of previous fix attempts (to avoid repeating)
            dropdown_context: Known dropdown options from discovery

        Returns:
            FixResult with new code and explanation
        """
        # Build the prompt
        prompt_parts = [
            "You are a code correction agent for Playwright web scrapers.",
            "",
            "## ERROR DETAILS",
            f"**Error Type:** {error_type}",
            f"**Error Message:** {error}",
            "",
            "**Stack Trace:**",
            f"```\n{stack_trace}\n```",
            "",
            "## CURRENT CODE",
            f"```python\n{current_code}\n```",
        ]

        if previous_fixes:
            prompt_parts.extend([
                "",
                "## PREVIOUS FIX ATTEMPTS (DO NOT REPEAT THESE)",
                *[f"- {fix}" for fix in previous_fixes]
            ])

        if dropdown_context:
            prompt_parts.extend([
                "",
                "## KNOWN DROPDOWN OPTIONS",
                f"```json\n{json.dumps(dropdown_context, indent=2)[:2000]}\n```"
            ])

        if page_html:
            # Truncate HTML to relevant portion
            html_snippet = page_html[:3000] if len(page_html) > 3000 else page_html
            prompt_parts.extend([
                "",
                "## PAGE HTML (truncated)",
                f"```html\n{html_snippet}\n```"
            ])

        prompt_parts.extend([
            "",
            "## YOUR TASK",
            "1. Analyze why the error occurred",
            "2. Generate COMPLETE fixed Python code",
            "3. Explain what you changed and why",
            "",
            "## COMMON FIXES",
            "- TimeoutError: Add more wait time, use different selector, wait for element",
            "- ElementNotFound: Check selector, element might be in iframe, dynamically loaded",
            "- Select2/Ant-Design: Use correct interaction pattern for the framework",
            "- Cascade issues: Wait after parent selection before filling child",
            "",
            "## OUTPUT FORMAT",
            "Respond with:",
            "1. ANALYSIS: Why the error occurred",
            "2. CHANGES: List of specific changes made",
            "3. CODE: Complete fixed Python code in ```python block",
            "",
            "IMPORTANT: Output the COMPLETE code, not just the changed parts."
        ])

        prompt = "\n".join(prompt_parts)

        # Include screenshot if available
        messages_content = []
        if screenshot_base64:
            messages_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot_base64
                }
            })

        messages_content.append({
            "type": "text",
            "text": prompt
        })

        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8000,
            messages=[{"role": "user", "content": messages_content}]
        )

        cost = self.cost_tracker.add(
            "claude-sonnet-4-5-20250929",
            response.usage.input_tokens,
            response.usage.output_tokens
        )

        text = response.content[0].text

        # Extract code from response
        code_match = re.search(r'```python\s*(.*?)\s*```', text, re.DOTALL)
        new_code = code_match.group(1) if code_match else ""

        # Extract changes list
        changes = []
        changes_match = re.search(r'CHANGES?:?\s*(.*?)(?=CODE:|```|$)', text, re.DOTALL | re.IGNORECASE)
        if changes_match:
            changes_text = changes_match.group(1)
            changes = [line.strip().lstrip('- •') for line in changes_text.split('\n') if line.strip() and line.strip().startswith(('-', '•', '*'))]

        # Extract reasoning
        analysis_match = re.search(r'ANALYSIS:?\s*(.*?)(?=CHANGES?:|$)', text, re.DOTALL | re.IGNORECASE)
        reasoning = analysis_match.group(1).strip() if analysis_match else ""

        # Validate syntax before returning
        if new_code:
            try:
                compile(new_code, '<string>', 'exec')
            except SyntaxError as e:
                logger = __import__('logging').getLogger(__name__)
                logger.warning(f"Generated code has syntax error: {e}")
                # Try to fix common issues
                new_code = self._fix_common_syntax_errors(new_code)
                try:
                    compile(new_code, '<string>', 'exec')
                except SyntaxError:
                    # Still broken, return failure
                    return FixResult(
                        success=False,
                        changes_made=["Syntax error in generated code"],
                        reasoning=f"AI generated code with syntax error: {e}",
                        new_code="",
                        cost=cost
                    )

        return FixResult(
            success=bool(new_code),
            changes_made=changes,
            reasoning=reasoning,
            new_code=new_code,
            cost=cost
        )

    def _fix_common_syntax_errors(self, code: str) -> str:
        """Try to fix common syntax errors in generated code"""
        import re

        # Fix unclosed strings
        lines = code.split('\n')
        fixed_lines = []

        for line in lines:
            # Count quotes
            single_quotes = line.count("'") - line.count("\\'")
            double_quotes = line.count('"') - line.count('\\"')

            # If odd number of quotes, might be unclosed string
            if single_quotes % 2 != 0:
                # Try to close it
                if "'" in line and not line.rstrip().endswith("'"):
                    line = line.rstrip() + "'"

            if double_quotes % 2 != 0:
                if '"' in line and not line.rstrip().endswith('"'):
                    line = line.rstrip() + '"'

            fixed_lines.append(line)

        return '\n'.join(fixed_lines)


class ScraperValidator:
    """
    Self-healing validation loop for generated scrapers

    Runs the scraper, captures errors, uses AI to fix, and repeats
    until successful or max attempts reached.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        screenshot_dir: str = "screenshots/validation",
        headless: bool = True
    ):
        self.max_attempts = max_attempts
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless

        self.api_key = os.getenv("api_key")
        self.client = anthropic.Anthropic(
            api_key=self.api_key,
            base_url="https://ai.megallm.io"
        )
        self.cost_tracker = CostTracker()

        self.screenshot_verifier = ScreenshotVerifier(self.client, self.cost_tracker)
        self.code_corrector = CodeCorrectionAgent(self.client, self.cost_tracker)

        self.validation_history: List[ValidationResult] = []
        self.fix_history: List[FixResult] = []

    async def validate_scraper(
        self,
        scraper_path: str,
        test_data: Dict[str, Any],
        portal_context: Optional[Dict] = None,
        dry_run: bool = True
    ) -> Tuple[bool, str, List[ValidationResult]]:
        """
        Validate a scraper with self-healing loop

        Args:
            scraper_path: Path to the scraper Python file
            test_data: Test data to fill the form with
            portal_context: Context from discovery (dropdowns, cascades, etc.)
            dry_run: If True, don't actually submit the form

        Returns:
            Tuple of (success, final_scraper_path, validation_history)
        """
        scraper_path = Path(scraper_path)

        if not scraper_path.exists():
            raise FileNotFoundError(f"Scraper not found: {scraper_path}")

        print(f"\n{'='*60}")
        print("SCRAPER VALIDATION - Self-Healing Loop")
        print(f"{'='*60}")
        print(f"Scraper: {scraper_path}")
        print(f"Max attempts: {self.max_attempts}")
        print(f"Dry run: {dry_run}")
        print(f"{'='*60}\n")

        previous_fixes = []

        for attempt in range(1, self.max_attempts + 1):
            print(f"\n[Attempt {attempt}/{self.max_attempts}]")

            # Run the scraper
            result = await self._run_scraper_test(
                scraper_path,
                test_data,
                attempt,
                dry_run=dry_run
            )

            self.validation_history.append(result)

            if result.success:
                print(f"✅ Validation PASSED on attempt {attempt}")
                print(f"   Fields filled: {len(result.fields_filled)}")
                print(f"   Total cost: ${self.cost_tracker.total_cost:.4f}")

                # Store successful pattern in library for future reuse
                await self._store_successful_pattern(
                    scraper_path=scraper_path,
                    portal_context=portal_context,
                    validation_attempts=attempt
                )

                return True, str(scraper_path), self.validation_history

            print(f"❌ Attempt {attempt} failed: {result.error_type}")
            print(f"   Error: {result.error[:100]}..." if result.error else "   Unknown error")

            if attempt < self.max_attempts:
                # Try to fix the code
                print(f"\n🔧 Attempting AI code fix...")

                current_code = scraper_path.read_text()

                fix_result = await self.code_corrector.fix_code(
                    current_code=current_code,
                    error=result.error or "Unknown error",
                    error_type=result.error_type or "Unknown",
                    stack_trace=result.stack_trace or "",
                    screenshot_base64=result.screenshot_base64,
                    previous_fixes=previous_fixes,
                    dropdown_context=portal_context.get("dropdowns") if portal_context else None
                )

                self.fix_history.append(fix_result)

                if fix_result.success and fix_result.new_code:
                    print(f"   Fix applied: {len(fix_result.changes_made)} changes")
                    for change in fix_result.changes_made[:3]:
                        print(f"   - {change[:60]}...")

                    # Save fixed code
                    scraper_path.write_text(fix_result.new_code)
                    previous_fixes.extend(fix_result.changes_made)

                    print(f"   Cost: ${fix_result.cost:.4f}")
                else:
                    print(f"   ⚠️ AI could not generate fix")
                    break

        print(f"\n❌ Validation FAILED after {self.max_attempts} attempts")
        print(f"   Total cost: ${self.cost_tracker.total_cost:.4f}")
        return False, str(scraper_path), self.validation_history

    async def _run_scraper_test(
        self,
        scraper_path: Path,
        test_data: Dict[str, Any],
        attempt: int,
        dry_run: bool = True
    ) -> ValidationResult:
        """Run the scraper and capture results"""

        start_time = datetime.now()
        result = ValidationResult(success=False, attempt=attempt)

        browser = None
        playwright = None

        try:
            # Import the scraper dynamically
            import importlib.util
            spec = importlib.util.spec_from_file_location("scraper", scraper_path)
            scraper_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(scraper_module)

            # Find the form filler class
            filler_class = None
            for name, obj in vars(scraper_module).items():
                if name.endswith("FormFiller") and isinstance(obj, type):
                    filler_class = obj
                    break

            if not filler_class:
                result.error = "No FormFiller class found in scraper"
                result.error_type = "ImportError"
                return result

            # Create instance and run
            filler = filler_class(headless=self.headless)

            try:
                await filler.start()
                result.page_url = filler.page.url if filler.page else None

                # Fill the form
                await filler.fill_form(test_data)

                # Take screenshot after filling
                screenshot_path = self.screenshot_dir / f"attempt_{attempt}_filled.png"
                await filler.page.screenshot(path=str(screenshot_path))
                result.screenshot_path = str(screenshot_path)

                # Read screenshot as base64 for AI analysis
                with open(screenshot_path, "rb") as f:
                    result.screenshot_base64 = base64.b64encode(f.read()).decode()

                # Verify the form state using AI vision
                verification = await self.screenshot_verifier.verify_screenshot(
                    result.screenshot_base64,
                    "Are all form fields filled correctly? Are there any visible error messages or validation warnings?",
                    f"Form was filled with test data. Checking for issues."
                )

                if verification.get("issues_detected"):
                    result.validation_errors = verification["issues_detected"]
                    result.error = f"Visual verification found issues: {verification['issues_detected']}"
                    result.error_type = "ValidationError"
                elif verification.get("answer") == "no":
                    result.error = f"Form not filled correctly: {verification.get('observation', '')}"
                    result.error_type = "FillError"
                else:
                    # If not dry_run, we would submit here
                    if not dry_run:
                        # Check if submit method exists
                        if hasattr(filler, 'submit'):
                            await filler.submit()

                            # Take post-submit screenshot
                            await asyncio.sleep(2)
                            post_screenshot = self.screenshot_dir / f"attempt_{attempt}_submitted.png"
                            await filler.page.screenshot(path=str(post_screenshot))

                    result.success = True
                    result.fields_filled = list(test_data.keys())

            finally:
                await filler.close()

        except PlaywrightError as e:
            result.error = str(e)
            result.error_type = type(e).__name__
            result.stack_trace = traceback.format_exc()

            # Try to take error screenshot
            try:
                if 'filler' in locals() and filler.page:
                    error_screenshot = self.screenshot_dir / f"attempt_{attempt}_error.png"
                    await filler.page.screenshot(path=str(error_screenshot))
                    result.screenshot_path = str(error_screenshot)
                    with open(error_screenshot, "rb") as f:
                        result.screenshot_base64 = base64.b64encode(f.read()).decode()
            except:
                pass

        except Exception as e:
            result.error = str(e)
            result.error_type = type(e).__name__
            result.stack_trace = traceback.format_exc()

        finally:
            result.duration_seconds = (datetime.now() - start_time).total_seconds()

        return result

    async def dry_run(
        self,
        scraper_path: str,
        test_data: Dict[str, Any],
        take_screenshots: bool = True
    ) -> Dict[str, Any]:
        """
        Run scraper without submitting - just verify form fills correctly

        Args:
            scraper_path: Path to scraper
            test_data: Test data to fill
            take_screenshots: Whether to capture screenshots at each step

        Returns:
            Detailed report of the dry run
        """
        print(f"\n{'='*60}")
        print("DRY RUN - Form Fill Verification")
        print(f"{'='*60}\n")

        success, final_path, history = await self.validate_scraper(
            scraper_path=scraper_path,
            test_data=test_data,
            dry_run=True
        )

        report = {
            "success": success,
            "scraper_path": final_path,
            "attempts": len(history),
            "fixes_applied": len(self.fix_history),
            "total_cost": self.cost_tracker.total_cost,
            "validation_history": [
                {
                    "attempt": r.attempt,
                    "success": r.success,
                    "error": r.error,
                    "error_type": r.error_type,
                    "screenshot": r.screenshot_path,
                    "fields_filled": r.fields_filled,
                    "validation_errors": r.validation_errors,
                    "duration": r.duration_seconds
                }
                for r in history
            ],
            "fix_history": [
                {
                    "changes": f.changes_made,
                    "reasoning": f.reasoning[:200],
                    "cost": f.cost
                }
                for f in self.fix_history
            ]
        }

        return report

    async def _store_successful_pattern(
        self,
        scraper_path: Path,
        portal_context: Optional[Dict],
        validation_attempts: int
    ):
        """
        Store successful scraper pattern in the pattern library for future reuse.

        This is the key to pattern learning - when validation succeeds,
        we store the working code so future similar portals can benefit.
        """
        try:
            from knowledge.pattern_library import PatternLibrary

            # Extract portal info from context or path
            portal_name = scraper_path.parent.name if scraper_path.parent.name != "scrapers" else scraper_path.stem
            form_url = portal_context.get("url", "") if portal_context else ""

            # Build form schema from context
            form_schema = {}
            if portal_context:
                form_schema = portal_context.get("structure", {})
                if not form_schema and "dropdowns" in portal_context:
                    # Build minimal schema from dropdowns
                    form_schema = {
                        "fields": [
                            {"name": name, "type": "select", "options": list(info.get("options", {}).keys())}
                            for name, info in portal_context.get("dropdowns", {}).items()
                        ]
                    }

            if not form_schema.get("fields"):
                print("   ⚠️ No form schema available, skipping pattern storage")
                return

            # Read the successful code
            scraper_code = scraper_path.read_text()

            # Calculate confidence based on validation attempts
            # Fewer attempts = higher confidence (worked faster)
            confidence = max(0.5, 1.0 - (validation_attempts - 1) * 0.15)

            # Store the pattern
            pl = PatternLibrary(enable_vector_store=False)  # Skip vector for speed
            success = pl.store_pattern(
                municipality_name=portal_name,
                form_url=form_url,
                form_schema=form_schema,
                generated_code=scraper_code,
                confidence_score=confidence,
                validation_attempts=validation_attempts,
                js_analysis=portal_context.get("js_analysis") if portal_context else None
            )

            if success:
                print(f"   📚 Pattern stored in library (confidence: {confidence:.0%})")
            else:
                print(f"   ⚠️ Failed to store pattern")

        except ImportError:
            print("   ⚠️ Pattern library not available")
        except Exception as e:
            print(f"   ⚠️ Pattern storage error: {e}")

    def get_summary(self) -> str:
        """Get human-readable summary of validation"""
        lines = [
            f"\nValidation Summary",
            f"{'='*40}",
            f"Total attempts: {len(self.validation_history)}",
            f"Successful: {sum(1 for r in self.validation_history if r.success)}",
            f"Fixes applied: {len(self.fix_history)}",
            f"Total cost: ${self.cost_tracker.total_cost:.4f}",
        ]

        if self.validation_history:
            last = self.validation_history[-1]
            lines.append(f"Final status: {'✅ PASSED' if last.success else '❌ FAILED'}")
            if not last.success and last.error:
                lines.append(f"Last error: {last.error[:100]}")

        return "\n".join(lines)


# CLI interface
async def main():
    """Test the validator"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python scraper_validator.py <scraper_path> [--submit]")
        print("\nExample:")
        print("  python scraper_validator.py scrapers/ranchi_smart/ranchi_smart_scraper.py")
        return

    scraper_path = sys.argv[1]
    dry_run = "--submit" not in sys.argv

    # Sample test data
    test_data = {
        "problem": "Water Supply",
        "area": "Doranda",
        "name": "Test User",
        "mobile": "9876543210",
        "email": "test@example.com",
        "address": "123 Test Street, Ranchi",
        "remarks": "Test complaint for validation"
    }

    validator = ScraperValidator(
        max_attempts=3,
        headless=True
    )

    report = await validator.dry_run(
        scraper_path=scraper_path,
        test_data=test_data
    )

    print(validator.get_summary())

    # Save report
    report_path = Path("validation_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
