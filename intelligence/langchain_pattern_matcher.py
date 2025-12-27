"""
LangChain Pattern Matcher - Semantic pattern matching for forms
Uses LangChain + Claude to find similar form patterns intelligently
"""
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Optional LangChain imports (graceful degradation)
try:
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain not available. Install with: pip install langchain langchain-anthropic")


@dataclass
class PatternMatch:
    """Represents a pattern match result"""
    municipality: str
    similarity_score: float
    reasoning: str
    field_overlap: float
    structure_similarity: float
    recommendations: List[str]


class LangChainPatternMatcher:
    """
    Use LangChain + Claude for intelligent pattern matching

    Features:
    - Semantic similarity (not just structural)
    - Understands field purpose (e.g., "mobile" vs "phone" vs "contact_number")
    - Considers validation patterns, cascading logic
    - Provides reasoning for matches
    """

    def __init__(self):
        """Initialize with LangChain if available"""
        self.available = LANGCHAIN_AVAILABLE

        if not self.available:
            logger.warning("⚠️  LangChain not available, pattern matcher disabled")
            return

        # Get LangChain-compatible Claude model
        from config.ai_client import ai_client

        self.llm = ai_client.get_langchain_chat_model("fast")  # Haiku for speed

        if not self.llm:
            logger.warning("⚠️  LangChain model not available")
            self.available = False
            return

        logger.info("✓ LangChain pattern matcher initialized")

    def find_similar_patterns(
        self,
        target_schema: Dict[str, Any],
        known_patterns: List[Dict[str, Any]],
        top_k: int = 3
    ) -> List[PatternMatch]:
        """
        Find similar form patterns using semantic understanding

        Args:
            target_schema: The form schema to match against
            known_patterns: List of known form schemas with metadata
            top_k: Number of top matches to return

        Returns:
            List of PatternMatch objects sorted by similarity
        """
        if not self.available:
            logger.warning("LangChain not available, returning empty matches")
            return []

        if not known_patterns:
            logger.info("No known patterns to match against")
            return []

        # Build prompt
        prompt_template = PromptTemplate(
            input_variables=["target_schema", "known_patterns", "top_k"],
            template="""You are an expert at analyzing government form structures.

**TARGET FORM:**
{target_schema}

**KNOWN PATTERNS:**
{known_patterns}

**TASK:**
Find the {top_k} most similar forms to the target. Consider:
1. Field types and purposes (semantic understanding)
2. Form structure and complexity
3. Validation patterns
4. Cascading relationships
5. Overall workflow similarity

For each match, provide:
- Municipality name
- Similarity score (0.0-1.0)
- Reasoning (why similar)
- Field overlap score
- Structure similarity score
- Recommendations (what can be reused)

Return JSON array of matches sorted by similarity (highest first):
[
  {{
    "municipality": "...",
    "similarity_score": 0.95,
    "reasoning": "...",
    "field_overlap": 0.90,
    "structure_similarity": 0.92,
    "recommendations": ["...", "..."]
  }}
]

Be strict: only return scores > 0.6. Return empty array if no good matches."""
        )

        # Create chain
        chain = LLMChain(llm=self.llm, prompt=prompt_template)

        # Execute
        try:
            response = chain.run(
                target_schema=self._schema_to_text(target_schema),
                known_patterns=self._patterns_to_text(known_patterns),
                top_k=top_k
            )

            # Parse JSON response
            matches_data = json.loads(response)

            # Convert to PatternMatch objects
            matches = [
                PatternMatch(
                    municipality=m["municipality"],
                    similarity_score=m["similarity_score"],
                    reasoning=m["reasoning"],
                    field_overlap=m["field_overlap"],
                    structure_similarity=m["structure_similarity"],
                    recommendations=m["recommendations"]
                )
                for m in matches_data[:top_k]
            ]

            logger.info(f"✅ Found {len(matches)} similar patterns")
            return matches

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Pattern matching failed: {e}")
            return []

    def explain_similarity(
        self,
        form1: Dict[str, Any],
        form2: Dict[str, Any]
    ) -> str:
        """
        Explain why two forms are similar or different

        Returns:
            Human-readable explanation
        """
        if not self.available:
            return "LangChain not available"

        prompt_template = PromptTemplate(
            input_variables=["form1", "form2"],
            template="""Compare these two government forms and explain their similarities/differences:

**FORM 1:**
{form1}

**FORM 2:**
{form2}

Provide a clear, concise explanation covering:
1. What's similar (field types, structure, workflow)
2. What's different (complexity, validation, features)
3. Reusability score (0-100%)
4. Specific recommendations for code reuse

Format as a short paragraph (3-4 sentences)."""
        )

        chain = LLMChain(llm=self.llm, prompt=prompt_template)

        try:
            explanation = chain.run(
                form1=self._schema_to_text(form1),
                form2=self._schema_to_text(form2)
            )
            return explanation.strip()
        except Exception as e:
            logger.error(f"Explanation failed: {e}")
            return f"Error: {str(e)}"

    def suggest_code_reuse(
        self,
        target_schema: Dict[str, Any],
        similar_pattern: Dict[str, Any],
        existing_code: str
    ) -> Dict[str, Any]:
        """
        Suggest which parts of existing code can be reused

        Returns:
            Dict with reusable sections and required modifications
        """
        if not self.available:
            return {"error": "LangChain not available"}

        prompt_template = PromptTemplate(
            input_variables=["target_schema", "similar_pattern", "existing_code"],
            template="""You have a new form to scrape and similar existing code.

**NEW FORM:**
{target_schema}

**SIMILAR FORM:**
{similar_pattern}

**EXISTING CODE:**
```python
{existing_code}
```

**TASK:**
Identify which code sections can be reused vs need modification.

Return JSON:
{{
  "reusability_score": 0.85,
  "reusable_sections": [
    {{"name": "...", "reason": "...", "lines": "50-75"}},
    ...
  ],
  "modifications_needed": [
    {{"section": "...", "change": "...", "reason": "..."}},
    ...
  ],
  "new_code_needed": [
    {{"feature": "...", "reason": "..."}},
    ...
  ]
}}"""
        )

        chain = LLMChain(llm=self.llm, prompt=prompt_template)

        try:
            response = chain.run(
                target_schema=self._schema_to_text(target_schema),
                similar_pattern=self._schema_to_text(similar_pattern),
                existing_code=existing_code[:2000]  # Limit size
            )

            return json.loads(response)
        except Exception as e:
            logger.error(f"Code reuse analysis failed: {e}")
            return {"error": str(e)}

    def _schema_to_text(self, schema: Dict[str, Any]) -> str:
        """Convert schema to human-readable text"""
        fields = schema.get("fields", [])

        text = f"Form with {len(fields)} fields:\\n"

        for i, field in enumerate(fields[:20], 1):  # Limit to 20 fields
            name = field.get("name", "unknown")
            ftype = field.get("type", "unknown")
            required = "required" if field.get("required") else "optional"

            text += f"{i}. {name} ({ftype}, {required})"

            if field.get("options"):
                text += f" - options: {len(field['options'])}"
            if field.get("depends_on"):
                text += f" - depends on {field['depends_on']}"

            text += "\\n"

        if schema.get("captcha_present"):
            text += "\\n- Has CAPTCHA"
        if schema.get("multi_step"):
            text += "\\n- Multi-step form"
        if schema.get("file_upload"):
            text += "\\n- Has file upload"

        return text

    def _patterns_to_text(self, patterns: List[Dict[str, Any]]) -> str:
        """Convert list of patterns to text"""
        text = ""

        for i, pattern in enumerate(patterns, 1):
            municipality = pattern.get("municipality", f"Pattern {i}")
            text += f"\\n{i}. {municipality}:\\n"
            text += self._schema_to_text(pattern.get("schema", {}))
            text += "\\n"

        return text


