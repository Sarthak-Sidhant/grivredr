"""
Tracking ID Extraction - Extract tracking/reference IDs from success pages

Consolidates the duplicate implementations in human_recorder_agent.py and test_agent.py.
"""
import re
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


# Common patterns for tracking IDs in Indian government portals
TRACKING_ID_PATTERNS = [
    # Explicit tracking ID labels
    r'tracking\s*(?:id|no|number)[:\s]*([A-Z0-9\-\/]+)',
    r'reference\s*(?:id|no|number)[:\s]*([A-Z0-9\-\/]+)',
    r'complaint\s*(?:id|no|number)[:\s]*([A-Z0-9\-\/]+)',
    r'registration\s*(?:id|no|number)[:\s]*([A-Z0-9\-\/]+)',
    r'ticket\s*(?:id|no|number)[:\s]*([A-Z0-9\-\/]+)',
    r'grievance\s*(?:id|no|number)[:\s]*([A-Z0-9\-\/]+)',

    # Common ID formats
    r'(?:ID|No|Number)[:\s]+([A-Z]{2,4}[\-\/]?\d{6,12})',  # e.g., GRV-123456
    r'(?:ID|No|Number)[:\s]+(\d{4}[\-\/]\d{6,8})',  # e.g., 2024/123456
    r'([A-Z]{2,5}\d{10,15})',  # e.g., CPGRMS2024123456

    # Fallback numeric patterns
    r'(?:successfully registered|submitted successfully)[.\s]+(?:your|the)?\s*(?:reference|tracking|complaint)?\s*(?:id|no|number)?[:\s]*([A-Z0-9\-\/]+)',
]


def extract_tracking_id(text: str, html: Optional[str] = None) -> Optional[str]:
    """
    Extract tracking/reference ID from success page text or HTML

    Args:
        text: Plain text content of the page
        html: Optional HTML content for additional parsing

    Returns:
        Extracted tracking ID or None
    """
    if not text:
        return None

    text_lower = text.lower()

    # Check if this looks like a success page
    success_indicators = [
        'success', 'submitted', 'registered', 'received',
        'thank you', 'complaint has been', 'reference number'
    ]

    is_success_page = any(indicator in text_lower for indicator in success_indicators)

    if not is_success_page:
        logger.debug("Page doesn't appear to be a success page")
        return None

    # Try each pattern
    for pattern in TRACKING_ID_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            tracking_id = match.group(1).strip()
            # Validate: should be at least 5 characters
            if len(tracking_id) >= 5:
                logger.info(f"Extracted tracking ID: {tracking_id}")
                return tracking_id

    # Try HTML-specific extraction if available
    if html:
        # Look for ID in specific elements
        html_patterns = [
            r'<span[^>]*class="[^"]*tracking[^"]*"[^>]*>([^<]+)</span>',
            r'<div[^>]*class="[^"]*reference[^"]*"[^>]*>([^<]+)</div>',
            r'<strong>([A-Z]{2,4}[\-\/]?\d{6,12})</strong>',
            r'<b>([A-Z]{2,4}[\-\/]?\d{6,12})</b>',
        ]

        for pattern in html_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                tracking_id = match.group(1).strip()
                if len(tracking_id) >= 5:
                    logger.info(f"Extracted tracking ID from HTML: {tracking_id}")
                    return tracking_id

    logger.warning("Could not extract tracking ID from page")
    return None


def extract_all_ids(text: str) -> List[str]:
    """
    Extract all potential tracking IDs from text

    Useful when multiple IDs might be present or for debugging.

    Args:
        text: Text content

    Returns:
        List of potential tracking IDs
    """
    ids = []

    for pattern in TRACKING_ID_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            match = match.strip()
            if len(match) >= 5 and match not in ids:
                ids.append(match)

    return ids


def validate_tracking_id(tracking_id: str) -> bool:
    """
    Validate if a string looks like a valid tracking ID

    Args:
        tracking_id: Potential tracking ID

    Returns:
        True if valid format
    """
    if not tracking_id:
        return False

    # Must be at least 5 characters
    if len(tracking_id) < 5:
        return False

    # Must contain at least one digit
    if not any(c.isdigit() for c in tracking_id):
        return False

    # Should be mostly alphanumeric with allowed separators
    allowed_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/')
    if not all(c.upper() in allowed_chars for c in tracking_id):
        return False

    return True


def format_tracking_id(tracking_id: str) -> str:
    """
    Format tracking ID for display

    Args:
        tracking_id: Raw tracking ID

    Returns:
        Formatted tracking ID
    """
    if not tracking_id:
        return ""

    # Clean up whitespace
    formatted = ' '.join(tracking_id.split())

    # Uppercase
    formatted = formatted.upper()

    return formatted


def extract_status_from_page(text: str) -> Dict[str, Any]:
    """
    Extract complaint status information from status check page

    Args:
        text: Text content of status page

    Returns:
        Dictionary with status information
    """
    result = {
        "status": "unknown",
        "last_updated": None,
        "remarks": None,
        "officer": None,
        "department": None
    }

    text_lower = text.lower()

    # Extract status
    status_patterns = {
        "pending": ["pending", "under review", "awaiting", "in queue"],
        "in_progress": ["in progress", "processing", "assigned", "being addressed"],
        "resolved": ["resolved", "completed", "closed", "addressed", "fixed"],
        "rejected": ["rejected", "declined", "cancelled", "invalid"],
    }

    for status, keywords in status_patterns.items():
        if any(keyword in text_lower for keyword in keywords):
            result["status"] = status
            break

    # Extract date
    date_patterns = [
        r'last\s*updated[:\s]*(\d{1,2}[\-\/]\d{1,2}[\-\/]\d{2,4})',
        r'date[:\s]*(\d{1,2}[\-\/]\d{1,2}[\-\/]\d{2,4})',
        r'on\s*(\d{1,2}[\-\/]\d{1,2}[\-\/]\d{2,4})',
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["last_updated"] = match.group(1)
            break

    # Extract remarks
    remarks_patterns = [
        r'remarks?[:\s]*(.+?)(?:\n|$)',
        r'comments?[:\s]*(.+?)(?:\n|$)',
        r'notes?[:\s]*(.+?)(?:\n|$)',
    ]

    for pattern in remarks_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            remarks = match.group(1).strip()
            if len(remarks) > 5:
                result["remarks"] = remarks[:200]  # Limit length
                break

    return result
