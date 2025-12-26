"""
Scraper Generator Trainer - Trains the scraper generator using documentation and recordings
Uses Claude Opus to learn from markdown docs and generate better scrapers
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.ai_client import ai_client
from agents.base_agent import cost_tracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScraperGeneratorTrainer:
    """
    Trains scraper generator using:
    1. Markdown documentation (patterns, examples, architecture)
    2. Human recordings (ground truth data)
    3. Existing generated scrapers (learn from what works)
    """

    def __init__(self):
        self.docs_knowledge_file = Path("intelligence/documentation_knowledge.json")
        self.training_data_file = Path("intelligence/training_data/training_examples.json")
        self.trained_model_dir = Path("intelligence/trained_models")
        self.trained_model_dir.mkdir(parents=True, exist_ok=True)

    async def train_from_documentation(
        self,
        municipality: str = "ranchi_smart"
    ) -> Dict[str, Any]:
        """
        Train scraper generator by analyzing documentation

        Args:
            municipality: Municipality to train for

        Returns:
            Training result with learned patterns
        """
        logger.info(f"🎓 Training scraper generator from documentation for {municipality}")

        # Load documentation knowledge
        if not self.docs_knowledge_file.exists():
            logger.error("❌ Documentation knowledge not found. Run markdown_doc_analyzer.py first")
            return {"success": False, "error": "No documentation knowledge"}

        with open(self.docs_knowledge_file) as f:
            docs_knowledge = json.load(f)

        # Load training examples (human recordings)
        training_examples = []
        if self.training_data_file.exists():
            with open(self.training_data_file) as f:
                training_data = json.load(f)
                training_examples = [ex for ex in training_data if ex.get('municipality') == municipality]

        # Load existing scraper (if available)
        existing_scraper = self._load_existing_scraper(municipality)

        # Build comprehensive training prompt
        training_prompt = self._build_training_prompt(
            municipality,
            docs_knowledge,
            training_examples,
            existing_scraper
        )

        logger.info(f"📝 Training prompt: {len(training_prompt)} characters")

        # Call Opus for learning
        response = await self._call_opus(training_prompt)

        # Parse learned scraper template
        scraper_template = self._parse_scraper_template(response)

        # Save trained model
        model_data = {
            "municipality": municipality,
            "scraper_template": scraper_template,
            "trained_from": {
                "documentation_docs": docs_knowledge.get("total_documents", 0),
                "code_examples": docs_knowledge.get("total_code_examples", 0),
                "recording_examples": len(training_examples)
            },
            "training_cost": cost_tracker.total_cost
        }

        model_file = self.trained_model_dir / f"{municipality}_scraper_template.json"
        with open(model_file, 'w') as f:
            json.dump(model_data, f, indent=2, default=str)

        logger.info(f"✅ Training complete! Saved to {model_file}")

        return {
            "success": True,
            "municipality": municipality,
            "model_file": str(model_file),
            "scraper_template": scraper_template
        }

    def _load_existing_scraper(self, municipality: str) -> Optional[str]:
        """Load existing generated scraper if available"""
        scraper_file = Path(f"generated_scrapers/{municipality}/{municipality}_scraper.py")

        if scraper_file.exists():
            with open(scraper_file) as f:
                return f.read()

        return None

    def _build_training_prompt(
        self,
        municipality: str,
        docs_knowledge: Dict,
        training_examples: List[Dict],
        existing_scraper: Optional[str]
    ) -> str:
        """Build comprehensive training prompt from all sources"""

        prompt = f"""You are training an AI scraper generator to create high-quality web scrapers for grievance submission forms.

**Municipality**: {municipality}

**Your Task**: Learn from the provided documentation, examples, and existing code to create an optimal scraper template.

---

## 📚 DOCUMENTATION KNOWLEDGE

Total documents analyzed: {docs_knowledge.get('total_documents', 0)}
Total code examples: {docs_knowledge.get('total_code_examples', 0)}

### Key Python Code Examples:

"""

        # Add relevant Python code examples
        python_examples = []
        for doc in docs_knowledge.get('documents', []):
            for ex in doc.get('code_examples', []):
                if ex.get('language') == 'python':
                    python_examples.append(ex)

        # Show first 10 most relevant examples
        for i, ex in enumerate(python_examples[:10], 1):
            if len(ex.get('code', '')) > 100:  # Only substantial examples
                prompt += f"\n**Example {i}**: {ex.get('description', 'Code example')}\n"
                prompt += f"```python\n{ex.get('code')[:500]}...\n```\n"

        prompt += "\n---\n\n"

        # Add training examples from recordings
        if training_examples:
            prompt += f"## 🎯 TRAINING DATA (Human Recordings)\n\n"
            prompt += f"Total examples: {len(training_examples)}\n\n"

            for i, ex in enumerate(training_examples[:3], 1):
                prompt += f"### Recording {i}:\n"
                prompt += f"- URL: {ex.get('url', 'N/A')}\n"
                prompt += f"- Fields discovered: {len(ex.get('fields_discovered', []))}\n"
                prompt += f"- Dropdowns: {len(ex.get('dropdown_options', {}))}\n"
                prompt += f"- Total actions: {ex.get('total_actions', 0)}\n\n"

                # Show field structure
                if ex.get('fields_discovered'):
                    prompt += "**Fields:**\n```json\n"
                    prompt += json.dumps(ex.get('fields_discovered')[:3], indent=2)
                    prompt += "\n```\n\n"

        prompt += "\n---\n\n"

        # Add existing scraper for reference
        if existing_scraper:
            prompt += f"## 🔧 EXISTING SCRAPER\n\n"
            prompt += f"Current implementation for {municipality}:\n\n"
            prompt += "```python\n"
            prompt += existing_scraper[:2000]  # First 2000 chars
            prompt += "\n... (truncated)\n```\n\n"
            prompt += "---\n\n"

        # Instructions
        prompt += """
