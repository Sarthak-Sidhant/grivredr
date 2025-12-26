"""
Training Data Manager - Converts human recordings into AI training data
Learns from HITL interactions to improve automatic form discovery
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TrainingExample:
    """Single training example from human recording"""
    municipality: str
    url: str
    recording_id: str
    timestamp: datetime

    # Ground truth from human
    fields_discovered: List[Dict[str, Any]]
    dropdown_options: Dict[str, List[Dict]]
    actions_sequence: List[Dict[str, Any]]
    submit_button: Dict[str, str]

    # Metadata
    success: bool
    tracking_id: Optional[str] = None
    total_actions: int = 0

    def to_dict(self):
        return {
            **asdict(self),
            'timestamp': str(self.timestamp)
        }


class TrainingDataManager:
    """
    Manages conversion of human recordings into structured training data
    for improving AI agents
    """

    def __init__(self, recordings_dir: str = "recordings/sessions"):
        self.recordings_dir = Path(recordings_dir)
        self.training_data_dir = Path("intelligence/training_data")
        self.training_data_dir.mkdir(parents=True, exist_ok=True)

        self.examples: List[TrainingExample] = []
        self._load_existing_training_data()

    def _load_existing_training_data(self):
        """Load previously processed training examples"""
        training_file = self.training_data_dir / "training_examples.json"
        if training_file.exists():
            with open(training_file) as f:
                data = json.load(f)
                logger.info(f"📚 Loaded {len(data)} existing training examples")

    def process_recording(self, recording_path: Path) -> Optional[TrainingExample]:
        """
        Convert a human recording into a training example

        Args:
            recording_path: Path to recording JSON file

        Returns:
            TrainingExample or None if invalid
        """
        logger.info(f"📖 Processing recording: {recording_path.name}")

        with open(recording_path) as f:
            recording = json.load(f)

        # Extract metadata (check both metadata and root level)
        metadata = recording.get('metadata', {})
        municipality = recording.get('municipality') or metadata.get('municipality', 'unknown')
        url = recording.get('url') or metadata.get('url', '')
        recording_id = recording_path.stem

        # Parse timestamp
        timestamp_str = metadata.get('timestamp')
        if timestamp_str:
            timestamp = datetime.fromisoformat(timestamp_str)
        else:
            # Use start_time if available
            start_time = recording.get('start_time')
            if start_time:
                timestamp = datetime.fromtimestamp(start_time)
            else:
                timestamp = datetime.now()

        # Extract field discoveries from actions
        fields_discovered = self._extract_fields_from_actions(
            recording.get('actions', [])
        )

        # Extract dropdown options
        dropdown_options = recording.get('dropdown_options', {})

        # Extract action sequence
        actions_sequence = recording.get('actions', [])

        # Find submit button
        submit_button = self._find_submit_action(actions_sequence)

        # Success indicator
        success = metadata.get('success', False)
        tracking_id = metadata.get('tracking_id')

        example = TrainingExample(
            municipality=municipality,
            url=url,
            recording_id=recording_id,
            timestamp=timestamp,
            fields_discovered=fields_discovered,
            dropdown_options=dropdown_options,
            actions_sequence=actions_sequence,
            submit_button=submit_button,
            success=success,
            tracking_id=tracking_id,
            total_actions=len(actions_sequence)
        )

        self.examples.append(example)
        logger.info(f"✅ Created training example: {len(fields_discovered)} fields, {len(dropdown_options)} dropdowns")

        return example

    def _extract_fields_from_actions(self, actions: List[Dict]) -> List[Dict[str, Any]]:
        """Extract field information from recorded actions"""
        fields = {}

        for action in actions:
            action_type = action.get('type')
            selector = action.get('selector')

            if not selector:
                continue

            # Determine field type and properties
            if action_type == 'fill':
                field_name = self._extract_field_name(selector)
                fields[field_name] = {
                    'name': field_name,
                    'selector': selector,
                    'type': 'text',
                    'label': action.get('field_name', field_name),
                    'required': True,  # Assume required if human filled it
                    'example_value': action.get('value')
                }

            elif action_type == 'select':
                field_name = self._extract_field_name(selector)
                fields[field_name] = {
                    'name': field_name,
                    'selector': selector,
                    'type': 'dropdown',
                    'label': action.get('field_name', field_name),
                    'required': True,
                    'selected_value': action.get('value'),
                    'selected_label': action.get('label')
                }

        return list(fields.values())

    def _extract_field_name(self, selector: str) -> str:
        """Extract field name from selector"""
        # Remove '#' prefix
        name = selector.replace('#', '')

        # Extract last part after underscores
        parts = name.split('_')
        if len(parts) > 2:
            return '_'.join(parts[-2:])
        return name

    def _find_submit_action(self, actions: List[Dict]) -> Dict[str, str]:
        """Find submit button from actions"""
        for action in reversed(actions):
            if action.get('type') == 'click' and 'submit' in action.get('selector', '').lower():
                return {
                    'selector': action.get('selector'),
                    'text': action.get('label', 'Submit')
                }

        return {'selector': 'button[type=submit]', 'text': 'Submit'}

    def process_all_recordings(self) -> int:
        """Process all recordings in the recordings directory"""
        if not self.recordings_dir.exists():
            logger.warning(f"Recordings directory not found: {self.recordings_dir}")
            return 0

        recording_files = list(self.recordings_dir.glob("*.json"))
        logger.info(f"📂 Found {len(recording_files)} recording files")

        processed = 0
        for recording_file in recording_files:
            try:
                example = self.process_recording(recording_file)
                if example:
                    processed += 1
            except Exception as e:
                logger.error(f"❌ Failed to process {recording_file.name}: {e}")

        logger.info(f"✅ Processed {processed}/{len(recording_files)} recordings")
        return processed

    def save_training_data(self):
        """Save all training examples to disk"""
        output_file = self.training_data_dir / "training_examples.json"

        data = [example.to_dict() for example in self.examples]

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"💾 Saved {len(data)} training examples to {output_file}")

    def get_municipality_examples(self, municipality: str) -> List[TrainingExample]:
        """Get all training examples for a specific municipality"""
        return [ex for ex in self.examples if ex.municipality == municipality]

    def generate_training_summary(self) -> Dict[str, Any]:
        """Generate summary statistics of training data"""
        if not self.examples:
            return {"total_examples": 0}

        municipalities = set(ex.municipality for ex in self.examples)
        total_fields = sum(len(ex.fields_discovered) for ex in self.examples)
        total_dropdowns = sum(len(ex.dropdown_options) for ex in self.examples)
        successful = sum(1 for ex in self.examples if ex.success)

        return {
            "total_examples": len(self.examples),
            "municipalities": list(municipalities),
            "total_fields_discovered": total_fields,
            "total_dropdowns": total_dropdowns,
            "successful_submissions": successful,
            "success_rate": successful / len(self.examples) if self.examples else 0,
            "avg_actions_per_recording": sum(ex.total_actions for ex in self.examples) / len(self.examples)
        }


# CLI tool
if __name__ == "__main__":
    import sys

    manager = TrainingDataManager()

    if len(sys.argv) > 1:
        # Process specific recording
        recording_path = Path(sys.argv[1])
        manager.process_recording(recording_path)
    else:
        # Process all recordings
        manager.process_all_recordings()

    # Save training data
    manager.save_training_data()

    # Print summary
    summary = manager.generate_training_summary()
    print("\n" + "="*70)
    print("TRAINING DATA SUMMARY")
    print("="*70)
    for key, value in summary.items():
        print(f"{key}: {value}")
