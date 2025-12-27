"""
Code Extraction Utilities - Extract code from markdown and AI responses

Consolidates the 4+ duplicate implementations of markdown code extraction
found across the codebase.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def extract_code_from_markdown(text: str, language: str = "python") -> str:
    """
    Extract code from markdown code blocks in AI responses

    Handles various formats:
    - ```python\ncode\n```
    - ```\ncode\n```
    - Raw code without blocks

    Args:
        text: Text potentially containing markdown code blocks
        language: Expected language (default: python)

    Returns:
        Extracted code or original text if no code block found
    """
    if not text:
        return ""

    # Try language-specific code block first
    pattern = rf'```{language}\s*(.*?)\s*```'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        logger.debug(f"Extracted {language} code block")
        return match.group(1).strip()

    # Try generic code block
    pattern = r'```\s*(.*?)\s*```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        logger.debug("Extracted generic code block")
        return match.group(1).strip()

    # No code block found, return as-is
    logger.debug("No code block found, returning raw text")
    return text.strip()


def extract_json_from_markdown(text: str) -> str:
    """
    Extract JSON from markdown code blocks

    Args:
        text: Text potentially containing markdown JSON blocks

    Returns:
        Extracted JSON string or original text
    """
    if not text:
        return ""

    # Try json-specific code block
    pattern = r'```json\s*(.*?)\s*```'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try generic code block
    pattern = r'```\s*(.*?)\s*```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find raw JSON (starts with { or [)
    json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
    if json_match:
        return json_match.group(1).strip()

    return text.strip()


def extract_method_from_code(code: str, method_name: str) -> Optional[str]:
    """
    Extract a specific method definition from Python code

    Args:
        code: Full Python code
        method_name: Name of method to extract (e.g., "_fill_dropdown")

    Returns:
        Method code or None if not found
    """
    if not code or not method_name:
        return None

    # Pattern to match async def or def methods
    pattern = rf'((?:async\s+)?def {re.escape(method_name)}\([^)]*\):.*?)(?=\n    (?:async\s+)?def |\n    class |\nclass |\Z)'
    match = re.search(pattern, code, re.DOTALL)

    if match:
        return match.group(1).strip()

    return None


def extract_class_from_code(code: str, class_name: Optional[str] = None) -> Optional[str]:
    """
    Extract a class definition from Python code

    Args:
        code: Full Python code
        class_name: Optional specific class name. If None, extracts first class.

    Returns:
        Class code or None if not found
    """
    if not code:
        return None

    if class_name:
        pattern = rf'(class {re.escape(class_name)}.*?)(?=\nclass |\Z)'
    else:
        pattern = r'(class \w+.*?)(?=\nclass |\Z)'

    match = re.search(pattern, code, re.DOTALL)

    if match:
        return match.group(1).strip()

    return None


def extract_class_name(code: str) -> Optional[str]:
    """
    Extract the class name from Python code

    Args:
        code: Python code containing a class definition

    Returns:
        Class name or None
    """
    if not code:
        return None

    match = re.search(r'class\s+(\w+)', code)
    if match:
        return match.group(1)

    return None
