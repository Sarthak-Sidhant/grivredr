"""
Pattern Library - Learns from successful scrapers to improve future generations

Enhanced with:
- Optional vector embeddings for semantic search
- Actual code snippet storage (not just descriptions)
- UI framework detection integration
- Cascade pattern recognition
"""
import json
import sqlite3
import hashlib
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Optional vector store imports (graceful degradation)
try:
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import HuggingFaceEmbeddings
    VECTOR_STORE_AVAILABLE = True
except ImportError:
    VECTOR_STORE_AVAILABLE = False
    logger.info("Vector store not available. Install with: pip install langchain-community chromadb sentence-transformers")


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

    Features:
    - SQLite for structured data (fast, reliable)
    - Optional Chroma vector store for semantic search
    - Hybrid search: SQL + semantic similarity
    """

    def __init__(
        self,
        db_path: str = "knowledge/patterns.db",
        enable_vector_store: bool = True
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # Initialize vector store (optional)
        self.vector_store = None
        self.embeddings = None
        self.use_vector_search = False

        if enable_vector_store and VECTOR_STORE_AVAILABLE:
            try:
                self._init_vector_store()
                self.use_vector_search = True
                logger.info("✓ Vector store enabled for semantic search")
            except Exception as e:
                logger.warning(f"Vector store init failed: {e}, falling back to SQL-only")
        elif enable_vector_store:
            logger.info("Vector store requested but not available (install langchain-community)")

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

    def _init_vector_store(self):
        """Initialize Chroma vector store for semantic search"""
        vector_dir = self.db_path.parent / "vectors"
        vector_dir.mkdir(exist_ok=True)

        # Use lightweight sentence transformers model
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",  # Fast, 80MB
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        # Initialize Chroma
        self.vector_store = Chroma(
            persist_directory=str(vector_dir),
            embedding_function=self.embeddings,
            collection_name="form_patterns"
        )

        logger.info(f"✓ Vector store initialized at {vector_dir}")

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

            # Detect UI framework
            ui_framework = self._detect_ui_framework(form_schema, generated_code)

            # Check for Select2 specifically
            has_select2 = any(
                'select2' in f.get('class', '').lower() or f.get('select2', False)
                for f in fields
            )

            # Build rich metadata
            metadata = {
                "field_count": len(fields),
                "has_file_upload": any(f['type'] == 'file' for f in fields),
                "has_cascading": bool(js_analysis and js_analysis.get("cascading_dropdowns")),
                "ui_framework": ui_framework,
                "select2_detected": has_select2,
                "jquery_required": has_select2 or 'jQuery' in generated_code or '$.fn' in generated_code,
                "has_ant_design": 'ant-select' in generated_code or 'ant-' in str(form_schema),
            }

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
                metadata=metadata
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

            # Also store in vector store for semantic search
            if self.use_vector_search and self.vector_store:
                try:
                    # Convert schema to searchable text
                    schema_text = self._schema_to_searchable_text(form_schema, municipality_name)

                    # Store with metadata
                    self.vector_store.add_texts(
                        texts=[schema_text],
                        metadatas=[{
                            "municipality": municipality_name,
                            "form_signature": form_signature,
                            "confidence_score": confidence_score,
                            "field_count": len(fields),
                            "js_complexity": js_complexity
                        }],
                        ids=[form_signature]  # Use signature as ID for deduplication
                    )

                    logger.debug(f"  └─ Also stored in vector store")
                except Exception as e:
                    logger.warning(f"Vector store failed (non-critical): {e}")

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

    def _detect_ui_framework(self, form_schema: Dict[str, Any], generated_code: str) -> str:
        """
        Detect UI framework from schema and generated code

        Returns framework identifier string
        """
        fields = form_schema.get("fields", [])
        schema_str = str(form_schema).lower()
        code_lower = generated_code.lower()

        # Check for Ant Design
        if any('ant-' in f.get('class', '').lower() for f in fields):
            return "ant_design"
        if 'ant-select' in schema_str or 'ant-select' in code_lower:
            return "ant_design"
        if '.ant-select-dropdown' in generated_code:
            return "ant_design"

        # Check for Select2
        if any('select2' in f.get('class', '').lower() or f.get('select2', False) for f in fields):
            return "select2"
        if 'select2' in schema_str or '$.fn.select2' in generated_code:
            return "select2"

        # Check for ASP.NET
        form_url = form_schema.get("url", "")
        if ".aspx" in form_url.lower():
            return "asp_net_webforms"
        if any('ctl00' in f.get('selector', '') for f in fields):
            return "asp_net_webforms"
        if '__viewstate' in code_lower or '__dopostback' in code_lower:
            return "asp_net_webforms"

        # Check for Bootstrap
        if any('form-control' in f.get('class', '').lower() for f in fields):
            return "bootstrap"

        # Check for Material UI
        if any('mui' in f.get('class', '').lower() for f in fields):
            return "material_ui"

        return "plain_html"

    def _extract_code_snippets(self, generated_code: str) -> Dict[str, str]:
        """
        Extract ACTUAL reusable code snippets from generated scraper

        Instead of storing descriptions, extracts full method implementations
        that can be directly reused in future scrapers.
        """
        snippets = {}

        # Extract ant-design searchable select handler (proven working)
        ant_select_match = re.search(
            r'(async def _fill_searchable_select\(self[^)]+\):.*?(?=\n    async def |\n    def |\nclass |\Z))',
            generated_code,
            re.DOTALL
        )
        if ant_select_match:
            snippets["ant_select"] = ant_select_match.group(1).strip()
            logger.debug("Extracted ant_select snippet")

        # Extract select2 handler
        select2_match = re.search(
            r'(async def _fill_select2[^(]*\([^)]+\):.*?(?=\n    async def |\n    def |\nclass |\Z))',
            generated_code,
            re.DOTALL
        )
        if select2_match:
            snippets["select2"] = select2_match.group(1).strip()
            logger.debug("Extracted select2 snippet")

        # Extract cascade handler
        cascade_match = re.search(
            r'(async def _fill_cascading[^(]*\([^)]+\):.*?(?=\n    async def |\n    def |\nclass |\Z))',
            generated_code,
            re.DOTALL
        )
        if cascade_match:
            snippets["cascade"] = cascade_match.group(1).strip()
            logger.debug("Extracted cascade snippet")

        # Extract text input with validation handler
        text_val_match = re.search(
            r'(async def _fill_text[^(]*\([^)]+\):.*?(?=\n    async def |\n    def |\nclass |\Z))',
            generated_code,
            re.DOTALL
        )
        if text_val_match:
            snippets["text_input"] = text_val_match.group(1).strip()
            logger.debug("Extracted text_input snippet")

        # Extract file upload handler
        upload_match = re.search(
            r'(async def _upload[^(]*\([^)]+\):.*?(?=\n    async def |\n    def |\nclass |\Z))',
            generated_code,
            re.DOTALL
        )
        if upload_match:
            snippets["file_upload"] = upload_match.group(1).strip()
            logger.debug("Extracted file_upload snippet")

        # Extract ASP.NET viewstate handler
        viewstate_match = re.search(
            r'(async def _get_asp[^(]*\([^)]+\):.*?(?=\n    async def |\n    def |\nclass |\Z))',
            generated_code,
            re.DOTALL
        )
        if viewstate_match:
            snippets["asp_viewstate"] = viewstate_match.group(1).strip()
            logger.debug("Extracted asp_viewstate snippet")

        # Extract retry decorator if present
        retry_match = re.search(
            r'(def retry_with_backoff\([^)]+\):.*?(?=\ndef |\nclass |\nasync def |\Z))',
            generated_code,
            re.DOTALL
        )
        if retry_match:
            snippets["retry_decorator"] = retry_match.group(1).strip()
            logger.debug("Extracted retry_decorator snippet")

        # Log extraction summary
        if snippets:
            logger.info(f"   Extracted {len(snippets)} code snippets: {list(snippets.keys())}")
        else:
            # Fallback to basic detection
            if "await page.fill(" in generated_code:
                snippets["basic_fill"] = "page.fill()"
            if "await page.select_option(" in generated_code:
                snippets["basic_select"] = "page.select_option()"

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

        stats = {
            "total_patterns": total_patterns,
            "avg_confidence": round(avg_confidence, 2),
            "avg_success_rate": round(avg_success, 2),
            "vector_store_enabled": self.use_vector_search
        }

        if self.use_vector_search and self.vector_store:
            try:
                # Get vector store count
                stats["vector_store_count"] = self.vector_store._collection.count()
            except Exception as e:
                logger.debug(f"Could not get vector store count: {e}")
                stats["vector_store_count"] = "unavailable"

        return stats

    def find_similar_patterns_semantic(
        self,
        form_schema: Dict[str, Any],
        municipality: str = "",
        top_k: int = 3
    ) -> List[Tuple[float, ScraperPattern]]:
        """
        Find similar patterns using semantic vector search

        Uses embeddings to understand semantic similarity beyond just field types.
        Example: "mobile_number" vs "phone" vs "contact" are semantically similar.

        Args:
            form_schema: Form schema to match
            municipality: Municipality name (for context)
            top_k: Number of results

        Returns:
            List of (similarity_score, pattern) tuples
        """
        if not self.use_vector_search:
            logger.warning("Vector search not available, use find_similar_patterns() instead")
            return []

        try:
            # Convert schema to searchable text
            query_text = self._schema_to_searchable_text(form_schema, municipality)

            # Semantic search
            results = self.vector_store.similarity_search_with_score(
                query=query_text,
                k=top_k
            )

            # Convert to pattern objects
            similar_patterns = []

            for doc, score in results:
                # Get full pattern from SQL by signature
                form_signature = doc.metadata.get("form_signature")

                if form_signature:
                    pattern = self._get_pattern_by_signature(form_signature)
                    if pattern:
                        # Convert distance to similarity (closer = more similar)
                        similarity = 1.0 / (1.0 + score)
                        similar_patterns.append((similarity, pattern))

            logger.info(f"✓ Semantic search found {len(similar_patterns)} matches")
            return similar_patterns

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def find_similar_patterns_hybrid(
        self,
        form_schema: Dict[str, Any],
        municipality: str = "",
        top_k: int = 3
    ) -> List[ScraperPattern]:
        """
        Hybrid search: combines SQL (structural) + vector (semantic) search

        Best of both worlds:
        - SQL finds structurally similar forms (same field types)
        - Vectors find semantically similar forms (similar purpose/domain)
        - Merges and re-ranks results

        Args:
            form_schema: Form schema
            municipality: Municipality name
            top_k: Number of results

        Returns:
            List of ScraperPattern objects sorted by combined similarity
        """
        # Get SQL results (structural similarity)
        sql_results = self.find_similar_patterns(form_schema, top_k=top_k*2)

        if not self.use_vector_search:
            # Fall back to SQL only
            return sql_results[:top_k]

        # Get vector results (semantic similarity)
        vector_results = self.find_similar_patterns_semantic(form_schema, municipality, top_k=top_k*2)

        # Merge and combine scores
        combined = {}

        # Add SQL results
        for i, pattern in enumerate(sql_results):
            score = 1.0 - (i / len(sql_results)) if sql_results else 0
            combined[pattern.form_signature] = {
                "pattern": pattern,
                "sql_score": score,
                "vector_score": 0.0
            }

        # Add vector results
        for similarity, pattern in vector_results:
            if pattern.form_signature in combined:
                combined[pattern.form_signature]["vector_score"] = similarity
            else:
                combined[pattern.form_signature] = {
                    "pattern": pattern,
                    "sql_score": 0.0,
                    "vector_score": similarity
                }

        # Calculate combined score (weighted average)
        scored_patterns = []
        for sig, data in combined.items():
            # 60% SQL (structural), 40% semantic
            combined_score = (0.6 * data["sql_score"]) + (0.4 * data["vector_score"])
            scored_patterns.append((combined_score, data["pattern"]))

        # Sort by combined score
        scored_patterns.sort(key=lambda x: x[0], reverse=True)

        results = [pattern for _, pattern in scored_patterns[:top_k]]

        logger.info(f"✓ Hybrid search found {len(results)} matches (SQL: {len(sql_results)}, Vector: {len(vector_results)})")
        return results

    def _schema_to_searchable_text(self, schema: Dict[str, Any], municipality: str = "") -> str:
        """
        Convert form schema to searchable text for embeddings

        Creates rich text description that captures semantic meaning
        """
        fields = schema.get("fields", [])

        text_parts = []

        # Municipality context
        if municipality:
            text_parts.append(f"Municipality: {municipality}")

        # Field descriptions (semantic rich)
        text_parts.append(f"Form with {len(fields)} fields:")

        for field in fields[:20]:  # Limit to avoid token limits
            name = field.get("name", "unknown").replace("_", " ")
            ftype = field.get("type", "text")
            required = "required" if field.get("required") else "optional"

            field_desc = f"{name} ({ftype}, {required})"

            # Add semantic context
            if ftype == "select" and field.get("options"):
                field_desc += f" with {len(field['options'])} options"
            if field.get("depends_on"):
                field_desc += f" cascades from {field['depends_on']}"
            if field.get("validation"):
                field_desc += f" validated"

            text_parts.append(field_desc)

        # Form features
        features = []
        if schema.get("captcha_present"):
            features.append("has CAPTCHA")
        if schema.get("multi_step"):
            features.append("multi-step form")
        if any(f.get("type") == "file" for f in fields):
            features.append("has file upload")

        cascading_count = len([f for f in fields if f.get("depends_on")])
        if cascading_count > 0:
            features.append(f"{cascading_count} cascading fields")

        if features:
            text_parts.append(f"Features: {', '.join(features)}")

        return "\n".join(text_parts)

    def _get_pattern_by_signature(self, form_signature: str) -> Optional[ScraperPattern]:
        """Get pattern from SQL by form signature"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM patterns WHERE form_signature = ? LIMIT 1",
            (form_signature,)
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return self._row_to_pattern(row)
        return None

    def get_templates_for_schema(self, form_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get recommended code templates based on form schema

        Combines:
        1. Templates from code_templates.py based on detected framework
        2. Code snippets from similar successful patterns
        3. Cascade pattern recommendations

        Args:
            form_schema: Form schema to analyze

        Returns:
            Dictionary with templates, snippets, and recommendations
        """
        result = {
            "ui_framework": "unknown",
            "framework_confidence": 0.0,
            "templates": {},
            "snippets_from_patterns": {},
            "cascade_recommendations": [],
            "recommendations": []
        }

        # 1. Detect UI framework
        ui_framework = self._detect_ui_framework(form_schema, "")
        result["ui_framework"] = ui_framework

        # 2. Try to get templates from code_templates module
        try:
            from knowledge.code_templates import (
                get_templates_for_framework,
                get_cascade_pattern,
                UIFramework as TemplateFramework
            )

            # Map string to enum
            framework_map = {
                "ant_design": TemplateFramework.ANT_DESIGN,
                "select2": TemplateFramework.SELECT2,
                "asp_net_webforms": TemplateFramework.ASP_NET_WEBFORMS,
                "bootstrap": TemplateFramework.PLAIN_HTML,
                "material_ui": TemplateFramework.MATERIAL_UI,
                "plain_html": TemplateFramework.PLAIN_HTML,
            }

            template_framework = framework_map.get(ui_framework, TemplateFramework.PLAIN_HTML)
            templates = get_templates_for_framework(template_framework)

            for name, template in templates.items():
                result["templates"][name] = {
                    "code": template.code,
                    "description": template.description,
                    "tested_on": template.tested_on
                }

            result["framework_confidence"] = 0.8 if templates else 0.3
            logger.info(f"   Found {len(templates)} templates for {ui_framework}")

        except ImportError:
            logger.warning("code_templates module not available")

        # 3. Get snippets from similar patterns in library
        similar_patterns = self.find_similar_patterns(form_schema, top_k=3)
        for pattern in similar_patterns:
            if pattern.code_snippets:
                for snippet_type, snippet_code in pattern.code_snippets.items():
                    if snippet_type not in result["snippets_from_patterns"]:
                        result["snippets_from_patterns"][snippet_type] = {
                            "code": snippet_code,
                            "source": pattern.municipality_name,
                            "confidence": pattern.confidence_score
                        }

        # 4. Detect cascade patterns
        fields = form_schema.get("fields", [])
        cascade_fields = [f for f in fields if f.get("cascades_to") or f.get("depends_on")]

        try:
            from knowledge.code_templates import get_cascade_pattern, get_recommended_wait_time

            for field in cascade_fields:
                parent = field.get("name", "")
                child = field.get("cascades_to", "")
                if parent and child:
                    cascade_info = get_cascade_pattern(parent, child)
                    if cascade_info:
                        result["cascade_recommendations"].append({
                            "parent": parent,
                            "child": child,
                            "wait_time": cascade_info["wait_time"],
                            "description": cascade_info["description"]
                        })
                    else:
                        # Default recommendation
                        result["cascade_recommendations"].append({
                            "parent": parent,
                            "child": child,
                            "wait_time": get_recommended_wait_time(parent, child),
                            "description": f"Cascade: {parent} → {child}"
                        })
        except ImportError:
            pass

        # 5. Build recommendations list
        if ui_framework == "ant_design":
            result["recommendations"] = [
                "Use _fill_searchable_select() for ant-select dropdowns",
                "Find visible dropdown with .ant-select-dropdown",
                "Wait 0.8s after click for dropdown animation",
            ]
        elif ui_framework == "select2":
            result["recommendations"] = [
                "DO NOT use page.select_option() - use jQuery",
                "Set value with $(selector).val(value).trigger('change')",
            ]
        elif ui_framework == "asp_net_webforms":
            result["recommendations"] = [
                "Extract __VIEWSTATE before submission",
                "Selectors use ctl00_ContentPlaceHolder1_ prefix",
            ]

        return result
