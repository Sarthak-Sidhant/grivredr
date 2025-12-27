"""
JavaScript Analyzer Agent - Analyzes form submission logic and dynamic behavior
Determines if form can be replicated in Python or needs browser automation
"""
import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from playwright.async_api import async_playwright, Page, Browser

from agents.base_agent import BaseAgent, cost_tracker
from agents.form_discovery_agent import FormSchema
from config.ai_client import ai_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class JSEvent:
    """Captured JavaScript event"""
    event_type: str  # xhr, fetch, form_submit, validation, etc.
    timestamp: float
    details: Dict[str, Any]


@dataclass
class JSAnalysis:
    """Complete JavaScript analysis"""
    submission_method: str  # form_post, ajax_xhr, ajax_fetch, custom
    endpoint: str = ""
    http_method: str = "POST"
    requires_browser: bool = False
    replicable_in_python: bool = True
    python_equivalent: str = ""
    complexity_score: float = 0.0

    # Captured behaviors
    validation_logic: List[str] = field(default_factory=list)
    ajax_calls: List[Dict[str, Any]] = field(default_factory=list)
    dynamic_behaviors: List[str] = field(default_factory=list)
    csrf_token_required: bool = False
    csrf_token_selector: Optional[str] = None

    # Recommendations
    recommendation: str = ""
    warnings: List[str] = field(default_factory=list)


