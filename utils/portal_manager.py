"""
Portal Manager - Manages portal data directory structure for the scraper factory

This module provides a unified interface for storing and retrieving:
- Portal scrapers
- Form structures
- Dropdown context (options and cascades)
- Field mappings
- Training session data

Directory Structure:
portals/
├── {state}/
│   └── {district}/
│       └── {portal_name}/
│           ├── scraper.py
│           ├── structure.json
│           ├── context/
│           │   ├── dropdowns.json
│           │   ├── cascades.json
│           │   └── field_mappings.json
│           ├── metadata.json
│           ├── training/
│           │   ├── session.json
│           │   └── recording.json
│           └── screenshots/
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class PortalManager:
    """Manages portal data directory structure for the scraper factory"""

    def __init__(self, base_dir: str = "portals"):
        """
        Initialize PortalManager with base directory

        Args:
            base_dir: Base directory for portal data (default: "portals")
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"PortalManager initialized with base_dir: {self.base_dir}")

    def get_portal_path(self, state: str, district: str, portal: str) -> Path:
        """
        Get the path to a portal's data directory

        Args:
            state: State name (e.g., "jharkhand", "delhi")
            district: District name (e.g., "ranchi", "central_zone")
            portal: Portal name (e.g., "ranchi_smart", "mcd_delhi")

        Returns:
            Path to the portal directory
        """
        return self.base_dir / state.lower() / district.lower() / portal.lower()

    def create_portal_structure(self, state: str, district: str, portal: str) -> Path:
        """
        Create the full directory structure for a portal

        Args:
            state: State name
            district: District name
            portal: Portal name

        Returns:
            Path to the portal directory
        """
        portal_path = self.get_portal_path(state, district, portal)

        # Create all subdirectories
        (portal_path / "context").mkdir(parents=True, exist_ok=True)
        (portal_path / "training").mkdir(parents=True, exist_ok=True)
        (portal_path / "screenshots").mkdir(parents=True, exist_ok=True)

        logger.info(f"Created portal structure: {portal_path}")
        return portal_path

    def save_scraper(
        self,
        state: str,
        district: str,
        portal: str,
        scraper_code: str,
        class_name: Optional[str] = None
    ) -> Path:
        """
        Save generated scraper code

        Args:
            state: State name
            district: District name
            portal: Portal name
            scraper_code: The Python scraper code
            class_name: Optional class name for the scraper

        Returns:
            Path to saved scraper file
        """
        portal_path = self.create_portal_structure(state, district, portal)
        scraper_path = portal_path / "scraper.py"

        scraper_path.write_text(scraper_code)
        logger.info(f"Saved scraper to {scraper_path}")

        return scraper_path

    def save_structure(
        self,
        state: str,
        district: str,
        portal: str,
        structure: Dict[str, Any]
    ) -> Path:
        """
        Save form structure JSON

        Args:
            state: State name
            district: District name
            portal: Portal name
            structure: Form structure dictionary

        Returns:
            Path to saved structure file
        """
        portal_path = self.create_portal_structure(state, district, portal)
        structure_path = portal_path / "structure.json"

        with open(structure_path, 'w') as f:
            json.dump(structure, f, indent=2)
        logger.info(f"Saved structure to {structure_path}")

        return structure_path

    def save_context(
        self,
        state: str,
        district: str,
        portal: str,
        dropdowns: Optional[Dict[str, Any]] = None,
        cascades: Optional[Dict[str, Any]] = None,
        field_mappings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Path]:
        """
        Save dropdown context for AI requests

        This is critical for the scraper factory - it stores:
        - All dropdown options with their values/IDs
        - Cascading relationships with all child options
        - Human-readable to API value mappings

        Args:
            state: State name
            district: District name
            portal: Portal name
            dropdowns: Dropdown options {field_name: {selector, options: {label: value}}}
            cascades: Cascade relationships {relationship_name: {parent, child, mappings}}
            field_mappings: Field name to selector mappings

        Returns:
            Dictionary of paths to saved files
        """
        portal_path = self.create_portal_structure(state, district, portal)
        context_path = portal_path / "context"
        saved_paths = {}

        if dropdowns:
            dropdowns_path = context_path / "dropdowns.json"
            with open(dropdowns_path, 'w') as f:
                json.dump(dropdowns, f, indent=2)
            saved_paths["dropdowns"] = dropdowns_path
            logger.info(f"Saved dropdowns to {dropdowns_path}")

        if cascades:
            cascades_path = context_path / "cascades.json"
            with open(cascades_path, 'w') as f:
                json.dump(cascades, f, indent=2)
            saved_paths["cascades"] = cascades_path
            logger.info(f"Saved cascades to {cascades_path}")

        if field_mappings:
            mappings_path = context_path / "field_mappings.json"
            with open(mappings_path, 'w') as f:
                json.dump(field_mappings, f, indent=2)
            saved_paths["field_mappings"] = mappings_path
            logger.info(f"Saved field_mappings to {mappings_path}")

        return saved_paths

    def load_context(
        self,
        state: str,
        district: str,
        portal: str
    ) -> Dict[str, Any]:
        """
        Load all context needed for AI requests

        Returns:
            Dictionary with structure, dropdowns, cascades, field_mappings
        """
        portal_path = self.get_portal_path(state, district, portal)
        context = {}

        # Load structure
        structure_path = portal_path / "structure.json"
        if structure_path.exists():
            with open(structure_path) as f:
                context["structure"] = json.load(f)

        # Load context files
        context_path = portal_path / "context"
        for file_name in ["dropdowns.json", "cascades.json", "field_mappings.json"]:
            file_path = context_path / file_name
            if file_path.exists():
                key = file_name.replace(".json", "")
                with open(file_path) as f:
                    context[key] = json.load(f)

        return context

    def save_metadata(
        self,
        state: str,
        district: str,
        portal: str,
        url: str,
        framework_detected: Optional[str] = None,
        patterns_used: Optional[List[str]] = None,
        training_cost: float = 0.0,
        **extra_metadata
    ) -> Path:
        """
        Save portal metadata

        Args:
            state: State name
            district: District name
            portal: Portal name
            url: Portal URL
            framework_detected: Detected UI framework (e.g., "ant-design", "asp-net")
            patterns_used: List of pattern names used in generation
            training_cost: Cost of training in USD
            **extra_metadata: Any additional metadata

        Returns:
            Path to saved metadata file
        """
        portal_path = self.create_portal_structure(state, district, portal)
        metadata_path = portal_path / "metadata.json"

        metadata = {
            "portal_name": portal,
            "state": state,
            "district": district,
            "url": url,
            "framework_detected": framework_detected,
            "patterns_used": patterns_used or [],
            "training_cost": training_cost,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            **extra_metadata
        }

        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved metadata to {metadata_path}")

        return metadata_path

    def save_training_session(
        self,
        state: str,
        district: str,
        portal: str,
        session_data: Dict[str, Any],
        recording_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Path]:
        """
        Save training session data

        Args:
            state: State name
            district: District name
            portal: Portal name
            session_data: Training session data
            recording_data: Optional human recording data

        Returns:
            Dictionary of paths to saved files
        """
        portal_path = self.create_portal_structure(state, district, portal)
        training_path = portal_path / "training"
        saved_paths = {}

        # Save session
        session_path = training_path / "session.json"
        with open(session_path, 'w') as f:
            json.dump(session_data, f, indent=2, default=str)
        saved_paths["session"] = session_path

        # Save recording if provided
        if recording_data:
            recording_path = training_path / "recording.json"
            with open(recording_path, 'w') as f:
                json.dump(recording_data, f, indent=2, default=str)
            saved_paths["recording"] = recording_path

        logger.info(f"Saved training session to {training_path}")
        return saved_paths

    def list_portals(self, state: Optional[str] = None) -> List[Dict[str, str]]:
        """
        List all portals, optionally filtered by state

        Args:
            state: Optional state filter

        Returns:
            List of dictionaries with state, district, portal info
        """
        portals = []

        if state:
            state_path = self.base_dir / state.lower()
            if not state_path.exists():
                return []
            states = [state_path]
        else:
            states = [d for d in self.base_dir.iterdir() if d.is_dir()]

        for state_dir in states:
            for district_dir in state_dir.iterdir():
                if district_dir.is_dir():
                    for portal_dir in district_dir.iterdir():
                        if portal_dir.is_dir():
                            portals.append({
                                "state": state_dir.name,
                                "district": district_dir.name,
                                "portal": portal_dir.name,
                                "path": str(portal_dir)
                            })

        return portals

    def migrate_old_structure(self) -> Dict[str, Any]:
        """
        Migrate existing data from old structure to new unified structure

        Handles:
        - scrapers/ directory
        - outputs/generated_scrapers/ directory
        - knowledge/ field mappings
        - data/training_sessions/ data

        Returns:
            Migration report with counts and any errors
        """
        report = {
            "migrated": [],
            "errors": [],
            "skipped": []
        }

        # Migrate from scrapers/ directory
        scrapers_dir = Path("scrapers")
        if scrapers_dir.exists():
            for portal_dir in scrapers_dir.iterdir():
                if portal_dir.is_dir():
                    try:
                        self._migrate_scraper_dir(portal_dir, report)
                    except Exception as e:
                        report["errors"].append(f"scrapers/{portal_dir.name}: {e}")

        # Migrate from outputs/generated_scrapers/
        outputs_dir = Path("outputs/generated_scrapers")
        if outputs_dir.exists():
            for district_dir in outputs_dir.iterdir():
                if district_dir.is_dir():
                    for portal_dir in district_dir.iterdir():
                        if portal_dir.is_dir():
                            try:
                                self._migrate_scraper_dir(
                                    portal_dir, report,
                                    district=district_dir.name.replace("_district", "")
                                )
                            except Exception as e:
                                report["errors"].append(f"outputs/{district_dir.name}/{portal_dir.name}: {e}")

        # Migrate field mappings from knowledge/
        knowledge_dir = Path("knowledge")
        if knowledge_dir.exists():
            for file_path in knowledge_dir.glob("*_field_mappings.json"):
                try:
                    self._migrate_field_mapping(file_path, report)
                except Exception as e:
                    report["errors"].append(f"knowledge/{file_path.name}: {e}")

        logger.info(f"Migration complete: {len(report['migrated'])} migrated, "
                    f"{len(report['errors'])} errors, {len(report['skipped'])} skipped")
        return report

    def _migrate_scraper_dir(
        self,
        source_dir: Path,
        report: Dict[str, List],
        district: Optional[str] = None
    ):
        """Migrate a single scraper directory"""
        portal_name = source_dir.name.replace("_hybrid", "").replace("_scraper", "")

        # Try to determine state/district from metadata or directory structure
        metadata_file = source_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
            state = metadata.get("state", "unknown")
            district = district or metadata.get("district", "unknown")
        else:
            state = "unknown"
            district = district or "unknown"

        # Create new structure
        new_path = self.create_portal_structure(state, district, portal_name)

        # Copy files
        for file_path in source_dir.iterdir():
            if file_path.is_file():
                # Rename scraper files to standard name
                if file_path.suffix == ".py":
                    dest = new_path / "scraper.py"
                elif file_path.name.endswith("_structure.json"):
                    dest = new_path / "structure.json"
                else:
                    dest = new_path / file_path.name

                shutil.copy2(file_path, dest)

        report["migrated"].append(f"{source_dir} -> {new_path}")

    def _migrate_field_mapping(self, source_file: Path, report: Dict[str, List]):
        """Migrate a field mapping file from knowledge/"""
        with open(source_file) as f:
            data = json.load(f)

        # Extract portal info from filename or content
        portal_name = source_file.stem.replace("_field_mappings", "")
        state = data.get("state", "unknown")
        district = data.get("district", "unknown")

        # If municipality is in the data, use it
        if "municipality" in data:
            portal_name = data["municipality"]

        # Create context directory and save
        portal_path = self.create_portal_structure(state, district, portal_name)
        context_path = portal_path / "context"

        # Save as field_mappings.json
        dest = context_path / "field_mappings.json"
        shutil.copy2(source_file, dest)

        # Also extract dropdown options if present
        if "field_mappings" in data:
            dropdowns = {}
            for field_name, field_data in data.get("field_mappings", {}).items():
                if field_data.get("type") == "select" and "searchable_values" in field_data:
                    dropdowns[field_name] = {
                        "selector": field_data.get("selector"),
                        "options": field_data.get("searchable_values", {})
                    }

            if dropdowns:
                dropdowns_path = context_path / "dropdowns.json"
                with open(dropdowns_path, 'w') as f:
                    json.dump(dropdowns, f, indent=2)

        report["migrated"].append(f"{source_file} -> {dest}")


# Singleton instance for convenience
portal_manager = PortalManager()
