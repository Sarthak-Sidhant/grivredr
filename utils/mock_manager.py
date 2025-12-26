"""
Mock Manager - Prevents real submissions during scraper testing
"""
import logging
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

logger = logging.getLogger(__name__)


class MockManager:
    """
    Manages mocking of browser operations and API calls during test mode
    """

    def __init__(self):
        self.mocked_operations = []
        self.captured_calls = []

    def create_mock_browser_context(self):
        """
        Create a mock browser context that simulates real behavior
        but doesn't make actual network calls
        """
        mock_context = MagicMock()

        # Mock successful operations
        mock_context.goto = self._mock_goto
        mock_context.click = self._mock_click
        mock_context.fill = self._mock_fill
        mock_context.select_option = self._mock_select_option
        mock_context.screenshot = self._mock_screenshot

        return mock_context

    def _mock_goto(self, url: str, **kwargs):
        """Mock page navigation"""
        logger.info(f"[MOCK] Navigating to: {url}")
        self.captured_calls.append({"operation": "goto", "url": url})
        return MagicMock()

    def _mock_click(self, selector: str, **kwargs):
        """Mock click operation"""
        logger.info(f"[MOCK] Clicking: {selector}")
        self.captured_calls.append({"operation": "click", "selector": selector})
        return MagicMock()

    def _mock_fill(self, selector: str, value: str, **kwargs):
        """Mock fill operation"""
        logger.info(f"[MOCK] Filling {selector} with: {value[:50]}...")
        self.captured_calls.append({
            "operation": "fill",
            "selector": selector,
            "value": value
        })
        return MagicMock()

    def _mock_select_option(self, selector: str, value: str, **kwargs):
        """Mock select operation"""
        logger.info(f"[MOCK] Selecting {value} in: {selector}")
        self.captured_calls.append({
            "operation": "select_option",
            "selector": selector,
            "value": value
        })
        return MagicMock()

    def _mock_screenshot(self, **kwargs):
        """Mock screenshot operation"""
        logger.info("[MOCK] Taking screenshot")
        self.captured_calls.append({"operation": "screenshot"})
        return b"mock_screenshot_data"

    def get_captured_calls(self) -> list:
        """Get all captured operations"""
        return self.captured_calls

    def verify_operation_sequence(self, expected_operations: list) -> bool:
        """
        Verify that operations were called in expected order

        Args:
            expected_operations: List of operation names like ["goto", "fill", "click"]

        Returns:
            True if operations match expected sequence
        """
        actual_operations = [call["operation"] for call in self.captured_calls]
        return actual_operations == expected_operations

    def verify_selector_used(self, selector: str) -> bool:
        """Check if a specific selector was used"""
        for call in self.captured_calls:
            if call.get("selector") == selector:
                return True
        return False

    def reset(self):
        """Reset captured calls"""
        self.captured_calls = []
        logger.info("[MOCK] Reset captured calls")


class PlaywrightMockContext:
    """
    Context manager for mocking Playwright operations during tests
    """

    def __init__(self, test_mode: bool = True):
        self.test_mode = test_mode
        self.mock_manager = MockManager()
        self.patches = []

    def __enter__(self):
        if not self.test_mode:
            return self.mock_manager

        # Patch Playwright async operations
        self.patches.append(
            patch('playwright.async_api.async_playwright')
        )

        # Start all patches
        for p in self.patches:
            p.start()

        logger.info("[MOCK] Playwright mock context activated")
        return self.mock_manager

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.test_mode:
            return

        # Stop all patches
        for p in self.patches:
            p.stop()

        logger.info("[MOCK] Playwright mock context deactivated")
