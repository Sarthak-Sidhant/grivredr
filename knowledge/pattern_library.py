"""
Pattern Library - Learns from successful scrapers to improve future generations
"""
import json
import sqlite3
import hashlib
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ScraperPattern:
    """Represents a successful scraper pattern"""
    id: Optional[int]
    municipality_name: str
    form_url: str
    form_signature: str  # Hash of field types/names
    field_types: List[str]
    dom_structure_hash: str
    js_complexity: str  # "none", "simple", "complex"
    code_snippets: Dict[str, str]
    success_rate: float
    confidence_score: float
    validation_attempts: int
    created_at: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PatternLibrary:
    """
    Stores and retrieves successful scraper patterns
    """

    def __init__(self, db_path: str = "knowledge/patterns.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database with schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                municipality_name TEXT NOT NULL,
                form_url TEXT NOT NULL,
                form_signature TEXT NOT NULL,
                field_types TEXT NOT NULL,  -- JSON array
                dom_structure_hash TEXT,
                js_complexity TEXT DEFAULT 'none',
                code_snippets TEXT,  -- JSON object
                success_rate REAL DEFAULT 1.0,
                confidence_score REAL,
                validation_attempts INTEGER,
                created_at TEXT NOT NULL,
                metadata TEXT,  -- JSON object
                UNIQUE(form_signature)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_form_signature
            ON patterns(form_signature)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_success_rate
            ON patterns(success_rate DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_municipality
            ON patterns(municipality_name)
        """)

        conn.commit()
        conn.close()

        logger.info(f"✓ Pattern library initialized at {self.db_path}")

    def store_pattern(
        self,
        municipality_name: str,
        form_url: str,
        form_schema: Dict[str, Any],
        generated_code: str,
        confidence_score: float,
        validation_attempts: int,
        js_analysis: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store a successful scraper pattern

        Args:
            municipality_name: Municipality name
            form_url: Form URL
            form_schema: Form schema with fields
            generated_code: Generated scraper code
            confidence_score: Validation confidence score
            validation_attempts: Number of validation attempts needed
            js_analysis: Optional JS analysis results

        Returns:
            True if stored successfully
        """
        try:
            # Calculate form signature
            fields = form_schema.get("fields", [])
            field_types = [f['type'] for f in fields]
            form_signature = self._calculate_form_signature(field_types)

            # Extract code snippets
            code_snippets = self._extract_code_snippets(generated_code)

            # Determine JS complexity
            js_complexity = "none"
            if js_analysis:
                if js_analysis.get("has_ajax") or js_analysis.get("cascading_dropdowns"):
                    js_complexity = "complex"
                elif js_analysis.get("has_dynamic_content"):
                    js_complexity = "simple"

            # Create pattern
            pattern = ScraperPattern(
                id=None,
                municipality_name=municipality_name,
                form_url=form_url,
                form_signature=form_signature,
                field_types=field_types,
                dom_structure_hash=self._calculate_dom_hash(form_schema),
                js_complexity=js_complexity,
                code_snippets=code_snippets,
                success_rate=1.0,  # Initial success rate
                confidence_score=confidence_score,
                validation_attempts=validation_attempts,
                created_at=datetime.now().isoformat(),
                metadata={
                    "field_count": len(fields),
                    "has_file_upload": any(f['type'] == 'file' for f in fields),
                    "has_cascading": bool(js_analysis and js_analysis.get("cascading_dropdowns"))
                }
            )

            # Store in database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO patterns (
                    municipality_name, form_url, form_signature, field_types,
                    dom_structure_hash, js_complexity, code_snippets,
                    success_rate, confidence_score, validation_attempts,
                    created_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern.municipality_name,
                pattern.form_url,
                pattern.form_signature,
                json.dumps(pattern.field_types),
                pattern.dom_structure_hash,
                pattern.js_complexity,
                json.dumps(pattern.code_snippets),
                pattern.success_rate,
                pattern.confidence_score,
                pattern.validation_attempts,
                pattern.created_at,
                json.dumps(pattern.metadata)
            ))

            conn.commit()
            conn.close()

            logger.info(f"✓ Stored pattern: {municipality_name} (signature: {form_signature[:8]}...)")
            return True

        except Exception as e:
            logger.error(f"Failed to store pattern: {e}")
            return False

    def find_similar_patterns(
        self,
        form_schema: Dict[str, Any],
        top_k: int = 3
    ) -> List[ScraperPattern]:
        """
        Find similar patterns based on form characteristics

        Args:
            form_schema: Form schema to match
            top_k: Number of similar patterns to return

        Returns:
            List of similar patterns, sorted by similarity
        """
        fields = form_schema.get("fields", [])
        field_types = [f['type'] for f in fields]
        query_signature = self._calculate_form_signature(field_types)

        # Check if query form has Select2
        has_select2 = any(
            'select2' in f.get('class', '').lower() or f.get('select2', False)
            for f in fields
        )

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Prioritize patterns with Select2 if query has Select2
        if has_select2:
            logger.info("🔍 Query has Select2, prioritizing Select2 patterns")
            cursor.execute("""
                SELECT * FROM patterns
                WHERE success_rate > 0.7
                  AND (metadata LIKE '%select2%' OR metadata LIKE '%jquery%')
                ORDER BY confidence_score DESC, success_rate DESC
                LIMIT 20
            """)
        else:
            # Get all patterns
            cursor.execute("""
                SELECT * FROM patterns
                WHERE success_rate > 0.7
                ORDER BY confidence_score DESC, success_rate DESC
                LIMIT 20
            """)

        rows = cursor.fetchall()
        conn.close()

        # Calculate similarity scores
        similar_patterns = []

        for row in rows:
            pattern = self._row_to_pattern(row)

            # Calculate Jaccard similarity
            similarity = self._calculate_similarity(field_types, pattern.field_types)

            if similarity > 0.3:  # Minimum threshold
                similar_patterns.append((similarity, pattern))

        # Sort by similarity and return top_k
        similar_patterns.sort(key=lambda x: x[0], reverse=True)
        results = [pattern for _, pattern in similar_patterns[:top_k]]

        if results:
            logger.info(f"✓ Found {len(results)} similar patterns (best: {similar_patterns[0][0]:.2%})")
        else:
            logger.info("No similar patterns found")

        return results

    def get_recommended_code_snippets(
        self,
        form_schema: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Get code snippets from similar successful scrapers

        Args:
            form_schema: Form schema

        Returns:
            Dictionary of code snippets
        """
        similar_patterns = self.find_similar_patterns(form_schema, top_k=3)

        if not similar_patterns:
            return {}

        # Aggregate snippets from top patterns
        all_snippets = {}

        for pattern in similar_patterns:
            for snippet_type, code in pattern.code_snippets.items():
                if snippet_type not in all_snippets:
                    all_snippets[snippet_type] = code

        logger.info(f"✓ Retrieved {len(all_snippets)} code snippet types")
        return all_snippets

    def _calculate_form_signature(self, field_types: List[str]) -> str:
        """Calculate unique signature for field type combination"""
        # Sort field types for consistency
        sorted_types = sorted(field_types)
        signature_string = ",".join(sorted_types)
        return hashlib.md5(signature_string.encode()).hexdigest()

    def _calculate_dom_hash(self, form_schema: Dict[str, Any]) -> str:
        """Calculate hash of DOM structure"""
        # Simple structure representation
        fields = form_schema.get("fields", [])
        structure = [f"{f['type']}:{f.get('name', 'unnamed')}" for f in fields]
        structure_string = "|".join(structure)
        return hashlib.md5(structure_string.encode()).hexdigest()

    def _calculate_similarity(self, types1: List[str], types2: List[str]) -> float:
        """Calculate Jaccard similarity between field type lists"""
        set1 = set(types1)
        set2 = set(types2)

        if not set1 and not set2:
            return 1.0

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def _extract_code_snippets(self, generated_code: str) -> Dict[str, str]:
        """Extract reusable code snippets from generated scraper"""
        snippets = {}

        # Extract field filling pattern
        if "await page.fill(" in generated_code or "await page.type(" in generated_code:
            snippets["field_filling"] = "await page.fill(selector, value)"

        # Extract dropdown handling
        if "await page.select_option(" in generated_code:
            snippets["dropdown_handling"] = "await page.select_option(selector, value)"

        # Extract wait patterns
        if "await page.wait_for_selector(" in generated_code:
            snippets["explicit_wait"] = "await page.wait_for_selector(selector, timeout=5000)"

        # Extract error handling pattern
        if "try:" in generated_code and "except" in generated_code:
            snippets["error_handling"] = "try-except with logging"

        return snippets

    def _row_to_pattern(self, row: tuple) -> ScraperPattern:
        """Convert database row to ScraperPattern object"""
        return ScraperPattern(
            id=row[0],
            municipality_name=row[1],
            form_url=row[2],
            form_signature=row[3],
            field_types=json.loads(row[4]),
            dom_structure_hash=row[5],
            js_complexity=row[6],
            code_snippets=json.loads(row[7]),
            success_rate=row[8],
            confidence_score=row[9],
            validation_attempts=row[10],
            created_at=row[11],
            metadata=json.loads(row[12]) if row[12] else {}
        )

    def get_statistics(self) -> Dict[str, Any]:
        """Get library statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM patterns")
        total_patterns = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(confidence_score) FROM patterns")
        avg_confidence = cursor.fetchone()[0] or 0.0

        cursor.execute("SELECT AVG(success_rate) FROM patterns")
        avg_success = cursor.fetchone()[0] or 0.0

        conn.close()

        return {
            "total_patterns": total_patterns,
            "avg_confidence": round(avg_confidence, 2),
            "avg_success_rate": round(avg_success, 2)
        }
