"""
Framework Detector - Identifies UI frameworks used in web forms

Detects common UI frameworks to select appropriate code templates:
- Ant Design (React-based, common in modern Chinese/Asian govt portals)
- Select2 (jQuery plugin, very common in older portals)
- Bootstrap (generic, widely used)
- ASP.NET WebForms (older Microsoft stack, __VIEWSTATE, __doPostBack)
- Material UI (Google-style, modern)
- Plain HTML (no framework detected)
"""
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class UIFramework(Enum):
    """Detected UI frameworks"""
    ANT_DESIGN = "ant_design"
    SELECT2 = "select2"
    BOOTSTRAP = "bootstrap"
    ASP_NET_WEBFORMS = "asp_net_webforms"
    MATERIAL_UI = "material_ui"
    PLAIN_HTML = "plain_html"
    UNKNOWN = "unknown"


@dataclass
class FrameworkDetectionResult:
    """Result of framework detection"""
    primary_framework: UIFramework
    confidence: float  # 0.0 to 1.0
    detected_frameworks: List[UIFramework]  # All detected (may be multiple)
    evidence: Dict[str, List[str]]  # Evidence found for each framework
    recommendations: List[str]  # Recommendations for scraper generation


# Detection patterns for each framework
FRAMEWORK_PATTERNS = {
    UIFramework.ANT_DESIGN: {
        "css_classes": [
            r"ant-\w+",  # ant-form, ant-input, ant-select, etc.
            r"antd-\w+",
        ],
        "html_attributes": [
            r"data-ant-\w+",
        ],
        "dom_structure": [
            r'class="ant-select-selector"',
            r'class="ant-form-item"',
            r'class="ant-input"',
            r'class="ant-btn"',
        ],
        "js_globals": [
            "antd",
            "ant-design",
        ],
        "dropdown_indicators": [
            r"ant-select-dropdown",
            r"ant-select-item-option",
        ],
    },

    UIFramework.SELECT2: {
        "css_classes": [
            r"select2-\w+",
            r"select2-container",
            r"select2-hidden-accessible",
        ],
        "html_attributes": [
            r"data-select2-id",
        ],
        "dom_structure": [
            r'class="select2-selection"',
            r'class="select2-results"',
        ],
        "js_globals": [
            "$.fn.select2",
            "Select2",
        ],
        "dropdown_indicators": [
            r"select2-dropdown",
            r"select2-results__option",
        ],
    },

    UIFramework.BOOTSTRAP: {
        "css_classes": [
            r"form-control",
            r"form-group",
            r"btn-primary",
            r"btn-secondary",
            r"form-select",
            r"input-group",
        ],
        "html_attributes": [
            r"data-bs-\w+",
            r"data-toggle",
        ],
        "dom_structure": [
            r'class="container"',
            r'class="row"',
            r'class="col-\w+"',
        ],
        "js_globals": [
            "bootstrap",
            "$.fn.modal",
        ],
        "dropdown_indicators": [
            r"dropdown-menu",
            r"dropdown-item",
        ],
    },

    UIFramework.ASP_NET_WEBFORMS: {
        "css_classes": [],  # ASP.NET doesn't have specific classes
        "html_attributes": [
            r'id="ctl\d+_',  # ctl00_ContentPlaceHolder1_...
            r'name="ctl\d+\$',
        ],
        "dom_structure": [
            r'name="__VIEWSTATE"',
            r'name="__EVENTVALIDATION"',
            r'name="__VIEWSTATEGENERATOR"',
            r'__doPostBack',
        ],
        "js_globals": [
            "__doPostBack",
            "WebForm_DoPostBackWithOptions",
        ],
        "dropdown_indicators": [],
    },

    UIFramework.MATERIAL_UI: {
        "css_classes": [
            r"MuiFormControl-\w+",
            r"MuiInputBase-\w+",
            r"MuiSelect-\w+",
            r"MuiButton-\w+",
        ],
        "html_attributes": [
            r"data-mui-\w+",
        ],
        "dom_structure": [
            r'class="MuiPaper-root"',
            r'class="MuiFormLabel-root"',
        ],
        "js_globals": [
            "MaterialUI",
        ],
        "dropdown_indicators": [
            r"MuiMenu-paper",
            r"MuiMenuItem-root",
        ],
    },
}