# Singleton instance
_pattern_matcher = None


def get_pattern_matcher() -> LangChainPatternMatcher:
    """Get singleton pattern matcher instance"""
    global _pattern_matcher

    if _pattern_matcher is None:
        _pattern_matcher = LangChainPatternMatcher()

    return _pattern_matcher


# For testing
if __name__ == "__main__":
    print("\\n" + "="*80)
    print("TESTING LANGCHAIN PATTERN MATCHER")
    print("="*80)

    matcher = get_pattern_matcher()

    if not matcher.available:
        print("\\n❌ LangChain not available, cannot test")
        exit(1)

    # Sample target form
    target = {
        "fields": [
            {"name": "applicant_name", "type": "text", "required": True},
            {"name": "mobile_number", "type": "tel", "required": True},
            {"name": "email", "type": "email", "required": False},
            {"name": "state", "type": "select", "required": True},
            {"name": "district", "type": "select", "required": True, "depends_on": "state"},
            {"name": "complaint_type", "type": "select", "required": True},
            {"name": "description", "type": "textarea", "required": True}
        ],
        "captcha_present": False,
        "multi_step": False
    }

    # Sample known patterns
    known = [
        {
            "municipality": "ranchi_smart",
            "schema": {
                "fields": [
                    {"name": "name", "type": "text", "required": True},
                    {"name": "phone", "type": "tel", "required": True},
                    {"name": "email", "type": "email", "required": True},
                    {"name": "state", "type": "select", "required": True},
                    {"name": "district", "type": "select", "required": True, "depends_on": "state"},
                    {"name": "issue", "type": "textarea", "required": True}
                ]
            }
        },
        {
            "municipality": "mumbai_portal",
            "schema": {
                "fields": [
                    {"name": "citizen_name", "type": "text", "required": True},
                    {"name": "contact", "type": "tel", "required": True},
                    {"name": "ward", "type": "select", "required": True},
                    {"name": "problem", "type": "textarea", "required": True},
                    {"name": "photo", "type": "file", "required": False}
                ],
                "file_upload": True
            }
        }
    ]

    print("\\n🔍 Finding similar patterns...")
    matches = matcher.find_similar_patterns(target, known, top_k=2)

    if matches:
        print(f"\\n✅ Found {len(matches)} matches:\\n")

        for i, match in enumerate(matches, 1):
            print(f"{i}. {match.municipality}")
            print(f"   Similarity: {match.similarity_score*100:.1f}%")
            print(f"   Field Overlap: {match.field_overlap*100:.1f}%")
            print(f"   Structure: {match.structure_similarity*100:.1f}%")
            print(f"   Reasoning: {match.reasoning}")
            print(f"   Recommendations:")
            for rec in match.recommendations:
                print(f"      - {rec}")
            print()
    else:
        print("\\n⚠️  No good matches found")

    print("="*80)
