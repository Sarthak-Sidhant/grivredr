"""
Human-in-the-Loop Recorder Agent
Records human interactions with forms to generate perfect scrapers
No AI guessing - just records what you actually do!
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from playwright.async_api import async_playwright, Browser, Page

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RecordedAction:
    """Single recorded action"""
    action_type: str  # navigate, click, fill, select, wait, submit
    timestamp: float
    selector: Optional[str] = None
    value: Optional[Any] = None
    element_info: Optional[Dict] = None
    screenshot: Optional[str] = None


@dataclass
class RecordingSession:
    """Complete recording session"""
    url: str
    municipality: str
    start_time: float
    end_time: Optional[float] = None
    actions: List[RecordedAction] = None
    success: bool = False
    tracking_id: Optional[str] = None

    def __post_init__(self):
        if self.actions is None:
            self.actions = []


class HumanRecorderAgent:
    """
    Records human interactions with forms to learn perfect automation

    How it works:
    1. Opens browser (visible, not headless)
    2. Injects monitoring JavaScript
    3. Records every click, type, select
    4. Generates scraper from recorded actions
    """

    def __init__(self, headless: bool = False, auto_stop: bool = False, capture_screenshots: bool = True):
        self.headless = headless
        self.auto_stop = auto_stop
        self.capture_screenshots = capture_screenshots
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.recording_session: Optional[RecordingSession] = None
        self.screenshots_dir = Path("recordings/screenshots")
        self.recordings_dir = Path("recordings/sessions")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.action_count = 0
        self.claude_notes = []  # AI-generated notes about what's happening
        self.captured_actions = []  # Python-side action buffer (survives postbacks)
        self.network_logs = []  # Capture all network requests

    async def start_recording(self, url: str, municipality: str) -> Dict[str, Any]:
        """
        Start a recording session
        Opens browser and waits for human to fill form
        """
        logger.info(f"🎬 Starting recording session for {municipality}")
        logger.info(f"📍 URL: {url}")

        self.recording_session = RecordingSession(
            url=url,
            municipality=municipality,
            start_time=datetime.now().timestamp()
        )

        # Set up signal handler to save on exit
        import signal

        def save_and_exit(signum=None, frame=None):
            """Save recording before exiting"""
            logger.info("\n💾 Saving recording before exit...")
            self._save_recording_sync(municipality, url)
            raise KeyboardInterrupt()

        signal.signal(signal.SIGINT, save_and_exit)

        # Initialize browser
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=['--disable-blink-features=AutomationControlled']
        )

        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        # Capture ALL network requests and extract dropdown selections from POST data
        async def log_request(request):
            self.network_logs.append({
                'timestamp': datetime.now().timestamp(),
                'method': request.method,
                'url': request.url,
                'post_data': request.post_data if request.method == 'POST' else None
            })
            logger.info(f"🌐 Network: {request.method} {request.url[:80]}")

            # CRITICAL: Extract dropdown selection from ASP.NET postback data
            if request.method == 'POST' and request.post_data:
                try:
                    post_data = request.post_data
                    # Check if this is a dropdown postback
                    if '__EVENTTARGET' in post_data and 'ddl' in post_data.lower():
                        import re
                        # Extract the dropdown ID from __EVENTTARGET
                        target_match = re.search(r'name="__EVENTTARGET"\s*\n\s*(.+?)\s*\n', post_data)
                        if target_match:
                            dropdown_id = target_match.group(1).strip()
                            logger.info(f"🔍 Dropdown postback detected: {dropdown_id}")

                            # Find the selected value for this dropdown
                            # Format: Content-Disposition: form-data; name="ctl00$ContentPlaceHolder1$ddlProblem"\n\n123\n
                            value_pattern = rf'name="{re.escape(dropdown_id)}"\s*\n\s*(.+?)\s*\n'
                            value_match = re.search(value_pattern, post_data)
                            if value_match:
                                selected_value = value_match.group(1).strip()
                                logger.info(f"✅ DROPDOWN CAPTURED: {dropdown_id} = '{selected_value}'")

                                # Create a select action from POST data
                                action_data = {
                                    'type': 'select',
                                    'timestamp': datetime.now().timestamp() * 1000,
                                    'selector': f'#{dropdown_id.replace("$", "_")}',
                                    'value': selected_value,
                                    'elementInfo': {'name': dropdown_id, 'id': dropdown_id}
                                }
                                self.captured_actions.append(action_data)
                            else:
                                logger.warning(f"⚠️  Could not find value for {dropdown_id} in POST data")
                except Exception as e:
                    logger.warning(f"Error parsing POST data: {e}")

        page.on("request", log_request)

        # Navigate to URL
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(1)

        # Clear any previous recording from localStorage
        await page.evaluate("() => localStorage.removeItem('_recorderActions')")

        # Set up auto-reinject on navigation
        async def handle_navigation():
            """Re-inject recorder after navigation"""
            await asyncio.sleep(1)
            try:
                await self._inject_recorder(page)
                logger.info("🔄 Recorder re-injected after navigation")
            except:
                pass

        # Listen for page loads and re-inject
        page.on("load", lambda: asyncio.create_task(handle_navigation()))

        # Inject recording script
        await self._inject_recorder(page)

        # Add visual indicator that changes when recorder is ready
        await page.evaluate("""
            () => {
                const banner = document.createElement('div');
                banner.id = 'recording-banner';
                banner.style.cssText = `
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    background: #ff4444;
                    color: white;
                    padding: 15px;
                    text-align: center;
                    font-size: 18px;
                    font-weight: bold;
                    z-index: 999999;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                    transition: background 0.5s;
                `;
                banner.innerHTML = '⏳ INITIALIZING RECORDER - Please wait...';
                document.body.prepend(banner);

                // Change to green when ready
                setTimeout(() => {
                    banner.style.background = '#22c55e';
                    banner.innerHTML = '✅ RECORDER READY - You can now fill the form. Dropdowns will be captured!';
                    setTimeout(() => {
                        banner.style.background = '#ff4444';
                        banner.innerHTML = '🔴 RECORDING - Fill the form normally. Press Ctrl+C when done.';
                    }, 2000);
                }, 1000);
            }
        """)

        logger.info("=" * 80)
        logger.info("🎬 RECORDING ACTIVE!")
        logger.info("=" * 80)
        logger.info("")
        logger.info("⚠️  CRITICAL INSTRUCTIONS - READ CAREFULLY:")
        logger.info("")
        logger.info("  1. ⏳ WAIT for the banner to turn GREEN (says 'RECORDER READY')")
        logger.info("  2. ⏳ WAIT 2 more seconds after it turns green")
        logger.info("  3. ✅ NOW you can start filling the form")
        logger.info("  4. 📋 Select dropdowns SLOWLY (wait 1 second after each selection)")
        logger.info("  5. 📝 Fill all text fields")
        logger.info("  6. 🖱️  Click submit button")
        logger.info("  7. ⏹️  Press Ctrl+C here when done")
        logger.info("")
        logger.info("⚠️  IMPORTANT: If you select dropdowns TOO FAST, they won't be captured!")
        logger.info("")
        logger.info("The system is recording:")
        logger.info("  ✓ Every dropdown selection (if you wait for recorder)")
        logger.info("  ✓ Every field you fill")
        logger.info("  ✓ Every button you click")
        logger.info("  ✓ The exact selectors used")
        logger.info("")
        logger.info("=" * 80)

        # Wait for user to complete the form
        try:
            # Keep checking for recorded actions
            while True:
                try:
                    await asyncio.sleep(1)
                except asyncio.CancelledError:
                    # Handle Ctrl+C gracefully
                    logger.info("\n⏸️  Recording stopped by user (Ctrl+C)")
                    break

                # Get recorded actions from browser (handle navigation errors)
                try:
                    # IMMEDIATELY check localStorage after any navigation
                    # This runs EVERY second to catch actions before they're lost
                    actions = await page.evaluate("""
                        () => {
                            // ALWAYS read from localStorage first (survives postbacks)
                            try {
                                const stored = JSON.parse(localStorage.getItem('_recorderActions') || '[]');
                                if (stored.length > 0) {
                                    console.log('📊 Found', stored.length, 'actions in localStorage');
                                    window._recordedActions = stored;
                                    return stored;
                                }
                            } catch(e) {
                                console.error('❌ Error reading localStorage:', e);
                            }
                            return window._recordedActions || [];
                        }
                    """)
                except Exception as e:
                    # Page navigated - re-inject recorder
                    if "Execution context was destroyed" in str(e) or "navigation" in str(e).lower():
                        logger.info("🔄 Page navigated, re-injecting recorder...")
                        await asyncio.sleep(1)
                        try:
                            await self._inject_recorder(page)
                        except:
                            pass
                        continue
                    else:
                        raise

                if actions:
                    # Process new actions
                    for action_data in actions:
                        action = RecordedAction(
                            action_type=action_data.get('type'),
                            timestamp=action_data.get('timestamp'),
                            selector=action_data.get('selector'),
                            value=action_data.get('value'),
                            element_info=action_data.get('elementInfo')
                        )

                        # Check if action already recorded (use both timestamp AND selector to avoid duplicates)
                        already_recorded = any(
                            a.timestamp == action.timestamp and a.selector == action.selector
                            for a in self.recording_session.actions
                        )

                        if not already_recorded:
                            self.action_count += 1

                            # CRITICAL: Store in Python-side buffer immediately
                            self.captured_actions.append(action_data)

                            # Take screenshot for significant actions (not every keystroke)
                            if self.capture_screenshots and action.action_type in ['select', 'click', 'submit']:
                                screenshot_path = self.screenshots_dir / f"{municipality}_action_{self.action_count:03d}_{action.action_type}.png"
                                await page.screenshot(path=str(screenshot_path), full_page=False)
                                action.screenshot = str(screenshot_path)
                                logger.info(f"📸 Screenshot: {screenshot_path.name}")

                            self.recording_session.actions.append(action)

                            # Get human-readable description
                            field_label = action.element_info.get('placeholder', '') or action.element_info.get('name', '')
                            if action.action_type == 'fill':
                                logger.info(f"📝 [{self.action_count}] Typed in '{field_label}': {action.value}")
                            elif action.action_type == 'select':
                                logger.info(f"✅ [{self.action_count}] DROPDOWN SELECTED: '{action.value}' in '{field_label}'")
                            elif action.action_type == 'click':
                                logger.info(f"🖱️  [{self.action_count}] Clicked: {action.value or field_label}")
                            elif action.action_type == 'submit':
                                logger.info(f"📤 [{self.action_count}] Form submitted")

                    # Don't clear buffer anymore - we want to accumulate actions
                    # (localStorage will persist them across postbacks)
                    # await page.evaluate("() => window._recordedActions = []")

                    # Every 5 actions, analyze what's happening with Claude
                    if self.action_count > 0 and self.action_count % 5 == 0:
                        await self._analyze_session_progress(page, municipality)

                # Check if form was submitted (look for success indicators)
                # Only check if we have at least one submit/click action
                has_submit = any(a.action_type in ['submit', 'click'] for a in self.recording_session.actions)

                success_detected = False
                if has_submit:
                    success_detected = await page.evaluate("""
                        () => {
                            // Look for very specific success patterns
                            const body = document.body;
                            const text = body.innerText.toLowerCase();

                            // Check if there's a success message element (more reliable)
                            const successElements = body.querySelectorAll(
                                '.success, .alert-success, [class*="success"], ' +
                                '[id*="success"], .confirmation, [class*="confirmation"]'
                            );

                            if (successElements.length > 0) {
                                // Check if any of these are actually visible
                                for (const elem of successElements) {
                                    if (elem.offsetParent !== null && elem.textContent.trim()) {
                                        return true;
                                    }
                                }
                            }

                            // Look for tracking/complaint ID patterns
                            const hasTrackingId = /complaint\s*(?:id|number).*?[A-Z0-9]{5,}/i.test(text) ||
                                                 /tracking\s*(?:id|number).*?[A-Z0-9]{5,}/i.test(text);

                            if (hasTrackingId) {
                                return true;
                            }

                            // Check if URL changed (common after successful submission)
                            const urlChanged = window.location.href.includes('success') ||
                                             window.location.href.includes('confirmation') ||
                                             window.location.href.includes('thank');

                            if (urlChanged) {
                                return true;
                            }

                            return false;
                        }
                    """)

                if self.auto_stop and success_detected and len(self.recording_session.actions) > 5:
                    logger.info("✅ Success detected! Finishing recording...")

                    # Try to extract tracking ID
                    tracking_id = await self._extract_tracking_id(page)
                    if tracking_id:
                        self.recording_session.tracking_id = tracking_id
                        logger.info(f"🎫 Tracking ID: {tracking_id}")

                    # Take final screenshot
                    screenshot_path = self.screenshots_dir / f"{municipality}_success_{int(datetime.now().timestamp())}.png"
                    await page.screenshot(path=str(screenshot_path), full_page=True)
                    logger.info(f"📸 Success screenshot: {screenshot_path}")

                    break

        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("\n⏸️  Recording stopped by user (Ctrl+C detected)")

        # Finalize recording
        self.recording_session.end_time = datetime.now().timestamp()
        self.recording_session.success = len(self.recording_session.actions) > 0

        # Save recording (using helper method)
        recording_file = self._save_recording_sync(municipality, url)

        logger.info(f"📊 Recorded {len(self.recording_session.actions)} actions")

        # Clean up
        await self.browser.close()
        await self.playwright.stop()

        return {
            'success': True,
            'recording_file': str(recording_file),
            'actions_count': len(self.recording_session.actions),
            'tracking_id': self.recording_session.tracking_id
        }

    def _save_recording_sync(self, municipality: str, url: str) -> Path:
        """Save recording synchronously (for signal handlers)"""
        # Use Python-side buffer if recording_session actions are empty
        if not self.recording_session:
            logger.warning("No recording session")
            return None

        if len(self.recording_session.actions) == 0 and len(self.captured_actions) == 0:
            logger.warning("No actions to save")
            return None

        # If recording_session is empty but we have captured_actions, restore them
        if len(self.recording_session.actions) == 0 and len(self.captured_actions) > 0:
            logger.info(f"📦 Restoring {len(self.captured_actions)} actions from Python buffer")
            for action_data in self.captured_actions:
                action = RecordedAction(
                    action_type=action_data.get('type'),
                    timestamp=action_data.get('timestamp'),
                    selector=action_data.get('selector'),
                    value=action_data.get('value'),
                    element_info=action_data.get('elementInfo')
                )
                self.recording_session.actions.append(action)

        # Finalize if not already done
        if not self.recording_session.end_time:
            self.recording_session.end_time = datetime.now().timestamp()

        recording_file = self.recordings_dir / f"{municipality}_{int(self.recording_session.start_time)}.json"

        # Extract dropdown options before saving
        logger.info(f"📋 Extracting dropdown options for future use...")
        dropdown_options = {}
        try:
            dropdown_options = asyncio.run(self._extract_dropdown_options_from_recording(
                self.recording_session.url,
                self.recording_session.actions
            ))
        except Exception as e:
            logger.warning(f"Could not extract dropdown options: {e}")

        with open(recording_file, 'w') as f:
            json.dump({
                'url': self.recording_session.url,
                'municipality': self.recording_session.municipality,
                'start_time': self.recording_session.start_time,
                'end_time': self.recording_session.end_time,
                'actions': [asdict(a) for a in self.recording_session.actions],
                'tracking_id': self.recording_session.tracking_id,
                'claude_notes': self.claude_notes,
                'total_actions': self.action_count,
                'network_logs': self.network_logs,  # Include network activity
                'dropdown_options': dropdown_options  # Include dropdown options
            }, f, indent=2)

        # Also save a human-readable summary
        summary_file = self.recordings_dir / f"{municipality}_{int(self.recording_session.start_time)}_NOTES.md"
        with open(summary_file, 'w') as f:
            f.write(f"# Recording Session Summary\n\n")
            f.write(f"**Municipality:** {municipality}\n")
            f.write(f"**URL:** {url}\n")
            f.write(f"**Total Actions:** {self.action_count}\n")
            f.write(f"**Duration:** {self.recording_session.end_time - self.recording_session.start_time:.1f}s\n\n")

            if self.claude_notes:
                f.write(f"## Claude's Observations\n\n")
                for note in self.claude_notes:
                    f.write(f"### After {note['action_count']} actions\n")
                    f.write(f"{note['note']}\n\n")

            f.write(f"## Actions Recorded\n\n")
            for i, action in enumerate(self.recording_session.actions, 1):
                field_name = action.element_info.get('name', 'unknown') if action.element_info else 'unknown'
                f.write(f"{i}. **{action.action_type}** - {field_name}")
                if action.value:
                    f.write(f" = `{action.value}`")
                f.write("\n")

        logger.info(f"📄 Summary saved: {summary_file}")
        logger.info(f"💾 Recording saved: {recording_file}")

        return recording_file

    async def _inject_recorder(self, page: Page):
        """Inject JavaScript to record user interactions"""
        await page.evaluate("""
            () => {
                // Initialize recording array
                window._recordedActions = [];

                // Restore actions from localStorage (in case of postback)
                try {
                    const stored = JSON.parse(localStorage.getItem('_recorderActions') || '[]');
                    if (stored.length > 0) {
                        console.log('🔄 Restored ' + stored.length + ' actions from localStorage after postback');
                        window._recordedActions = stored;
                    }
                } catch(e) {}

                // Helper to get best selector for an element
                function getBestSelector(element) {
                    // Prefer ID
                    if (element.id) {
                        return '#' + element.id;
                    }

                    // Try name attribute
                    if (element.name) {
                        return `[name="${element.name}"]`;
                    }

                    // Try data attributes
                    const dataId = element.getAttribute('data-id');
                    if (dataId) {
                        return `[data-id="${dataId}"]`;
                    }

                    // Build CSS path
                    const path = [];
                    let current = element;
                    while (current && current.nodeType === Node.ELEMENT_NODE) {
                        let selector = current.nodeName.toLowerCase();
                        if (current.className) {
                            selector += '.' + current.className.split(' ').join('.');
                        }
                        path.unshift(selector);
                        current = current.parentElement;

                        // Stop at form or main container
                        if (current && (current.tagName === 'FORM' || current.id)) {
                            if (current.id) {
                                path.unshift('#' + current.id);
                            }
                            break;
                        }
                    }
                    return path.join(' > ');
                }

                // Helper to get element info
                function getElementInfo(element) {
                    return {
                        tagName: element.tagName.toLowerCase(),
                        type: element.type || element.tagName.toLowerCase(),
                        id: element.id,
                        name: element.name,
                        className: element.className,
                        placeholder: element.placeholder,
                        value: element.value,
                        text: element.textContent?.substring(0, 100)
                    };
                }

                // Record input changes
                document.addEventListener('input', (e) => {
                    const element = e.target;
                    if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                        const action = {
                            type: 'fill',
                            timestamp: Date.now(),
                            selector: getBestSelector(element),
                            value: element.value,
                            elementInfo: getElementInfo(element)
                        };

                        window._recordedActions.push(action);

                        // Persist to localStorage
                        try {
                            localStorage.setItem('_recorderActions', JSON.stringify(window._recordedActions));
                        } catch(e) {}
                    }
                }, true);

                // NEW APPROACH: Capture dropdown clicks BEFORE selection happens
                // This intercepts at mousedown/click level, before change event
                document.addEventListener('mousedown', (e) => {
                    const element = e.target.closest('select') || e.target;
                    if (element.tagName === 'SELECT') {
                        // Store the current value BEFORE change
                        element.dataset._previousValue = element.value;
                        console.log('👆 Mousedown on dropdown:', element.id);
                    }
                }, true);

                // Capture IMMEDIATELY when dropdown changes (before postback)
                document.addEventListener('change', (e) => {
                    const element = e.target;
                    if (element.tagName === 'SELECT') {
                        const selectedOption = element.options[element.selectedIndex];
                        const action = {
                            type: 'select',
                            timestamp: Date.now(),
                            selector: getBestSelector(element),
                            value: selectedOption?.text || element.value,
                            elementInfo: getElementInfo(element)
                        };

                        console.log('🎯 DROPDOWN CHANGED:', action.selector, '→', action.value);

                        // Save to BOTH localStorage AND a global array
                        window._recordedActions.push(action);

                        try {
                            const stored = JSON.parse(localStorage.getItem('_recorderActions') || '[]');
                            stored.push(action);
                            localStorage.setItem('_recorderActions', JSON.stringify(stored));
                            console.log('✅ SAVED TO LOCALSTORAGE:', stored.length, 'total actions');
                        } catch(err) {
                            console.error('❌ FAILED:', err);
                        }
                    }
                }, true);

                // Intercept ASP.NET __doPostBack to capture actions before postback
                if (typeof __doPostBack !== 'undefined') {
                    const original__doPostBack = __doPostBack;
                    window.__doPostBack = function(eventTarget, eventArgument) {
                        console.log('⚡ POSTBACK TRIGGERED:', eventTarget);

                        // CRITICAL: Save all actions to localStorage before postback
                        try {
                            if (window._recordedActions.length > 0) {
                                localStorage.setItem('_recorderActions', JSON.stringify(window._recordedActions));
                                console.log('💾 Saved', window._recordedActions.length, 'actions before postback');
                            }
                        } catch(e) {
                            console.error('❌ Failed to save before postback:', e);
                        }

                        return original__doPostBack(eventTarget, eventArgument);
                    };
                    console.log('✅ Intercepted __doPostBack');
                }

                // Also save on page unload (backup)
                window.addEventListener('beforeunload', () => {
                    try {
                        if (window._recordedActions.length > 0) {
                            localStorage.setItem('_recorderActions', JSON.stringify(window._recordedActions));
                            console.log('💾 Saved on beforeunload:', window._recordedActions.length, 'actions');
                        }
                    } catch(e) {}
                });

                // Record clicks on buttons/links
                document.addEventListener('click', (e) => {
                    const element = e.target;
                    if (element.tagName === 'BUTTON' ||
                        element.tagName === 'A' ||
                        element.type === 'submit' ||
                        element.classList.contains('btn')) {
                        window._recordedActions.push({
                            type: 'click',
                            timestamp: Date.now(),
                            selector: getBestSelector(element),
                            value: element.textContent?.trim() || element.value,
                            elementInfo: getElementInfo(element)
                        });
                    }
                }, true);

                // Record form submissions
                document.addEventListener('submit', (e) => {
                    const form = e.target;
                    window._recordedActions.push({
                        type: 'submit',
                        timestamp: Date.now(),
                        selector: getBestSelector(form),
                        value: null,
                        elementInfo: getElementInfo(form)
                    });
                }, true);

                console.log('🎬 Recording script injected successfully!');
            }
        """)

        logger.info("✅ Recording script injected")

    async def _analyze_session_progress(self, page: Page, municipality: str):
        """Use Claude to analyze what the user is doing"""
        try:
            # Take a quick screenshot
            screenshot_path = self.screenshots_dir / f"{municipality}_analysis_{int(datetime.now().timestamp())}.png"
            await page.screenshot(path=str(screenshot_path))

            # Get recent actions summary
            recent_actions = self.recording_session.actions[-5:]
            actions_summary = "\n".join([
                f"- {a.action_type}: {a.element_info.get('name', 'unknown')} = {a.value}"
                for a in recent_actions
            ])

            # Prepare screenshot for Claude
            import base64
            with open(screenshot_path, 'rb') as f:
                screenshot_base64 = base64.b64encode(f.read()).decode()

            # Ask Claude what's happening
            from config.ai_client import ai_client

            response = ai_client.client.messages.create(
                model=ai_client.models["fast"],  # Use Haiku for speed
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
                            "text": f"""Analyze this grievance form submission in progress.