class FrameworkDetector:
    """
    Detects UI frameworks from HTML content and form structure

    Usage:
        detector = FrameworkDetector()
        result = detector.detect_from_html(html_content)
        result = detector.detect_from_schema(form_schema)
    """

    def detect_from_html(self, html_content: str) -> FrameworkDetectionResult:
        """
        Detect UI framework from raw HTML content

        Args:
            html_content: Full HTML of the page

        Returns:
            FrameworkDetectionResult with detected framework(s)
        """
        evidence: Dict[str, List[str]] = {}
        scores: Dict[UIFramework, float] = {}

        for framework, patterns in FRAMEWORK_PATTERNS.items():
            framework_evidence = []
            score = 0.0

            # Check CSS classes
            for pattern in patterns.get("css_classes", []):
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    framework_evidence.extend(matches[:5])  # Limit to 5 examples
                    score += len(matches) * 0.1

            # Check HTML attributes
            for pattern in patterns.get("html_attributes", []):
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    framework_evidence.extend(matches[:3])
                    score += len(matches) * 0.15

            # Check DOM structure (more specific = higher weight)
            for pattern in patterns.get("dom_structure", []):
                if re.search(pattern, html_content, re.IGNORECASE):
                    framework_evidence.append(pattern)
                    score += 0.25

            # Check dropdown indicators (important for scraper generation)
            for pattern in patterns.get("dropdown_indicators", []):
                if re.search(pattern, html_content, re.IGNORECASE):
                    framework_evidence.append(f"dropdown: {pattern}")
                    score += 0.2

            if framework_evidence:
                evidence[framework.value] = list(set(framework_evidence))[:10]
                scores[framework] = min(score, 1.0)  # Cap at 1.0

        return self._build_result(scores, evidence)

    def detect_from_schema(self, form_schema: Dict[str, Any]) -> FrameworkDetectionResult:
        """
        Detect UI framework from form schema

        Uses field classes, selectors, and structure to identify framework.

        Args:
            form_schema: Form schema with fields

        Returns:
            FrameworkDetectionResult
        """
        evidence: Dict[str, List[str]] = {}
        scores: Dict[UIFramework, float] = {}

        fields = form_schema.get("fields", [])

        for field in fields:
            field_class = field.get("class", "")
            selector = field.get("selector", "")
            field_type = field.get("type", "")

            # Check for Ant Design
            if "ant-" in field_class.lower() or "antd" in field_class.lower():
                evidence.setdefault("ant_design", []).append(f"class: {field_class}")
                scores[UIFramework.ANT_DESIGN] = scores.get(UIFramework.ANT_DESIGN, 0) + 0.3

            # Check for Select2
            if "select2" in field_class.lower():
                evidence.setdefault("select2", []).append(f"class: {field_class}")
                scores[UIFramework.SELECT2] = scores.get(UIFramework.SELECT2, 0) + 0.3

            if field.get("select2", False):
                evidence.setdefault("select2", []).append("select2: true in schema")
                scores[UIFramework.SELECT2] = scores.get(UIFramework.SELECT2, 0) + 0.4

            # Check for ASP.NET
            if "ctl00" in selector or "ContentPlaceHolder" in selector:
                evidence.setdefault("asp_net_webforms", []).append(f"selector: {selector}")
                scores[UIFramework.ASP_NET_WEBFORMS] = scores.get(UIFramework.ASP_NET_WEBFORMS, 0) + 0.25

            # Check for Bootstrap
            if "form-control" in field_class or "form-select" in field_class:
                evidence.setdefault("bootstrap", []).append(f"class: {field_class}")
                scores[UIFramework.BOOTSTRAP] = scores.get(UIFramework.BOOTSTRAP, 0) + 0.15

            # Check for Material UI
            if "Mui" in field_class:
                evidence.setdefault("material_ui", []).append(f"class: {field_class}")
                scores[UIFramework.MATERIAL_UI] = scores.get(UIFramework.MATERIAL_UI, 0) + 0.3

        # Check form URL for hints
        form_url = form_schema.get("url", "")
        if ".aspx" in form_url.lower():
            evidence.setdefault("asp_net_webforms", []).append("URL ends with .aspx")
            scores[UIFramework.ASP_NET_WEBFORMS] = scores.get(UIFramework.ASP_NET_WEBFORMS, 0) + 0.2

        # Normalize scores
        for framework in scores:
            scores[framework] = min(scores[framework], 1.0)

        return self._build_result(scores, evidence)

    def detect_from_page_content(
        self,
        html_content: str,
        form_schema: Optional[Dict[str, Any]] = None
    ) -> FrameworkDetectionResult:
        """
        Combined detection from both HTML and schema

        Args:
            html_content: HTML content
            form_schema: Optional form schema

        Returns:
            Combined FrameworkDetectionResult
        """
        html_result = self.detect_from_html(html_content)

        if form_schema:
            schema_result = self.detect_from_schema(form_schema)

            # Merge evidence
            combined_evidence = dict(html_result.evidence)
            for key, values in schema_result.evidence.items():
                if key in combined_evidence:
                    combined_evidence[key].extend(values)
                else:
                    combined_evidence[key] = values

            # Use schema result primary if more confident
            if schema_result.confidence > html_result.confidence:
                return FrameworkDetectionResult(
                    primary_framework=schema_result.primary_framework,
                    confidence=max(html_result.confidence, schema_result.confidence),
                    detected_frameworks=list(set(html_result.detected_frameworks + schema_result.detected_frameworks)),
                    evidence=combined_evidence,
                    recommendations=self._get_recommendations(schema_result.primary_framework)
                )

        return html_result

    def _build_result(
        self,
        scores: Dict[UIFramework, float],
        evidence: Dict[str, List[str]]
    ) -> FrameworkDetectionResult:
        """Build detection result from scores and evidence"""

        if not scores:
            return FrameworkDetectionResult(
                primary_framework=UIFramework.PLAIN_HTML,
                confidence=0.5,
                detected_frameworks=[UIFramework.PLAIN_HTML],
                evidence={},
                recommendations=self._get_recommendations(UIFramework.PLAIN_HTML)
            )

        # Sort by score
        sorted_frameworks = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        primary = sorted_frameworks[0][0]
        primary_confidence = sorted_frameworks[0][1]

        # Get all detected (above threshold)
        detected = [fw for fw, score in sorted_frameworks if score > 0.1]

        return FrameworkDetectionResult(
            primary_framework=primary,
            confidence=primary_confidence,
            detected_frameworks=detected,
            evidence=evidence,
            recommendations=self._get_recommendations(primary)
        )

    def _get_recommendations(self, framework: UIFramework) -> List[str]:
        """Get scraper generation recommendations for a framework"""

        recommendations = {
            UIFramework.ANT_DESIGN: [
                "Use _fill_searchable_select() for ant-select dropdowns",
                "Find visible dropdown with .ant-select-dropdown and is_visible() check",
                "Click wrapper element (ancestor div with ant-select class) to open dropdown",
                "Options are in .ant-select-item-option elements",
                "Wait 0.8s after click for dropdown animation",
                "For cascading: wait 1.5s after parent selection for child to load",
            ],
            UIFramework.SELECT2: [
                "DO NOT use page.select_option() - it will timeout",
                "Use jQuery: $(selector).val(value).trigger('change')",
                "For searchable: click container, type in .select2-search__field",
                "Options appear in .select2-results__option",
                "Wait 1-2s after selection for cascading dropdowns",
            ],
            UIFramework.ASP_NET_WEBFORMS: [
                "Extract __VIEWSTATE and __EVENTVALIDATION before submission",
                "Selectors use ctl00_ContentPlaceHolder1_ prefix",
                "Cascading may use __doPostBack - monitor network tab",
                "Standard page.select_option() usually works for dropdowns",
            ],
            UIFramework.BOOTSTRAP: [
                "Standard HTML select handling usually works",
                "For custom dropdowns, check for dropdown-menu/dropdown-item classes",
                "May need to click button to open dropdown first",
            ],
            UIFramework.MATERIAL_UI: [
                "Click MuiSelect to open menu",
                "Options in MuiMenu-paper with MuiMenuItem-root",
                "May need keyboard navigation (ArrowDown, Enter)",
            ],
            UIFramework.PLAIN_HTML: [
                "Use standard page.select_option() for dropdowns",
                "Use page.fill() for text inputs",
                "Check for any custom JavaScript handlers",
            ],
        }

        return recommendations.get(framework, ["No specific recommendations"])