class JavaScriptAnalyzerAgent(BaseAgent):
    """
    Agent that analyzes JavaScript form behavior and determines automation strategy
    """

    def __init__(self, headless: bool = False):
        super().__init__(name="JSAnalyzerAgent", max_attempts=3)
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.playwright = None

    async def _execute_attempt(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute JavaScript analysis
        """
        url = task.get("url")
        schema_dict = task.get("schema")

        if not url:
            return {"success": False, "error": "No URL provided"}

        logger.info(f"🔬 [{self.name}] Analyzing JavaScript at {url}")

        await self._init_browser()

        try:
            # Phase 1: Inject monitoring code and capture events
            events = await self._capture_js_events(url)

            # Phase 2: Analyze captured events
            preliminary_analysis = self._analyze_events(events)

            # Phase 3: Ask Claude to interpret the behavior
            claude_analysis = await self._ask_claude_to_interpret(
                url, events, preliminary_analysis
            )

            # Phase 4: Determine automation strategy
            final_analysis = await self._determine_automation_strategy(
                claude_analysis, events
            )

            self._record_action(
                action_type="js_analysis",
                description="Completed JavaScript analysis",
                result=final_analysis.recommendation,
                success=True
            )

            return {
                "success": True,
                "message": f"Analysis complete: {final_analysis.submission_method}",
                "analysis": self._analysis_to_dict(final_analysis),
                "recommendation": final_analysis.recommendation
            }

        except Exception as e:
            logger.error(f"❌ [{self.name}] Analysis failed: {e}")
            return {"success": False, "error": str(e)}

        finally:
            await self._cleanup_browser()

    async def _init_browser(self):
        """Initialize Playwright browser"""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )

    async def _cleanup_browser(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def _capture_js_events(self, url: str) -> List[JSEvent]:
        """
        Capture JavaScript events by injecting monitoring code
        """
        logger.info(f"🎬 [{self.name}] Capturing JavaScript events")

        context = await self.browser.new_context()
        page = await context.new_page()
        events = []
        network_requests = []

        # ENHANCED: Monitor ALL network requests with full details
        async def handle_request(route, request):
            """Capture all network requests for API detection"""
            network_requests.append({
                'url': request.url,
                'method': request.method,
                'headers': dict(request.headers),
                'post_data': request.post_data,
                'resource_type': request.resource_type,
                'timestamp': time.time()
            })
            await route.continue_()

        async def handle_response(response):
            """Capture response data"""
            try:
                if response.request.resource_type in ['xhr', 'fetch']:
                    # This is an API call - capture the response
                    network_requests.append({
                        'type': 'response',
                        'url': response.url,
                        'status': response.status,
                        'headers': dict(await response.all_headers()),
                        'body': (await response.text())[:1000] if response.ok else None,  # First 1000 chars
                        'timestamp': time.time()
                    })
            except:
                pass

        # Intercept all network traffic
        await page.route('**/*', handle_request)
        page.on('response', handle_response)

        try:
            # Inject monitoring script
            await page.add_init_script("""
                window._grivredr_events = [];

                // Monitor XHR
                const oldXHR = window.XMLHttpRequest;
                window.XMLHttpRequest = function() {
                    const xhr = new oldXHR();
                    const oldSend = xhr.send;
                    const oldOpen = xhr.open;

                    let method, url;

                    xhr.open = function(m, u) {
                        method = m;
                        url = u;
                        return oldOpen.apply(xhr, arguments);
                    };

                    xhr.send = function(data) {
                        window._grivredr_events.push({
                            type: 'xhr',
                            timestamp: Date.now(),
                            method: method,
                            url: url,
                            data: data,
                            requestHeaders: {}
                        });

                        xhr.addEventListener('load', function() {
                            window._grivredr_events.push({
                                type: 'xhr_response',
                                timestamp: Date.now(),
                                status: xhr.status,
                                response: xhr.responseText?.substring(0, 500)
                            });
                        });

                        return oldSend.apply(xhr, arguments);
                    };

                    return xhr;
                };

                // Monitor fetch
                const oldFetch = window.fetch;
                window.fetch = function() {
                    const args = Array.from(arguments);
                    window._grivredr_events.push({
                        type: 'fetch',
                        timestamp: Date.now(),
                        url: args[0],
                        options: args[1]
                    });
                    return oldFetch.apply(window, arguments);
                };

                // Monitor form submissions
                document.addEventListener('submit', function(e) {
                    window._grivredr_events.push({
                        type: 'form_submit',
                        timestamp: Date.now(),
                        action: e.target.action,
                        method: e.target.method,
                        formData: Array.from(new FormData(e.target)).map(([k,v]) => [k, typeof v === 'string' ? v : '<file>'])
                    });
                }, true);

                // Monitor validation
                document.addEventListener('invalid', function(e) {
                    window._grivredr_events.push({
                        type: 'validation_error',
                        timestamp: Date.now(),
                        field: e.target.name || e.target.id,
                        message: e.target.validationMessage
                    });
                }, true);

                console.log('✅ Grivredr monitoring active');
            """)

            # Navigate to page
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Fill form with dummy data
            logger.info("   Filling form to trigger JS events...")
            await self._fill_dummy_form(page)

            # Wait a bit for AJAX calls
            await asyncio.sleep(2)

            # Try to submit
            logger.info("   Submitting form to capture submission logic...")
            try:
                await page.click("button[type='submit'], input[type='submit']", timeout=5000)
                await asyncio.sleep(2)
            except:
                logger.warning("   Could not click submit button")

            # Collect captured events
            captured = await page.evaluate("window._grivredr_events || []")

            logger.info(f"   📦 Captured {len(captured)} events")

            # Convert to JSEvent objects
            for event_data in captured:
                events.append(JSEvent(
                    event_type=event_data.get("type", "unknown"),
                    timestamp=event_data.get("timestamp", time.time() * 1000),
                    details=event_data
                ))

            # Add network requests as events
            for req in network_requests:
                events.append(JSEvent(
                    event_type='network_request' if req.get('method') else 'network_response',
                    timestamp=req.get('timestamp', time.time()) * 1000,
                    details=req
                ))

            logger.info(f"   🌐 Captured {len(network_requests)} network requests")

            return events

        except Exception as e:
            logger.error(f"Event capture failed: {e}")
            return events

        finally:
            await context.close()

    async def _fill_dummy_form(self, page: Page):
        """Fill form with dummy data to trigger events"""
        try:
            # Fill text inputs
            text_inputs = await page.query_selector_all("input[type='text'], input[type='email'], input[type='tel']")
            for inp in text_inputs[:5]:  # First 5
                try:
                    await inp.fill("test", timeout=1000)
                except:
                    pass

            # Fill textareas
            textareas = await page.query_selector_all("textarea")
            for ta in textareas[:2]:
                try:
                    await ta.fill("test comment", timeout=1000)
                except:
                    pass

            # Select first option in dropdowns
            selects = await page.query_selector_all("select")
            for sel in selects[:3]:
                try:
                    options = await sel.query_selector_all("option")
                    if len(options) > 1:
                        await options[1].click(timeout=1000)
                except:
                    pass

            await asyncio.sleep(1)

        except Exception as e:
            logger.warning(f"Dummy form fill failed: {e}")

    def _analyze_events(self, events: List[JSEvent]) -> Dict[str, Any]:
        """
        Analyze captured events for patterns
        """
        analysis = {
            "has_xhr": any(e.event_type == "xhr" for e in events),
            "has_fetch": any(e.event_type == "fetch" for e in events),
            "has_form_submit": any(e.event_type == "form_submit" for e in events),
            "validation_errors": [e for e in events if e.event_type == "validation_error"],
            "ajax_calls": [],
            "api_calls": [],  # NEW: Detailed API call tracking
            "submission_endpoint": None
        }

        # Extract AJAX calls
        for event in events:
            if event.event_type in ["xhr", "fetch"]:
                analysis["ajax_calls"].append({
                    "type": event.event_type,
                    "method": event.details.get("method", "GET"),
                    "url": event.details.get("url", ""),
                    "data": event.details.get("data", {})
                })

            # NEW: Extract full network requests for API detection
            if event.event_type == "network_request":
                resource_type = event.details.get("resource_type", "")
                if resource_type in ["xhr", "fetch"]:
                    analysis["api_calls"].append({
                        "url": event.details.get("url"),
                        "method": event.details.get("method"),
                        "headers": event.details.get("headers", {}),
                        "body": event.details.get("post_data"),
                        "resource_type": resource_type
                    })

            # NEW: Match responses to requests
            if event.event_type == "network_response":
                url = event.details.get("url")
                # Find matching request
                for api_call in analysis["api_calls"]:
                    if api_call["url"] == url and "response" not in api_call:
                        api_call["response"] = {
                            "status": event.details.get("status"),
                            "headers": event.details.get("headers", {}),
                            "body": event.details.get("body")
                        }
                        break

        # Determine submission endpoint
        form_submits = [e for e in events if e.event_type == "form_submit"]
        if form_submits:
            analysis["submission_endpoint"] = form_submits[-1].details.get("action", "")

        # Check for AJAX submission (XHR/fetch after form interaction)
        if (analysis["has_xhr"] or analysis["has_fetch"]) and not analysis["has_form_submit"]:
            # Likely AJAX submission
            if analysis["ajax_calls"]:
                last_call = analysis["ajax_calls"][-1]
                analysis["submission_endpoint"] = last_call["url"]

        return analysis

    async def _ask_claude_to_interpret(
        self,
        url: str,
        events: List[JSEvent],
        preliminary: Dict[str, Any]
    ) -> str:
        """
        Ask Claude to interpret the JavaScript behavior
        """
        logger.info(f"🤖 [{self.name}] Asking Claude to interpret JS behavior")

        # Format events for Claude
        events_summary = []
        for event in events[:20]:  # First 20 events
            events_summary.append({
                "type": event.event_type,
                "details": str(event.details)[:200]  # Truncate
            })

        prompt = f"""Analyze this form's JavaScript behavior from {url}.

**Captured Events:**
{json.dumps(events_summary, indent=2)}

**Preliminary Analysis:**
- Has XHR calls: {preliminary['has_xhr']}
- Has Fetch calls: {preliminary['has_fetch']}
- Has standard form submit: {preliminary['has_form_submit']}
- AJAX calls: {len(preliminary['ajax_calls'])}
- Submission endpoint: {preliminary.get('submission_endpoint', 'Unknown')}

**Your Task:**
1. How is this form actually submitted? (standard POST, AJAX XHR, AJAX fetch, custom)
2. What is the submission endpoint and HTTP method?
3. Is there client-side validation happening?
4. Can this be replicated with Python requests library, or does it need a browser?
5. Are there any complex behaviors (CSRF tokens, signatures, encryption)?

Return JSON:
{{
    "submission_method": "form_post|ajax_xhr|ajax_fetch|custom",
    "endpoint": "URL",
    "http_method": "POST|GET",
    "can_use_python_requests": true/false,
    "reasoning": "explanation",
    "csrf_token_needed": true/false,
    "complex_behaviors": ["list any unusual patterns"],
    "python_approach": "Brief description of how to replicate in Python"
}}
"""

        start_time = time.time()
        response = ai_client.client.messages.create(
            model=ai_client.models["powerful"],  # Opus for complex analysis
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000
        )
        elapsed = time.time() - start_time

        usage = response.usage
        cost = cost_tracker.track_call(
            model=ai_client.models["powerful"],
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            agent_name=self.name
        )

        self._record_action(
            action_type="claude_interpretation",
            description="Claude interpreted JS behavior",
            result=response.content[0].text[:200],
            success=True,
            cost=cost
        )

        return response.content[0].text

    async def _determine_automation_strategy(
        self,
        claude_response: str,
        events: List[JSEvent]
    ) -> JSAnalysis:
        """
        Determine final automation strategy based on analysis
        """
        import re

        # Parse Claude's JSON response
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', claude_response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
            except:
                json_match = re.search(r'\{.*\}', claude_response, re.DOTALL)
                data = json.loads(json_match.group(0)) if json_match else {}
        else:
            data = {}

        analysis = JSAnalysis(
            submission_method=data.get("submission_method", "unknown"),
            endpoint=data.get("endpoint", ""),
            http_method=data.get("http_method", "POST"),
            csrf_token_required=data.get("csrf_token_needed", False)
        )

        # Determine if browser is needed
        can_use_requests = data.get("can_use_python_requests", False)
        analysis.replicable_in_python = can_use_requests

        # Calculate complexity score
        complexity_factors = []

        if analysis.submission_method == "custom":
            complexity_factors.append(0.4)
        elif analysis.submission_method in ["ajax_xhr", "ajax_fetch"]:
            complexity_factors.append(0.2)

        if analysis.csrf_token_required:
            complexity_factors.append(0.2)

        complex_behaviors = data.get("complex_behaviors", [])
        if complex_behaviors:
            complexity_factors.append(0.1 * len(complex_behaviors))

        analysis.complexity_score = min(sum(complexity_factors), 1.0)
        analysis.dynamic_behaviors = complex_behaviors

        # Determine if browser is required
        if analysis.complexity_score > 0.5:
            analysis.requires_browser = True
        elif not can_use_requests:
            analysis.requires_browser = True

        # Generate recommendation
        if analysis.requires_browser:
            analysis.recommendation = (
                f"This form requires browser automation (Playwright). "
                f"Submission method: {analysis.submission_method}. "
                f"Complexity: {analysis.complexity_score:.0%}."
            )
        else:
            analysis.recommendation = (
                f"This form can be automated with Python requests library. "
                f"Endpoint: {analysis.endpoint}. "
                f"Method: {analysis.http_method}."
            )

        # Generate Python equivalent
        if analysis.replicable_in_python and not analysis.requires_browser:
            analysis.python_equivalent = f"""
import requests

def submit_form(data):
    response = requests.{analysis.http_method.lower()}(
        url="{analysis.endpoint}",
        data=data,
        headers={{
            "User-Agent": "Mozilla/5.0...",
            "X-Requested-With": "XMLHttpRequest"  # If AJAX
        }}
    )
    return response.json()
"""
        else:
            analysis.python_equivalent = f"""
# Requires Playwright
from playwright.async_api import async_playwright

async def submit_form(data):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        # Navigate and fill form
        # ...
"""

        logger.info(f"📊 [{self.name}] Strategy: {analysis.recommendation}")

        return analysis

    def _analysis_to_dict(self, analysis: JSAnalysis) -> Dict[str, Any]:
        """Convert JSAnalysis to dict"""
        return {
            "submission_method": analysis.submission_method,
            "endpoint": analysis.endpoint,
            "http_method": analysis.http_method,
            "requires_browser": analysis.requires_browser,
            "replicable_in_python": analysis.replicable_in_python,
            "complexity_score": analysis.complexity_score,
            "python_equivalent": analysis.python_equivalent,
            "validation_logic": analysis.validation_logic,
            "ajax_calls": analysis.ajax_calls,
            "dynamic_behaviors": analysis.dynamic_behaviors,
            "csrf_token_required": analysis.csrf_token_required,
            "csrf_token_selector": analysis.csrf_token_selector,
            "recommendation": analysis.recommendation,
            "warnings": analysis.warnings
        }


# For testing
async def test_js_analyzer():
    """Test the JS analyzer agent"""
    agent = JavaScriptAnalyzerAgent(headless=False)

    result = await agent.execute({
        "url": "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online"
    })

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(test_js_analyzer())