Recent actions by human:
{actions_summary}

Provide a brief 1-2 sentence summary of:
1. What section of the form they're filling
2. What type of information is being entered
3. Any observations about the form structure

Be concise and helpful."""
                        }
                    ]
                }],
                temperature=0.3,
                max_tokens=200
            )

            note = response.content[0].text
            self.claude_notes.append({
                'timestamp': datetime.now().timestamp(),
                'action_count': self.action_count,
                'note': note,
                'screenshot': str(screenshot_path)
            })

            logger.info("=" * 60)
            logger.info(f"🤖 Claude's Analysis (after {self.action_count} actions):")
            logger.info(f"   {note}")
            logger.info("=" * 60)

        except Exception as e:
            logger.debug(f"Claude analysis failed (non-critical): {e}")

    async def _extract_tracking_id(self, page: Page) -> Optional[str]:
        """Try to extract tracking/complaint ID from success page"""
        import re

        page_text = await page.evaluate("() => document.body.innerText")

        # Common patterns for tracking IDs
        patterns = [
            r'complaint\s*(?:id|number|no\.?)\s*:?\s*([A-Z0-9-]+)',
            r'tracking\s*(?:id|number|no\.?)\s*:?\s*([A-Z0-9-]+)',
            r'reference\s*(?:id|number|no\.?)\s*:?\s*([A-Z0-9-]+)',
            r'([A-Z]{2,5}\d{5,10})',
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def generate_scraper_from_recording(
        self,
        recording_file: str,
        output_dir: Optional[str] = None,
        extract_dropdown_options: bool = True
    ) -> str:
        """
        Generate a working scraper from recorded actions
        No AI needed - just translates your actions to code!
        """
        logger.info(f"🔧 Generating scraper from recording: {recording_file}")

        # Load recording
        with open(recording_file, 'r') as f:
            recording_data = json.load(f)

        municipality = recording_data['municipality']
        url = recording_data['url']
        actions = recording_data['actions']

        if output_dir is None:
            output_dir = f"outputs/generated_scrapers/{municipality}"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Use saved dropdown options if available, otherwise extract them
        dropdown_options_map = recording_data.get('dropdown_options', {})

        if not dropdown_options_map and extract_dropdown_options:
            logger.info(f"📋 No saved options found. Extracting dropdown options from form...")
            dropdown_options_map = asyncio.run(self._extract_dropdown_options(url, actions))
        elif dropdown_options_map:
            logger.info(f"✅ Using saved dropdown options from recording")

        # Save to knowledge base for natural language queries
        if dropdown_options_map:
            self._save_to_knowledge_base(municipality, url, dropdown_options_map)

        # Generate scraper code
        scraper_code = self._generate_scraper_code(municipality, url, actions, dropdown_options_map)

        scraper_file = output_path / f"{municipality}_scraper.py"
        with open(scraper_file, 'w') as f:
            f.write(scraper_code)

        logger.info(f"✅ Scraper generated: {scraper_file}")

        return str(scraper_file)

    def _save_to_knowledge_base(self, municipality: str, url: str, dropdown_options: Dict[str, List[Dict]]):
        """Save dropdown options to knowledge base for NLP queries"""
        from utils.field_query import FieldQueryEngine

        knowledge_dir = Path("knowledge")
        knowledge_dir.mkdir(exist_ok=True)

        knowledge_file = knowledge_dir / f"{municipality}_field_mappings.json"

        # Check if file already exists
        if knowledge_file.exists():
            logger.info(f"📚 Knowledge base already exists: {knowledge_file}")
            return

        # Build searchable mappings
        field_mappings = {}

        for selector, options in dropdown_options.items():
            # Extract field name from selector
            field_name = selector.split('_')[-1].lower()
            if 'ddl' in selector.lower():
                field_name = selector.split('ddl')[-1].lower()

            # Clean field name
            field_name = field_name.replace('$', '').replace('_', '')

            # Build searchable index
            searchable_values = {}
            for opt in options:
                value = opt['value']
                text = opt['text']

                if value and text and value != '0':  # Skip empty/default options
                    # Add original text (lowercase)
                    text_lower = text.lower().strip()
                    searchable_values[text_lower] = value

                    # Add simplified versions for better matching
                    # Remove special chars and extra spaces
                    simplified = re.sub(r'[^\w\s]', ' ', text_lower)
                    simplified = re.sub(r'\s+', ' ', simplified).strip()
                    if simplified != text_lower:
                        searchable_values[simplified] = value

            field_mappings[field_name] = {
                "field_id": selector.replace('#', '').replace('_', '$'),
                "selector": selector,
                "label": field_name.replace('_', ' ').title(),
                "type": "select",
                "required": True,
                "searchable_values": searchable_values
            }

        # Save to knowledge base
        knowledge_data = {
            "municipality": municipality,
            "url": url,
            "field_mappings": field_mappings
        }

        with open(knowledge_file, 'w') as f:
            json.dump(knowledge_data, f, indent=2)

        logger.info(f"💾 Saved knowledge base: {knowledge_file}")
        logger.info(f"   Fields: {', '.join(field_mappings.keys())}")
        logger.info(f"   Total searchable values: {sum(len(f['searchable_values']) for f in field_mappings.values())}")

    async def _extract_dropdown_options_from_recording(self, url: str, actions: List) -> Dict[str, List[Dict]]:
        """Extract dropdown options from recorded actions (wrapper for compatibility)"""
        # Convert RecordedAction objects to dicts if needed
        actions_dicts = []
        for a in actions:
            if hasattr(a, '__dict__'):
                actions_dicts.append(asdict(a))
            else:
                actions_dicts.append(a)
        return await self._extract_dropdown_options(url, actions_dicts)

    async def _extract_dropdown_options(self, url: str, actions: List[Dict]) -> Dict[str, List[Dict]]:
        """Extract all options from dropdowns in the form"""
        from playwright.async_api import async_playwright

        dropdown_options = {}
        select_actions = [a for a in actions if a.get('action_type') == 'select']

        if not select_actions:
            return dropdown_options

        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Extract options from each dropdown
            for action in select_actions:
                selector = action.get('selector', '')
                if selector:
                    try:
                        options = await page.evaluate(f"""
                            (selector) => {{
                                const select = document.querySelector(selector);
                                if (!select) return [];
                                return Array.from(select.options).map(opt => ({{
                                    value: opt.value,
                                    text: opt.text.trim()
                                }})).filter(o => o.value && o.text);
                            }}
                        """, selector)

                        if options:
                            dropdown_options[selector] = options
                            logger.info(f"   Found {len(options)} options for {selector}")
                    except Exception as e:
                        logger.debug(f"Could not extract options for {selector}: {e}")

            await browser.close()
            await playwright.stop()
        except Exception as e:
            logger.warning(f"Could not extract dropdown options: {e}")

        return dropdown_options

    def _generate_scraper_code(
        self,
        municipality: str,
        url: str,
        actions: List[Dict],
        dropdown_options_map: Dict[str, List[Dict]] = None
    ) -> str:
        """Generate Python scraper code from recorded actions"""

        # Group fill actions by selector and keep only the LAST value per field
        # (since we record every keystroke, we only want the final result)
        fill_actions_map = {}
        for action in actions:
            if action['action_type'] == 'fill':
                selector = action['selector']
                fill_actions_map[selector] = action  # Overwrites previous, keeping last

        fill_actions = list(fill_actions_map.values())

        # Keep all select and click actions (these are discrete, not keystrokes)
        select_actions = [a for a in actions if a['action_type'] == 'select']
        click_actions = [a for a in actions if a['action_type'] == 'click']

        logger.info(f"Grouped {len(actions)} actions into {len(fill_actions)} fill, {len(select_actions)} select, {len(click_actions)} click actions")

        # Generate fill statements
        fill_code = ""
        for action in fill_actions:
            selector = action['selector']
            # Extract a better field name from the selector or element info
            element_info = action.get('elementInfo', {})

            # Try to get a meaningful field name
            if element_info.get('name'):
                raw_name = element_info['name']
            elif element_info.get('id'):
                raw_name = element_info['id']
            else:
                raw_name = selector.strip('#')

            # Clean up ASP.NET field names (e.g., ctl00$ContentPlaceHolder1$txtComplaintName -> name)
            if 'Name' in raw_name:
                field_name = 'name'
            elif 'Mobile' in raw_name:
                field_name = 'mobile'
            elif 'Contact' in raw_name:
                field_name = 'contact'
            elif 'Email' in raw_name:
                field_name = 'email'
            elif 'Address' in raw_name:
                field_name = 'address'
            elif 'Remark' in raw_name:
                field_name = 'remarks'
            elif 'attach' in raw_name.lower():
                field_name = 'attachment'
            else:
                field_name = raw_name.lower().replace('ctl00_contentplaceholder1_', '').replace('txt', '').replace('complaint', '')

            fill_code += f"""            # Fill {field_name}
            try:
                await page.fill("{selector}", grievance_data.get('{field_name}', ''), timeout=5000)
                logger.info(f"✓ Filled {field_name}")
            except Exception as e:
                logger.warning(f"Could not fill {field_name}: {{e}}")
