"""
Field Query Utility - Maps natural language to dropdown values
"""
import json
import re
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from difflib import SequenceMatcher


class FieldQueryEngine:
    """Query dropdown values using natural language"""

    def __init__(self, knowledge_dir: Path = Path("knowledge")):
        self.knowledge_dir = Path(knowledge_dir)
        self.mappings: Dict[str, Dict] = {}
        self._load_mappings()

    def _load_mappings(self):
        """Load all field mapping files"""
        if not self.knowledge_dir.exists():
            return

        for mapping_file in self.knowledge_dir.glob("*_field_mappings.json"):
            with open(mapping_file) as f:
                data = json.load(f)
                municipality = data['municipality']
                self.mappings[municipality] = data

    def find_value(
        self,
        municipality: str,
        field_name: str,
        query: str,
        threshold: int = 50
    ) -> Optional[str]:
        """
        Find dropdown value matching natural language query

        Args:
            municipality: Municipality name (e.g., 'ranchi_smart')
            field_name: Field name (e.g., 'problem_type', 'area')
            query: Natural language query (e.g., 'air pollution')
            threshold: Minimum fuzzy match score (0-100), default 50

        Returns:
            Dropdown value or None if not found
        """
        if municipality not in self.mappings:
            return None

        field_data = self.mappings[municipality]['field_mappings'].get(field_name)
        if not field_data:
            return None

        searchable = field_data['searchable_values']
        query_normalized = query.lower().strip()

        # Try exact match first
        if query_normalized in searchable:
            return searchable[query_normalized]

        # Try substring match (query contains label or vice versa)
        for label, value in searchable.items():
            if query_normalized in label or label in query_normalized:
                return value

        # Try fuzzy matching using difflib
        best_match = None
        best_score = threshold / 100.0  # Convert to 0-1 range

        for label, value in searchable.items():
            # Use SequenceMatcher for similarity
            score = SequenceMatcher(None, query_normalized, label).ratio()
            if score > best_score:
                best_score = score
                best_match = value

            # Also check if all query words are in label (keyword matching)
            query_words = set(query_normalized.split())
            label_words = set(label.split())
            word_overlap = len(query_words & label_words) / len(query_words) if query_words else 0
            if word_overlap >= 0.6 and word_overlap > best_score:
                best_score = word_overlap
                best_match = value

        return best_match

    def parse_grievance_prompt(
        self,
        municipality: str,
        prompt: str
    ) -> Dict[str, str]:
        """
        Parse natural language prompt into field values

        Example:
            Input: "report air pollution in anand vihar colony"
            Output: {
                'problem_type': '499',
                'area': '158'
            }

        Args:
            municipality: Municipality name
            prompt: Natural language prompt

        Returns:
            Dictionary mapping field names to values
        """
        if municipality not in self.mappings:
            return {}

        prompt_lower = prompt.lower()
        result = {}

        # Try to identify problem type and area from prompt
        # This uses a simple heuristic - can be improved with NLP

        # Common patterns for problem identification
        problem_patterns = [
            r'report\s+(.+?)\s+(?:in|near|at)\s+',  # "report X in/near/at Y"
            r'complaint\s+about\s+(.+?)\s+(?:in|near|at)\s+',  # "complaint about X in/near/at Y"
            r'issue\s+with\s+(.+?)\s+(?:in|near|at)\s+',  # "issue with X in/near/at Y"
            r'problem\s+of\s+(.+?)\s+(?:in|near|at)\s+',  # "problem of X in/near/at Y"
        ]

        # Try to extract problem type
        for pattern in problem_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                problem_query = match.group(1).strip()
                value = self.find_value(municipality, 'problem', problem_query)
                if value:
                    result['problem_type'] = value  # Use problem_type for scraper compatibility
                break

        # Try to extract area (usually after "in", "near", or "at" keywords)
        area_match = re.search(r'\s+(?:in|near|at)\s+(.+?)$', prompt_lower)
        if area_match:
            area_query = area_match.group(1).strip()
            value = self.find_value(municipality, 'wardforarea', area_query)
            if value:
                result['area'] = value  # Use area for scraper compatibility

        return result

    def get_field_label(
        self,
        municipality: str,
        field_name: str,
        value: str
    ) -> Optional[str]:
        """Get human-readable label for a field value"""
        if municipality not in self.mappings:
            return None

        field_data = self.mappings[municipality]['field_mappings'].get(field_name)
        if not field_data:
            return None

        searchable = field_data['searchable_values']
        for label, val in searchable.items():
            if val == value:
                return label

        return None

    def search_values(
        self,
        municipality: str,
        field_name: str,
        query: str,
        limit: int = 5
    ) -> List[Tuple[str, str, int]]:
        """
        Search for multiple matching values (useful for suggestions)

        Returns:
            List of (label, value, score) tuples sorted by score
        """
        if municipality not in self.mappings:
            return []

        field_data = self.mappings[municipality]['field_mappings'].get(field_name)
        if not field_data:
            return []

        searchable = field_data['searchable_values']
        query_normalized = query.lower().strip()

        matches = []
        for label, value in searchable.items():
            # Use SequenceMatcher for similarity (returns 0-1)
            score = int(SequenceMatcher(None, query_normalized, label).ratio() * 100)
            if score > 50:  # Minimum threshold (50%)
                matches.append((label, value, score))

        # Sort by score descending
        matches.sort(key=lambda x: x[2], reverse=True)
        return matches[:limit]


# Example usage
if __name__ == "__main__":
    engine = FieldQueryEngine()

    # Example 1: Parse full prompt
    print("Example 1: Full prompt parsing")
    print("-" * 50)
    prompt = "report air pollution in anand vihar colony"
    result = engine.parse_grievance_prompt('ranchi_smart', prompt)
    print(f"Prompt: {prompt}")
    print(f"Parsed: {result}")
    print()

    # Get human-readable labels
    if 'problem_type' in result:
        label = engine.get_field_label('ranchi_smart', 'problem', result['problem_type'])
        print(f"Problem Type: {label} (value: {result['problem_type']})")

    if 'area' in result:
        label = engine.get_field_label('ranchi_smart', 'wardforarea', result['area'])
        print(f"Area: {label} (value: {result['area']})")
    print()

    # Example 2: Direct value lookup
    print("Example 2: Direct value lookup")
    print("-" * 50)
    problem_value = engine.find_value('ranchi_smart', 'problem', 'garbage on road')
    print(f"Query: 'garbage on road'")
    print(f"Value: {problem_value}")
    print()

    # Example 3: Fuzzy search suggestions
    print("Example 3: Fuzzy search (top 5 matches)")
    print("-" * 50)
    query = "dirty water"
    matches = engine.search_values('ranchi_smart', 'problem', query, limit=5)
    print(f"Query: '{query}'")
    for label, value, score in matches:
        print(f"  - {label} (value: {value}, score: {score})")
