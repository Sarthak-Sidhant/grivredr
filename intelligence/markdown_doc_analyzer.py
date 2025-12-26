"""
Markdown Documentation Analyzer - Extracts knowledge from markdown docs to train scraper generator
Reads PHASES documentation, code examples, and patterns
"""
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CodeExample:
    """Extracted code example from markdown"""
    language: str
    code: str
    description: str
    file_path: Optional[str] = None
    context: str = ""


@dataclass
class DocumentationKnowledge:
    """Knowledge extracted from documentation"""
    title: str
    file_path: str
    key_concepts: List[str]
    code_examples: List[CodeExample]
    patterns: List[Dict[str, str]]
    best_practices: List[str]
    architecture_notes: List[str]


class MarkdownDocAnalyzer:
    """
    Analyzes markdown documentation to extract training knowledge for scraper generator
    """

    def __init__(self, docs_dir: str = "."):
        self.docs_dir = Path(docs_dir)
        self.knowledge_base: List[DocumentationKnowledge] = []

    def analyze_document(self, doc_path: Path) -> DocumentationKnowledge:
        """
        Analyze a single markdown document

        Args:
            doc_path: Path to markdown file

        Returns:
            Extracted knowledge
        """
        logger.info(f"📖 Analyzing: {doc_path.name}")

        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract title
        title = self._extract_title(content, doc_path.name)

        # Extract code examples
        code_examples = self._extract_code_blocks(content)

        # Extract key concepts (headings)
        key_concepts = self._extract_headings(content)

        # Extract patterns
        patterns = self._extract_patterns(content)

        # Extract best practices
        best_practices = self._extract_best_practices(content)

        # Extract architecture notes
        architecture_notes = self._extract_architecture_notes(content)

        knowledge = DocumentationKnowledge(
            title=title,
            file_path=str(doc_path),
            key_concepts=key_concepts,
            code_examples=code_examples,
            patterns=patterns,
            best_practices=best_practices,
            architecture_notes=architecture_notes
        )

        logger.info(f"  ✓ Extracted: {len(code_examples)} code examples, {len(key_concepts)} concepts")

        return knowledge

    def _extract_title(self, content: str, filename: str) -> str:
        """Extract document title from first H1 or filename"""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return filename.replace('.md', '').replace('_', ' ').title()

    def _extract_code_blocks(self, content: str) -> List[CodeExample]:
        """Extract all code blocks with language and context"""
        code_examples = []

        # Pattern: ```language\ncode\n```
        pattern = r'```(\w+)?\n(.*?)\n```'
        matches = re.finditer(pattern, content, re.DOTALL)

        for match in matches:
            language = match.group(1) or 'text'
            code = match.group(2).strip()

            # Get context (text before code block)
            start_pos = match.start()
            context_start = max(0, start_pos - 200)
            context = content[context_start:start_pos].strip()

            # Extract description from context
            description = self._extract_description_from_context(context)

            code_examples.append(CodeExample(
                language=language,
                code=code,
                description=description,
                context=context[-100:] if len(context) > 100 else context
            ))

        return code_examples

    def _extract_description_from_context(self, context: str) -> str:
        """Extract description from surrounding text"""
        # Look for last sentence or line before code
        lines = context.split('\n')
        for line in reversed(lines):
            line = line.strip()
            if line and not line.startswith('#'):
                return line[:200]
        return ""

    def _extract_headings(self, content: str) -> List[str]:
        """Extract all headings as key concepts"""
        headings = []
        pattern = r'^#{1,6}\s+(.+)$'
        matches = re.finditer(pattern, content, re.MULTILINE)

        for match in matches:
            heading = match.group(1).strip()
            # Remove markdown links
            heading = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', heading)
            headings.append(heading)

        return headings

    def _extract_patterns(self, content: str) -> List[Dict[str, str]]:
        """Extract patterns mentioned in documentation"""
        patterns = []

        # Look for "Pattern:", "Example:", "Format:" sections
        pattern_markers = [
            r'Pattern:\s*(.+)',
            r'Example:\s*(.+)',
            r'Format:\s*(.+)',
            r'Structure:\s*(.+)'
        ]

        for marker in pattern_markers:
            matches = re.finditer(marker, content, re.IGNORECASE)
            for match in matches:
                pattern_text = match.group(1).strip()
                patterns.append({
                    'type': marker.split(':')[0].lower(),
                    'pattern': pattern_text[:500]
                })

        return patterns

    def _extract_best_practices(self, content: str) -> List[str]:
        """Extract best practices and recommendations"""
        practices = []

        # Look for bullet points under "Best Practices", "Recommendations", "Guidelines"
        sections = re.finditer(
            r'(?:Best Practices|Recommendations|Guidelines|Important):\s*\n((?:[-*]\s+.+\n?)+)',
            content,
            re.IGNORECASE | re.MULTILINE
        )

        for section in sections:
            items = re.findall(r'[-*]\s+(.+)', section.group(1))
            practices.extend(items)

        return practices

    def _extract_architecture_notes(self, content: str) -> List[str]:
        """Extract architecture and implementation notes"""
        notes = []

        # Look for sections mentioning architecture, implementation, design
        arch_sections = re.finditer(
            r'(?:Architecture|Implementation|Design|Structure).*?\n((?:.+\n?){1,10})',
            content,
            re.IGNORECASE
        )

        for section in arch_sections:
            note = section.group(1).strip()
            if len(note) > 50:
                notes.append(note[:500])

        return notes

    def analyze_all_docs(self, pattern: str = "*.md") -> List[DocumentationKnowledge]:
        """
        Analyze all markdown documents matching pattern

        Args:
            pattern: Glob pattern for markdown files

        Returns:
            List of extracted knowledge
        """
        doc_files = list(self.docs_dir.glob(pattern))

        # Also check root directory
        if self.docs_dir != Path('.'):
            doc_files.extend(Path('.').glob(pattern))

        # Remove duplicates
        doc_files = list(set(doc_files))

        logger.info(f"📚 Found {len(doc_files)} markdown documents")

        for doc_file in doc_files:
            try:
                knowledge = self.analyze_document(doc_file)
                self.knowledge_base.append(knowledge)
            except Exception as e:
                logger.error(f"❌ Failed to analyze {doc_file.name}: {e}")

        logger.info(f"✅ Analyzed {len(self.knowledge_base)} documents")
        return self.knowledge_base

    def get_code_examples_by_language(self, language: str) -> List[CodeExample]:
        """Get all code examples for a specific language"""
        examples = []
        for doc in self.knowledge_base:
            examples.extend([ex for ex in doc.code_examples if ex.language == language])
        return examples

    def save_knowledge_base(self, output_path: str = "intelligence/documentation_knowledge.json"):
        """Save extracted knowledge to JSON"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "total_documents": len(self.knowledge_base),
            "total_code_examples": sum(len(doc.code_examples) for doc in self.knowledge_base),
            "documents": [
                {
                    "title": doc.title,
                    "file_path": doc.file_path,
                    "key_concepts": doc.key_concepts,
                    "code_examples": [
                        {
                            "language": ex.language,
                            "code": ex.code,
                            "description": ex.description,
                            "context": ex.context
                        }
                        for ex in doc.code_examples
                    ],
                    "patterns": doc.patterns,
                    "best_practices": doc.best_practices,
                    "architecture_notes": doc.architecture_notes
                }
                for doc in self.knowledge_base
            ]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        logger.info(f"💾 Saved knowledge base: {output_file}")
        return output_file

    def generate_training_summary(self) -> Dict[str, Any]:
        """Generate summary of extracted knowledge"""
        if not self.knowledge_base:
            return {"error": "No knowledge base loaded"}

        total_code_examples = sum(len(doc.code_examples) for doc in self.knowledge_base)
        total_patterns = sum(len(doc.patterns) for doc in self.knowledge_base)
        total_practices = sum(len(doc.best_practices) for doc in self.knowledge_base)

        languages = {}
        for doc in self.knowledge_base:
            for ex in doc.code_examples:
                languages[ex.language] = languages.get(ex.language, 0) + 1

        return {
            "total_documents": len(self.knowledge_base),
            "total_code_examples": total_code_examples,
            "total_patterns": total_patterns,
            "total_best_practices": total_practices,
            "languages": languages,
            "document_titles": [doc.title for doc in self.knowledge_base]
        }


# CLI tool
if __name__ == "__main__":
    import sys

    analyzer = MarkdownDocAnalyzer()

    if len(sys.argv) > 1:
        # Analyze specific document
        doc_path = Path(sys.argv[1])
        knowledge = analyzer.analyze_document(doc_path)
        print(f"\n✅ Analyzed: {knowledge.title}")
        print(f"   Code examples: {len(knowledge.code_examples)}")
        print(f"   Key concepts: {len(knowledge.key_concepts)}")
    else:
        # Analyze all markdown docs
        analyzer.analyze_all_docs()

        # Save knowledge base
        output_file = analyzer.save_knowledge_base()

        # Print summary
        summary = analyzer.generate_training_summary()
        print("\n" + "="*70)
        print("DOCUMENTATION KNOWLEDGE SUMMARY")
        print("="*70)
        for key, value in summary.items():
            print(f"{key}: {value}")