def detect_framework(
    html_content: Optional[str] = None,
    form_schema: Optional[Dict[str, Any]] = None
) -> FrameworkDetectionResult:
    """
    Convenience function to detect framework

    Args:
        html_content: Optional HTML content
        form_schema: Optional form schema

    Returns:
        FrameworkDetectionResult
    """
    detector = FrameworkDetector()

    if html_content and form_schema:
        return detector.detect_from_page_content(html_content, form_schema)
    elif html_content:
        return detector.detect_from_html(html_content)
    elif form_schema:
        return detector.detect_from_schema(form_schema)
    else:
        return FrameworkDetectionResult(
            primary_framework=UIFramework.UNKNOWN,
            confidence=0.0,
            detected_frameworks=[],
            evidence={},
            recommendations=[]
        )


def get_template_code_for_schema(form_schema: Dict[str, Any]) -> str:
    """
    Get appropriate template code based on detected framework

    Args:
        form_schema: Form schema

    Returns:
        Formatted template code for AI prompt injection
    """
    from knowledge.code_templates import get_template_code_for_prompt, UIFramework as TemplateFramework

    detector = FrameworkDetector()
    result = detector.detect_from_schema(form_schema)

    # Map detector framework to template framework
    framework_map = {
        UIFramework.ANT_DESIGN: TemplateFramework.ANT_DESIGN,
        UIFramework.SELECT2: TemplateFramework.SELECT2,
        UIFramework.ASP_NET_WEBFORMS: TemplateFramework.ASP_NET_WEBFORMS,
        UIFramework.BOOTSTRAP: TemplateFramework.PLAIN_HTML,
        UIFramework.MATERIAL_UI: TemplateFramework.MATERIAL_UI,
        UIFramework.PLAIN_HTML: TemplateFramework.PLAIN_HTML,
    }

    template_framework = framework_map.get(result.primary_framework, TemplateFramework.PLAIN_HTML)

    return get_template_code_for_prompt(template_framework)