## 📋 TASK: Create Optimal Scraper Template

Based on all the above knowledge, create a **production-ready scraper template** with:

### 1. **Class Structure**
- Proper async/await patterns
- Browser management (headless option)
- Error handling and logging
- Timeout configuration

### 2. **Form Filling Logic**
- Handle text inputs (name, email, phone, address)
- Handle dropdowns (including Select2, ASP.NET dropdowns)
- Handle textareas (remarks, description)
- Handle file uploads (if needed)

### 3. **ASP.NET Specific Handling**
- ViewState and EventValidation fields
- __doPostBack mechanism
- ContentPlaceHolder patterns
- Postback delays

### 4. **Success Detection**
- Check for success messages
- Extract tracking IDs
- Handle errors and validation messages

### 5. **Code Quality**
- Type hints
- Docstrings
- Logging statements
- Proper exception handling

**OUTPUT FORMAT**:

Return a JSON object with this structure:

```json
{
  "scraper_template": {
    "class_name": "ModernScraperClass",
    "imports": ["import statements"],
    "class_structure": "full class code",
    "key_methods": {
      "submit_grievance": "main submission method",
      "fill_field": "generic field filling",
      "select_dropdown": "dropdown handling",
      "extract_tracking_id": "success ID extraction"
    },
    "best_practices": ["list of practices applied"],
    "improvements_over_existing": ["what's better"]
  },
  "confidence_score": 0.0-1.0,
  "notes": "any important notes"
}
```

Generate the optimal scraper template now.
"""

        return prompt

    async def _call_opus(self, prompt: str) -> str:
        """Call Opus model for training"""
        logger.info("🤖 Calling Opus model...")

        response = ai_client.client.chat.completions.create(
            model=ai_client.models["powerful"],  # Use Opus
            messages=[{
                "role": "user",
                "content": prompt
            }],
            temperature=0.2,  # Low temperature for consistent code generation
            max_tokens=8000  # Larger for code generation
        )

        return response.choices[0].message.content

    def _parse_scraper_template(self, response: str) -> Dict[str, Any]:
        """Parse scraper template from Opus response"""
        try:
            # Extract JSON from response
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

            template = json.loads(json_text)
            return template

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse template: {e}")
            return {
                "scraper_template": {},
                "raw_response": response,
                "error": str(e)
            }

    async def generate_scraper_from_template(
        self,
        municipality: str,
        form_data: Dict[str, Any]
    ) -> str:
        """
        Generate actual scraper code using the trained template

        Args:
            municipality: Municipality name
            form_data: Form schema/discovery data

        Returns:
            Generated scraper code
        """
        logger.info(f"🔨 Generating scraper for {municipality} using trained template")

        # Load trained template
        model_file = self.trained_model_dir / f"{municipality}_scraper_template.json"

        if not model_file.exists():
            logger.warning(f"No trained template found for {municipality}, training now...")
            await self.train_from_documentation(municipality)

        with open(model_file) as f:
            model_data = json.load(f)

        template = model_data.get('scraper_template', {})

        # Build generation prompt
        prompt = f"""Using the trained scraper template, generate a complete, production-ready scraper for {municipality}.

**Trained Template**:
```json
{json.dumps(template, indent=2)}
```

**Form Data**:
```json
{json.dumps(form_data, indent=2)}
```

**Requirements**:
1. Use the template structure and best practices
2. Adapt to the specific form fields provided
3. Include all necessary imports
4. Add proper error handling and logging
5. Make it production-ready

**Output**: Complete Python scraper code (just the code, no markdown).
"""

        response = await self._call_opus(prompt)

        # Extract Python code
        if "```python" in response:
            code_start = response.find("```python") + 9
            code_end = response.find("```", code_start)
            scraper_code = response[code_start:code_end].strip()
        else:
            scraper_code = response

        return scraper_code


# CLI tool
async def main():
    import sys

    trainer = ScraperGeneratorTrainer()

    if len(sys.argv) > 1:
        municipality = sys.argv[1]
    else:
        municipality = "ranchi_smart"

    # Train from documentation
    result = await trainer.train_from_documentation(municipality)

    print("\n" + "="*70)
    print("SCRAPER GENERATOR TRAINING RESULT")
    print("="*70)
    print(f"Success: {result.get('success')}")
    print(f"Municipality: {result.get('municipality')}")
    print(f"Model file: {result.get('model_file')}")

    if result.get('scraper_template'):
        template = result['scraper_template']
        print(f"\nTemplate generated:")
        print(f"  - Confidence: {template.get('confidence_score', 'N/A')}")
        print(f"  - Best practices: {len(template.get('best_practices', []))}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
