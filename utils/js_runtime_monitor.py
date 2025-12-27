"""
JavaScript Runtime Monitor - Captures dynamic JavaScript behavior
Injects monitoring code to track AJAX calls, DOM mutations, and event handlers
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class JSRuntimeMonitor:
    """
    Monitors JavaScript execution in real-time to capture dynamic behavior
    """

    def __init__(self):
        self.events_captured = []
        self.monitoring_active = False

    def get_monitoring_script(self) -> str:
        """
        Get JavaScript code to inject into page for monitoring

        Returns:
            JavaScript code as string
        """
        return """
(function() {
    // Initialize event storage
    window.__grivredr_events = [];
    window.__grivredr_monitoring = true;

    console.log('[Grivredr] JS Runtime monitoring activated');

    // Helper to log events
    function logEvent(event) {
        window.__grivredr_events.push({
            ...event,
            timestamp: new Date().toISOString()
        });
    }

    // 1. INTERCEPT XMLHttpRequest (AJAX calls)
    const originalXHR = window.XMLHttpRequest;
    window.XMLHttpRequest = function() {
        const xhr = new originalXHR();

        // Track when request opens
        const originalOpen = xhr.open;
        xhr.open = function(method, url, ...args) {
            xhr.__method = method;
            xhr.__url = url;
            return originalOpen.apply(this, [method, url, ...args]);
        };

        // Track when request completes
        xhr.addEventListener('loadstart', function() {
            logEvent({
                type: 'ajax_start',
                method: xhr.__method,
                url: xhr.__url
            });
        });

        xhr.addEventListener('load', function() {
            logEvent({
                type: 'ajax_complete',
                method: xhr.__method,
                url: xhr.__url,
                status: xhr.status,
                responseLength: xhr.responseText ? xhr.responseText.length : 0
            });
        });

        xhr.addEventListener('error', function() {
            logEvent({
                type: 'ajax_error',
                method: xhr.__method,
                url: xhr.__url
            });
        });

        return xhr;
    };

    // 2. INTERCEPT fetch API
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const url = args[0];
        const options = args[1] || {};

        logEvent({
            type: 'fetch_start',
            url: url,
            method: options.method || 'GET'
        });

        return originalFetch.apply(this, args)
            .then(response => {
                logEvent({
                    type: 'fetch_complete',
                    url: url,
                    status: response.status,
                    ok: response.ok
                });
                return response;
            })
            .catch(error => {
                logEvent({
                    type: 'fetch_error',
                    url: url,
                    error: error.message
                });
                throw error;
            });
    };

    // 3. MONITOR DOM MUTATIONS
    const observer = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                // Track significant DOM additions (forms, inputs, selects)
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) {  // Element node
                        const tagName = node.tagName ? node.tagName.toLowerCase() : '';

                        if (['form', 'input', 'select', 'textarea', 'button'].includes(tagName)) {
                            logEvent({
                                type: 'dom_added',
                                tagName: tagName,
                                id: node.id || null,
                                className: node.className || null
                            });
                        }
                    }
                });
            }

            if (mutation.type === 'attributes') {
                const target = mutation.target;
                if (target.nodeType === 1) {
                    logEvent({
                        type: 'dom_attribute_changed',
                        tagName: target.tagName.toLowerCase(),
                        attribute: mutation.attributeName,
                        newValue: target.getAttribute(mutation.attributeName)
                    });
                }
            }
        });
    });

    // Start observing
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['class', 'style', 'disabled', 'hidden', 'value']
    });

    // 4. MONITOR FORM EVENTS
    document.addEventListener('change', function(e) {
        if (e.target && (e.target.tagName === 'SELECT' || e.target.tagName === 'INPUT')) {
            logEvent({
                type: 'form_change',
                tagName: e.target.tagName,
                id: e.target.id || null,
                name: e.target.name || null,
                value: e.target.type === 'password' ? '[REDACTED]' : (e.target.value ? e.target.value.substring(0, 50) : null)
            });
        }
    }, true);

    // 5. MONITOR DYNAMIC OPTION LOADING (common in cascading dropdowns)
    const originalAdd = HTMLSelectElement.prototype.add;
    HTMLSelectElement.prototype.add = function(option, before) {
        logEvent({
            type: 'dropdown_option_added',
            selectId: this.id || null,
            selectName: this.name || null,
            optionText: option.text,
            optionValue: option.value
        });
        return originalAdd.apply(this, [option, before]);
    };

    // 6. TRACK FORM VALIDATION
    document.addEventListener('invalid', function(e) {
        logEvent({
            type: 'validation_error',
            element: e.target.tagName,
            id: e.target.id || null,
            name: e.target.name || null,
            validationMessage: e.target.validationMessage
        });
    }, true);

    console.log('[Grivredr] Monitoring hooks installed');
})();
"""

    async def inject_monitoring(self, page) -> bool:
        """
        Inject monitoring script into page

        Args:
            page: Playwright page object

        Returns:
            True if successful
        """
        try:
            monitoring_script = self.get_monitoring_script()
            await page.evaluate(monitoring_script)
            self.monitoring_active = True
            logger.info("✓ JS monitoring injected successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to inject JS monitoring: {e}")
            return False

    async def capture_events(self, page, timeout: int = 2) -> List[Dict[str, Any]]:
        """
        Capture all events that have been logged

        Args:
            page: Playwright page object
            timeout: How long to wait for events (seconds)

        Returns:
            List of captured events
        """
        try:
            # Wait a bit for events to accumulate
            await asyncio.sleep(timeout)

            # Retrieve events from page
            events = await page.evaluate("window.__grivredr_events || []")

            self.events_captured = events
            logger.info(f"✓ Captured {len(events)} JS events")

            return events

        except Exception as e:
            logger.error(f"Failed to capture events: {e}")
            return []

    async def interact_with_form(self, page, form_selector: str = "form") -> None:
        """
        Interact with form elements to trigger JavaScript

        Args:
            page: Playwright page object
            form_selector: CSS selector for form element
        """
        try:
            logger.info("🖱️ Interacting with form to trigger JS...")

            # Find all input fields
            inputs = await page.query_selector_all(f"{form_selector} input[type='text'], {form_selector} input[type='email']")

            for i, input_elem in enumerate(inputs[:3]):  # Limit to first 3
                try:
                    # Focus and blur to trigger events
                    await input_elem.focus()
                    await asyncio.sleep(0.2)
                    await input_elem.type("test", delay=50)
                    await asyncio.sleep(0.2)
                    await input_elem.blur()
                except Exception as e:
                    logger.debug(f"Input interaction failed: {e}")

            # Find and click dropdowns to see options
            selects = await page.query_selector_all(f"{form_selector} select")

            for i, select_elem in enumerate(selects[:3]):  # Limit to first 3
                try:
                    await select_elem.click()
                    await asyncio.sleep(0.5)

                    # Get options
                    options = await select_elem.query_selector_all("option")
                    if len(options) > 1:
                        # Select second option (first is usually placeholder)
                        await options[1].click()
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.debug(f"Select interaction failed: {e}")

            logger.info("✓ Form interaction complete")

        except Exception as e:
            logger.warning(f"Form interaction partial: {e}")

    def analyze_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze captured events to identify patterns

        Args:
            events: List of captured events

        Returns:
            Analysis results
        """
        analysis = {
            "total_events": len(events),
            "ajax_calls": [],
            "fetch_calls": [],
            "dynamic_fields": [],
            "cascading_dropdowns": [],
            "validation_rules": [],
            "has_ajax": False,
            "has_dynamic_content": False,
            "requires_specific_order": False
        }

        dropdown_changes = {}

        for event in events:
            event_type = event.get("type", "")

            # Track AJAX calls
            if event_type == "ajax_complete":
                analysis["ajax_calls"].append({
                    "url": event.get("url"),
                    "method": event.get("method"),
                    "status": event.get("status")
                })
                analysis["has_ajax"] = True

            # Track fetch calls
            elif event_type == "fetch_complete":
                analysis["fetch_calls"].append({
                    "url": event.get("url"),
                    "status": event.get("status")
                })
                analysis["has_ajax"] = True

            # Track dynamically added fields
            elif event_type == "dom_added" and event.get("tagName") in ["input", "select", "textarea"]:
                analysis["dynamic_fields"].append({
                    "tag": event.get("tagName"),
                    "id": event.get("id"),
                    "class": event.get("className")
                })
                analysis["has_dynamic_content"] = True

            # Track dropdown option additions (indicates cascading)
            elif event_type == "dropdown_option_added":
                select_id = event.get("selectId") or event.get("selectName")
                if select_id not in dropdown_changes:
                    dropdown_changes[select_id] = []
                dropdown_changes[select_id].append(event.get("optionText"))

            # Track validation rules
            elif event_type == "validation_error":
                analysis["validation_rules"].append({
                    "element": event.get("element"),
                    "id": event.get("id"),
                    "message": event.get("validationMessage")
                })

        # Identify cascading dropdowns (dropdowns that get options added dynamically)
        for select_id, options in dropdown_changes.items():
            if len(options) > 1:  # More than 1 option added = likely cascading
                analysis["cascading_dropdowns"].append({
                    "select": select_id,
                    "options_added": len(options)
                })
                analysis["requires_specific_order"] = True

        logger.info(f"📊 Analysis: {analysis['total_events']} events, "
                   f"AJAX: {analysis['has_ajax']}, "
                   f"Dynamic: {analysis['has_dynamic_content']}, "
                   f"Cascading: {len(analysis['cascading_dropdowns'])}")

        return analysis

    def get_summary(self) -> str:
        """
        Get human-readable summary of findings

        Returns:
            Summary string
        """
        if not self.events_captured:
            return "No JavaScript events captured. Form may be static."

        analysis = self.analyze_events(self.events_captured)

        summary_parts = []

        if analysis["has_ajax"]:
            summary_parts.append(f"✓ Detected {len(analysis['ajax_calls'])} AJAX calls - form uses dynamic loading")

        if analysis["cascading_dropdowns"]:
            summary_parts.append(f"✓ Found {len(analysis['cascading_dropdowns'])} cascading dropdowns - must select in order")

        if analysis["dynamic_fields"]:
            summary_parts.append(f"✓ {len(analysis['dynamic_fields'])} fields added dynamically")

        if analysis["validation_rules"]:
            summary_parts.append(f"✓ {len(analysis['validation_rules'])} client-side validation rules detected")

        if not summary_parts:
            summary_parts.append("Form appears to be static with no dynamic JavaScript behavior")

        return "\n".join(summary_parts)
