"""
AI Agent Trainer - Trains AI agents using human recordings as ground truth
Improves form discovery using HITL data with Claude Opus
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from config.ai_client import ai_client
from agents.base_agent import cost_tracker
from intelligence.training_data_manager import TrainingDataManager, TrainingExample

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TrainingPrompt:
    """Training prompt for teaching AI agents"""
    municipality: str
    task_description: str
    ground_truth: Dict[str, Any]
    examples: List[TrainingExample]
    context: str


class AgentTrainer:
    """
    Trains AI agents using human recordings as training data
    Uses Claude Opus for learning from examples
    """

    def __init__(self):
        self.training_manager = TrainingDataManager()
        self.models_dir = Path("intelligence/trained_models")
        self.models_dir.mkdir(parents=True, exist_ok=True)

    async def train_form_discovery(
        self,
        municipality: str,
        recording_examples: List[TrainingExample]
    ) -> Dict[str, Any]:
        """
        Train form discovery agent using human recordings

        Args:
            municipality: Municipality name
            recording_examples: List of training examples from recordings

        Returns:
            Training result with learned patterns
        """
        logger.info(f"🎓 Training form discovery for {municipality}")
        logger.info(f"   Using {len(recording_examples)} training examples")

        # Build training prompt
        training_prompt = self._build_discovery_training_prompt(
            municipality,
            recording_examples
        )

        # Call Opus model for learning
        response = await self._call_opus_model(training_prompt)

        # Parse learned patterns
        learned_patterns = self._parse_learned_patterns(response)

        # Save trained model
        model_data = {
            "municipality": municipality,
            "trained_on": len(recording_examples),
            "learned_patterns": learned_patterns,
            "training_cost": cost_tracker.total_cost
        }

        self._save_trained_model(municipality, model_data)

        logger.info(f"✅ Training complete! Learned {len(learned_patterns.get('field_patterns', []))} patterns")

        return {
            "success": True,
            "municipality": municipality,
            "patterns_learned": len(learned_patterns.get('field_patterns', [])),
            "model_file": str(self.models_dir / f"{municipality}_discovery_model.json")
        }

    def _build_discovery_training_prompt(
        self,
        municipality: str,
        examples: List[TrainingExample]
    ) -> str:
        """
        Build comprehensive training prompt from examples

        Returns:
            Training prompt for Opus
        """
        prompt = f"""You are training an AI agent to automatically discover and understand grievance submission forms.

**Municipality**: {municipality}

**Your Task**: Learn patterns from these human recordings to teach an AI agent how to:
1. Identify form fields (text inputs, dropdowns, textareas, etc.)
2. Extract dropdown options and their values
3. Understand field dependencies (cascading dropdowns)
4. Detect submit buttons
5. Recognize success indicators

**Training Examples**:

"""

        for i, example in enumerate(examples, 1):
            prompt += f"\n### Example {i}:\n"
            prompt += f"URL: {example.url}\n"
            prompt += f"Success: {example.success}\n"
            prompt += f"Total Actions: {example.total_actions}\n\n"

            # Include discovered fields
            if example.fields_discovered:
                prompt += "**Fields Discovered:**\n```json\n"
                prompt += json.dumps(example.fields_discovered, indent=2)
                prompt += "\n```\n\n"

            # Include dropdown options (limit to show structure)
            if example.dropdown_options:
                prompt += f"**Dropdown Fields:** {len(example.dropdown_options)} dropdowns\n"
                for selector, options in list(example.dropdown_options.items())[:2]:
                    prompt += f"  - {selector}: {len(options)} options\n"
                    # Show first few options
                    for opt in options[:3]:
                        prompt += f"    - {opt.get('text')} (value: {opt.get('value')})\n"
                prompt += "\n"

            # Include action sequence (summarized)
            if example.actions_sequence:
                action_types = [a.get('type') for a in example.actions_sequence]
                from collections import Counter
                action_counts = Counter(action_types)
                prompt += "**Action Types:**\n"
                for action_type, count in action_counts.items():
                    prompt += f"  - {action_type}: {count}\n"
                prompt += "\n"

        prompt += """
**Instructions**:

Based on these examples, extract and describe:

1. **Field Detection Patterns**:
   - What CSS selectors are used? (e.g., `input[type=text]`, `select`, `textarea`)
   - What ID patterns appear? (e.g., ASP.NET patterns like `ctl00_ContentPlaceHolder1_*`)
   - What are common field names?

2. **Dropdown Analysis**:
   - How are dropdowns structured?
   - What value patterns exist? (numeric IDs, strings, etc.)
   - Are there placeholder options (like "--Not Set--")?

3. **Field Dependencies**:
   - Do any fields depend on others?
   - Are there cascading dropdowns?

4. **Submit Button Patterns**:
   - What selectors identify submit buttons?
   - What text appears on submit buttons?

5. **Success Detection**:
   - What indicates successful submission?
   - Are there tracking IDs or confirmation messages?

**Output Format**:

Return a JSON object with this structure:

```json
{
  "field_patterns": [
    {
      "type": "text|dropdown|textarea|etc",
      "selector_pattern": "CSS selector pattern",
      "id_pattern": "Regex pattern for IDs",
      "detection_method": "How to detect this field type"
    }
  ],
  "dropdown_patterns": {
    "value_type": "numeric|string|mixed",
    "placeholder_values": ["0", "--Not Set--"],
    "option_structure": "description of structure"
  },
  "submit_button_patterns": [
    "selector patterns for submit buttons"
  ],
  "success_indicators": [
    "patterns that indicate success"
  ],
  "confidence_score": 0.0-1.0
}
```