"""

        # Generate select statements with Select2 support
        select_code = ""
        for action in select_actions:
            selector = action['selector']
            raw_selector = action.get('elementInfo', {}).get('id', selector.strip('#'))
            field_name = action.get('elementInfo', {}).get('name', 'dropdown')
            value = action.get('value', '')

            # Map to user-friendly field name
            if 'Problem' in raw_selector or 'ddlProblem' in raw_selector:
                field_name = 'problem_type'
            elif 'Ward' in raw_selector:
                field_name = 'ward' if 'ddlWard' == raw_selector.split('_')[-1] else 'area'
            elif 'Area' in raw_selector:
                field_name = 'area'
            elif 'Mode' in raw_selector or 'complaint_mode' in raw_selector.lower():
                field_name = 'complaint_mode'

            # Add available options as comments
            options_comment = ""
            if dropdown_options_map and selector in dropdown_options_map:
                options_comment = f"\n            # Available options for {field_name}:\n"
                for opt in dropdown_options_map[selector][:10]:  # Show first 10
                    options_comment += f"            #   '{opt['value']}' = '{opt['text']}'\n"
                if len(dropdown_options_map[selector]) > 10:
                    options_comment += f"            #   ... and {len(dropdown_options_map[selector]) - 10} more\n"

            select_code += f"""{options_comment}            # Select {field_name}
            try:
                # Handle Select2 dropdown (hidden select element)
                value = grievance_data.get('{field_name}', '{value}')
                await page.evaluate('''({{selector, value}}) => {{
                    const select = document.querySelector(selector);
                    if (select) {{
                        select.value = value;
                        // Trigger change event
                        const event = new Event('change', {{ bubbles: true }});
                        select.dispatchEvent(event);

                        // Also trigger Select2 change if it exists
                        if (window.jQuery && jQuery(select).data('select2')) {{
                            jQuery(select).trigger('change');
                        }}
                    }}
                }}''', {{"selector": "{selector}", "value": value}})

                # Wait for any postback to complete
                await asyncio.sleep(2)
                logger.info(f"✓ Selected {field_name}")
            except Exception as e:
                logger.warning(f"Could not select {field_name}: {{e}}")
