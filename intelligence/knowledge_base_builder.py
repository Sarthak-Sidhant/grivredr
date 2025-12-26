"""
Knowledge Base Builder - Learns from human recordings to build comprehensive knowledge bases
Creates searchable field mappings for NLP queries
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Set
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeBaseBuilder:
    """
    Builds knowledge bases from human recordings
    Creates searchable mappings for dropdown values
    """

    def __init__(self, recordings_dir: str = "recordings/sessions"):
        self.recordings_dir = Path(recordings_dir)
        self.knowledge_dir = Path("knowledge")
        self.knowledge_dir.mkdir(exist_ok=True)

    def build_from_recording(self, recording_path: Path) -> Dict[str, Any]:
        """
        Build knowledge base from a single recording

        Args:
            recording_path: Path to recording JSON

        Returns:
            Knowledge base dictionary
        """
        logger.info(f"🧠 Building knowledge base from: {recording_path.name}")

        with open(recording_path) as f:
            recording = json.load(f)

        metadata = recording.get('metadata', {})
        municipality = recording.get('municipality') or metadata.get('municipality', 'unknown')
        url = recording.get('url') or metadata.get('url', '')

        # Extract dropdown options
        dropdown_options = recording.get('dropdown_options', {})

        if not dropdown_options:
            logger.warning(f"⚠️ No dropdown options found in recording")
            return {}

        # Build field mappings
        field_mappings = self._build_field_mappings(dropdown_options)

        knowledge_base = {
            "municipality": municipality,
            "url": url,
            "created_from": "human_recording",
            "recording_id": recording_path.stem,
            "field_mappings": field_mappings,
            "metadata": {
                "total_fields": len(field_mappings),
                "total_options": sum(len(fm.get('searchable_values', {})) for fm in field_mappings.values()),
                "created_at": metadata.get('timestamp')
            }
        }

        return knowledge_base

    def _build_field_mappings(
        self,
        dropdown_options: Dict[str, List[Dict]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build searchable field mappings from dropdown options

        Args:
            dropdown_options: Dict mapping selectors to option lists

        Returns:
            Field mappings with searchable values
        """
        field_mappings = {}

        for selector, options in dropdown_options.items():
            # Extract field name from selector
            field_name = self._extract_field_name(selector)

            # Build searchable values
            searchable_values = self._build_searchable_values(options)

            # Create field mapping
            field_mappings[field_name] = {
                "field_id": selector.replace('#', '').replace('_', ''),
                "selector": selector,
                "label": field_name.replace('_', ' ').title(),
                "type": "select",
                "required": True,
                "searchable_values": searchable_values,
                "total_options": len(options)
            }

            logger.info(f"  ✓ {field_name}: {len(searchable_values)} searchable values")

        return field_mappings

    def _extract_field_name(self, selector: str) -> str:
        """Extract clean field name from selector"""
        # Remove # prefix
        name = selector.replace('#', '')

        # Handle ASP.NET naming (e.g., ctl00_ContentPlaceHolder1_ddlProblem -> problem)
        if 'ddl' in name.lower():
            # Extract part after 'ddl'
            parts = name.split('ddl')
            if len(parts) > 1:
                field_name = parts[-1].lower()
                return field_name

        # Handle regular selectors
        parts = name.split('_')
        if len(parts) > 2:
            return '_'.join(parts[-2:]).lower()

        return name.lower()

    def _build_searchable_values(
        self,
        options: List[Dict]
    ) -> Dict[str, str]:
        """
        Build searchable value mappings from dropdown options

        Creates multiple searchable variations of each option:
        - Original text (lowercased)
        - Simplified version (no special chars)
        - Common abbreviations
        - Keyword variations

        Args:
            options: List of option dictionaries with 'value' and 'text'

        Returns:
            Dict mapping searchable strings to option values
        """
        searchable = {}

        for opt in options:
            value = opt.get('value', '')
            text = opt.get('text', '')

            # Skip empty or placeholder values
            if not value or not text or value == '0' or text.lower().startswith('--'):
                continue

            text_lower = text.lower().strip()

            # Add original text
            searchable[text_lower] = value

            # Add simplified version (remove special characters)
            simplified = re.sub(r'[^\w\s]', ' ', text_lower)
            simplified = re.sub(r'\s+', ' ', simplified).strip()
            if simplified != text_lower and simplified:
                searchable[simplified] = value

            # Add individual keywords (for better partial matching)
            words = simplified.split()
            if len(words) > 2:
                # Add combinations of significant words
                significant_words = [w for w in words if len(w) > 3]
                if significant_words:
                    keywords = ' '.join(significant_words)
                    searchable[keywords] = value

        return searchable

    def build_from_all_recordings(self) -> Dict[str, Dict[str, Any]]:
        """
        Build knowledge bases from all recordings

        Returns:
            Dict mapping municipality names to knowledge bases
        """
        if not self.recordings_dir.exists():
            logger.warning(f"Recordings directory not found: {self.recordings_dir}")
            return {}

        recording_files = list(self.recordings_dir.glob("*.json"))
        logger.info(f"📂 Found {len(recording_files)} recording files")

        knowledge_bases = {}

        for recording_file in recording_files:
            try:
                kb = self.build_from_recording(recording_file)
                if kb:
                    municipality = kb['municipality']
                    knowledge_bases[municipality] = kb

                    # Save individual knowledge base
                    self._save_knowledge_base(kb)

            except Exception as e:
                logger.error(f"❌ Failed to build KB from {recording_file.name}: {e}")

        logger.info(f"\n✅ Built knowledge bases for {len(knowledge_bases)} municipalities")
        return knowledge_bases

    def _save_knowledge_base(self, kb: Dict[str, Any]):
        """Save knowledge base to file"""
        municipality = kb['municipality']
        output_file = self.knowledge_dir / f"{municipality}_field_mappings.json"

        with open(output_file, 'w') as f:
            json.dump(kb, f, indent=2)

        logger.info(f"💾 Saved knowledge base: {output_file}")

    def merge_knowledge_bases(
        self,
        municipality: str,
        knowledge_bases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge multiple knowledge bases for the same municipality
        Useful when you have multiple recordings

        Args:
            municipality: Municipality name
            knowledge_bases: List of knowledge base dicts

        Returns:
            Merged knowledge base
        """
        if not knowledge_bases:
            return {}

        # Start with first KB
        merged = knowledge_bases[0].copy()

        # Merge field mappings from other KBs
        for kb in knowledge_bases[1:]:
            for field_name, field_data in kb.get('field_mappings', {}).items():
                if field_name in merged['field_mappings']:
                    # Merge searchable values
                    merged['field_mappings'][field_name]['searchable_values'].update(
                        field_data.get('searchable_values', {})
                    )
                else:
                    # Add new field
                    merged['field_mappings'][field_name] = field_data

        # Update metadata
        merged['metadata']['merged_from'] = len(knowledge_bases)
        merged['metadata']['total_options'] = sum(
            len(fm.get('searchable_values', {}))
            for fm in merged['field_mappings'].values()
        )

        logger.info(f"🔀 Merged {len(knowledge_bases)} knowledge bases for {municipality}")
        return merged

    def analyze_coverage(self, municipality: str) -> Dict[str, Any]:
        """
        Analyze knowledge base coverage for a municipality

        Args:
            municipality: Municipality name

        Returns:
            Coverage analysis
        """
        kb_file = self.knowledge_dir / f"{municipality}_field_mappings.json"

        if not kb_file.exists():
            return {"error": "Knowledge base not found"}

        with open(kb_file) as f:
            kb = json.load(f)

        field_mappings = kb.get('field_mappings', {})

        analysis = {
            "municipality": municipality,
            "total_fields": len(field_mappings),
            "fields": {}
        }

        for field_name, field_data in field_mappings.items():
            searchable_values = field_data.get('searchable_values', {})
            analysis['fields'][field_name] = {
                "total_options": len(searchable_values),
                "searchable_variations": len(set(searchable_values.keys())),
                "unique_values": len(set(searchable_values.values()))
            }

        return analysis


# CLI tool
if __name__ == "__main__":
    import sys

    builder = KnowledgeBaseBuilder()

    if len(sys.argv) > 1:
        # Build from specific recording
        recording_path = Path(sys.argv[1])
        kb = builder.build_from_recording(recording_path)
        if kb:
            builder._save_knowledge_base(kb)
            print(f"\n✅ Knowledge base created for: {kb['municipality']}")
            print(f"   Total fields: {kb['metadata']['total_fields']}")
            print(f"   Total options: {kb['metadata']['total_options']}")
    else:
        # Build from all recordings
        knowledge_bases = builder.build_from_all_recordings()
        print(f"\n✅ Created {len(knowledge_bases)} knowledge bases")

        # Analyze coverage
        for municipality in knowledge_bases.keys():
            analysis = builder.analyze_coverage(municipality)
            print(f"\n📊 Coverage for {municipality}:")
            for field_name, stats in analysis.get('fields', {}).items():
                print(f"   {field_name}: {stats['total_options']} options, "
                      f"{stats['searchable_variations']} variations")