Analyze the examples and return the learned patterns in JSON format.
"""

        return prompt

    async def _call_opus_model(self, prompt: str) -> str:
        """
        Call Opus model for training

        Args:
            prompt: Training prompt

        Returns:
            Model response text
        """
        response = ai_client.client.chat.completions.create(
            model=ai_client.models["powerful"],  # Use Opus
            messages=[{
                "role": "user",
                "content": prompt
            }],
            temperature=0.3,
            max_tokens=4096
        )

        return response.choices[0].message.content

    def _parse_learned_patterns(self, response: str) -> Dict[str, Any]:
        """
        Parse learned patterns from Opus response

        Args:
            response: Opus response text

        Returns:
            Structured patterns dictionary
        """
        try:
            # Try to extract JSON from response
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_text = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_text = response[json_start:json_end].strip()
            else:
                json_text = response

            patterns = json.loads(json_text)
            return patterns

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse learned patterns: {e}")
            # Return default structure
            return {
                "field_patterns": [],
                "dropdown_patterns": {},
                "submit_button_patterns": [],
                "success_indicators": [],
                "confidence_score": 0.0,
                "raw_response": response
            }

    def _save_trained_model(self, municipality: str, model_data: Dict[str, Any]):
        """Save trained model to disk"""
        model_file = self.models_dir / f"{municipality}_discovery_model.json"

        with open(model_file, 'w') as f:
            json.dump(model_data, f, indent=2, default=str)

        logger.info(f"💾 Saved trained model: {model_file}")

    async def train_nlp_understanding(
        self,
        municipality: str,
        knowledge_base: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Train NLP understanding for mapping natural language to dropdown values

        Args:
            municipality: Municipality name
            knowledge_base: Knowledge base with field mappings

        Returns:
            Training result
        """
        logger.info(f"🧠 Training NLP understanding for {municipality}")

        field_mappings = knowledge_base.get('field_mappings', {})

        prompt = f"""You are training an NLP system to map natural language grievance descriptions to dropdown values.

**Municipality**: {municipality}

**Available Fields and Options**:

"""

        for field_name, field_data in field_mappings.items():
            searchable = field_data.get('searchable_values', {})
            prompt += f"\n### {field_name}:\n"
            prompt += f"Total options: {len(searchable)}\n"
            prompt += "Sample options:\n"

            # Show sample options
            for label, value in list(searchable.items())[:10]:
                prompt += f"  - \"{label}\" → {value}\n"

            prompt += "\n"

        prompt += """
**Task**: Analyze these dropdown options and create intelligent mapping rules.

For each field, identify:
1. **Keywords**: Important words that indicate this option
2. **Synonyms**: Alternative phrases users might use
3. **Patterns**: Common patterns in option names
4. **Categories**: Group similar options together

**Output Format**:

Return a JSON object with enhanced mapping rules:

```json
{
  "fields": {
    "field_name": {
      "keywords": ["word1", "word2"],
      "synonyms": {"official_term": ["synonym1", "synonym2"]},
      "categories": {
        "category_name": ["value1", "value2"]
      },
      "fuzzy_threshold": 0.5-0.9,
      "mapping_strategy": "description of how to map"
    }
  },
  "confidence_score": 0.0-1.0
}
```

Analyze and return the mapping rules in JSON format.
"""

        response = await self._call_opus_model(prompt)

        # Parse learned mapping rules
        mapping_rules = self._parse_learned_patterns(response)

        # Save NLP model
        model_data = {
            "municipality": municipality,
            "mapping_rules": mapping_rules,
            "training_cost": cost_tracker.total_cost
        }

        nlp_model_file = self.models_dir / f"{municipality}_nlp_model.json"
        with open(nlp_model_file, 'w') as f:
            json.dump(model_data, f, indent=2, default=str)

        logger.info(f"✅ NLP training complete! Saved to {nlp_model_file}")

        return {
            "success": True,
            "municipality": municipality,
            "model_file": str(nlp_model_file)
        }

    def load_trained_model(self, municipality: str, model_type: str = "discovery") -> Optional[Dict[str, Any]]:
        """
        Load a trained model

        Args:
            municipality: Municipality name
            model_type: 'discovery' or 'nlp'

        Returns:
            Model data or None
        """
        model_file = self.models_dir / f"{municipality}_{model_type}_model.json"

        if not model_file.exists():
            logger.warning(f"Model not found: {model_file}")
            return None

        with open(model_file) as f:
            return json.load(f)


# CLI tool
async def main():
    import sys

    trainer = AgentTrainer()

    if len(sys.argv) > 1:
        municipality = sys.argv[1]
    else:
        municipality = "ranchi_smart"

    logger.info(f"🎓 Starting training for {municipality}")

    # Load training examples
    trainer.training_manager.process_all_recordings()
    examples = trainer.training_manager.get_municipality_examples(municipality)

    if not examples:
        logger.error(f"❌ No training examples found for {municipality}")
        return

    # Train form discovery
    discovery_result = await trainer.train_form_discovery(municipality, examples)
    logger.info(f"\n✅ Form Discovery Training: {discovery_result}")

    # Load knowledge base for NLP training
    kb_file = Path(f"knowledge/{municipality}_field_mappings.json")
    if kb_file.exists():
        with open(kb_file) as f:
            kb = json.load(f)

        nlp_result = await trainer.train_nlp_understanding(municipality, kb)
        logger.info(f"\n✅ NLP Training: {nlp_result}")

    logger.info(f"\n🎉 Training complete for {municipality}!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