"""

        # Find submit button
        submit_selector = None
        for action in click_actions:
            if 'submit' in action.get('elementInfo', {}).get('type', '').lower():
                submit_selector = action['selector']
                break

        if not submit_selector and click_actions:
            submit_selector = click_actions[-1]['selector']  # Last click is probably submit

        # Generate complete scraper
        code = f'''"""
Auto-generated scraper from human recording
Municipality: {municipality}
URL: {url}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

This scraper was generated by recording a human filling the form.
It replicates the exact actions performed.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Browser, Page

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class {municipality.title()}Scraper:
    """
    Scraper for {municipality} grievance portal
    Generated from human recording session
    """

    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.base_url = "{url}"
        self.headless = headless
        self.timeout = timeout
        self._browser: Optional[Browser] = None

    async def submit_grievance(self, grievance_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a grievance using recorded actions

        Args:
            grievance_data: Dictionary with field names and values

        Returns:
            Result dictionary with success status and tracking ID
        """
        logger.info(f"🚀 Submitting grievance to {{self.base_url}}")

        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(headless=self.headless)

        try:
            context = await self._browser.new_context()
            page = await context.new_page()

            # Navigate
            logger.info(f"📍 Navigating to {{self.base_url}}")
            await page.goto(self.base_url, wait_until="networkidle", timeout=self.timeout)
            await asyncio.sleep(2)

{fill_code}
{select_code}

            # Submit form
            logger.info("📤 Submitting form...")
            try:
                await page.click("{submit_selector or 'button[type=submit]'}", timeout=5000)
                await asyncio.sleep(3)
                logger.info("✓ Form submitted")
            except Exception as e:
                logger.error(f"Failed to submit: {{e}}")
                return {{'success': False, 'error': str(e)}}

            # Check for success
            page_text = await page.evaluate("() => document.body.innerText.toLowerCase()")
            success = any(word in page_text for word in ['success', 'submitted', 'registered', 'thank you'])

            if success:
                logger.info("✅ Submission successful!")

                # Try to extract tracking ID
                tracking_id = await self._extract_tracking_id(page, page_text)

                return {{
                    'success': True,
                    'tracking_id': tracking_id,
                    'message': 'Grievance submitted successfully'
                }}
            else:
                logger.warning("⚠️  Could not confirm success")
                return {{
                    'success': False,
                    'error': 'Success confirmation not found'
                }}

        except Exception as e:
            logger.error(f"❌ Submission failed: {{e}}")
            return {{'success': False, 'error': str(e)}}

        finally:
            await self._browser.close()
            await playwright.stop()

    async def _extract_tracking_id(self, page: Page, page_text: str) -> Optional[str]:
        """Extract tracking ID from success page"""
        import re

        patterns = [
            r'complaint\\s*(?:id|number|no\\.?)\\s*:?\\s*([A-Z0-9-]+)',
            r'tracking\\s*(?:id|number|no\\.?)\\s*:?\\s*([A-Z0-9-]+)',
            r'([A-Z]{{2,5}}\\d{{5,10}})',
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None


# Test function
async def test_scraper():
    """Test the scraper with sample data"""
    scraper = {municipality.title()}Scraper(headless=False)

    # Sample data - replace with actual field names
    test_data = {{
        'name': 'Test User',
        'phone': '9876543210',
        'email': 'test@example.com',
        'complaint': 'Test complaint for validation',
        'address': 'Test Address, City - 123456'
    }}

    result = await scraper.submit_grievance(test_data)
    print(result)


if __name__ == "__main__":
    asyncio.run(test_scraper())
'''

        return code


# CLI interface
async def main():
    """CLI for recording sessions"""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m agents.human_recorder_agent <municipality> <url>")
        print()
        print("Example:")
        print("  python -m agents.human_recorder_agent ranchi https://smartranchi.in/...")
        sys.exit(1)

    municipality = sys.argv[1]
    url = sys.argv[2]

    recorder = HumanRecorderAgent(headless=False)
    result = await recorder.start_recording(url, municipality)

    if result['success']:
        print()
        print("=" * 80)
        print("✅ RECORDING COMPLETE!")
        print("=" * 80)
        print(f"📊 Recorded {result['actions_count']} actions")
        print(f"💾 Saved to: {result['recording_file']}")
        if result.get('tracking_id'):
            print(f"🎫 Tracking ID: {result['tracking_id']}")
        print()
        print("Next step: Generate scraper from recording")
        print(f"  python -c 'from agents.human_recorder_agent import HumanRecorderAgent; import asyncio; r = HumanRecorderAgent(); print(r.generate_scraper_from_recording(\"{result['recording_file']}\"))'")
        print()


if __name__ == "__main__":
    asyncio.run(main())
