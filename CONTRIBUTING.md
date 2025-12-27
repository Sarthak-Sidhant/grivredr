# Contributing to Grivredr

Thank you for your interest in contributing to Grivredr! This document provides guidelines and instructions for contributing.

## 🎯 Ways to Contribute

### 1. Testing on New Portals
The most valuable contribution is testing Grivredr on new government portals:
- Train on portals in your region/country
- Report success rates and any issues
- Share portal URLs and training results
- Help build the pattern library

### 2. Code Contributions
- Fix bugs and issues
- Improve agent intelligence
- Add new features
- Optimize performance
- Enhance documentation

### 3. Documentation
- Improve existing docs
- Add examples and tutorials
- Translate documentation
- Write blog posts about usage

### 4. Bug Reports
- Report issues you encounter
- Provide reproduction steps
- Share training session logs
- Include screenshots

## 🚀 Getting Started

### Setup Development Environment

```bash
# 1. Fork and clone the repository
git clone https://github.com/yourusername/grivredr.git
cd grivredr

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies (including dev dependencies)
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov black flake8

# 4. Install Playwright browsers
python -m playwright install chromium

# 5. Setup environment
cp .env.example .env
# Edit .env and add your API key

# 6. Verify setup
python verify_setup.py
```

### Run Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Run with coverage
pytest --cov=agents --cov=utils --cov=knowledge

# Run specific test file
pytest tests/unit/test_scraper_validator.py -v
```

## 📝 Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Make Changes

- Write clean, readable code
- Follow existing code style
- Add docstrings to functions/classes
- Update documentation if needed

### 3. Test Your Changes

```bash
# Run tests
pytest

# Format code
black agents/ utils/ knowledge/ cli/

# Check code quality
flake8 agents/ utils/ knowledge/ cli/
```

### 4. Commit Changes

Use clear, descriptive commit messages:

```bash
git add .
git commit -m "feat: add support for multi-page forms"
# or
git commit -m "fix: handle timeout in cascading dropdowns"
```

Commit message prefixes:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Adding or updating tests
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear description of changes
- Reference to any related issues
- Screenshots if UI-related
- Test results

## 🎨 Code Style Guidelines

### Python Style

We follow PEP 8 with some modifications:

```python
# Use descriptive variable names
form_schema = discover_form(url)  # Good
fs = df(u)  # Bad

# Add docstrings to functions/classes
async def train_portal(url: str, district: str) -> Dict[str, Any]:
    """
    Train AI to scrape a government portal.

    Args:
        url: Portal URL to train on
        district: District name for organization

    Returns:
        Training result with scraper path and metrics
    """
    pass

# Use type hints
def validate_scraper(code: str, test_mode: bool = True) -> ValidationResult:
    pass

# Keep functions focused and small
# Max ~50 lines per function ideal
```

### File Organization

```python
# Standard import order:
# 1. Standard library
# 2. Third-party packages
# 3. Local imports

import asyncio
import json
from typing import Dict, Any

from playwright.async_api import async_playwright

from agents.base_agent import BaseAgent
from config.ai_client import ai_client
```

### Agent Development

When creating new agents:

```python
from agents.base_agent import BaseAgent

class NewAgent(BaseAgent):
    """Brief description of what this agent does"""

    def __init__(self, **kwargs):
        super().__init__(name="NewAgent", max_attempts=3)
        # Initialize agent-specific attributes

    async def _execute_attempt(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's main logic.

        Args:
            task: Task dictionary with required parameters

        Returns:
            Result dictionary with success status and data
        """
        # Implementation here
        return {
            "success": True,
            "data": result_data
        }
```

## 🧪 Testing Guidelines

### Writing Tests

```python
import pytest
from agents.form_discovery_agent import FormDiscoveryAgent

@pytest.mark.asyncio
async def test_form_discovery_simple_form():
    """Test form discovery on a simple HTML form"""
    agent = FormDiscoveryAgent(headless=True)

    result = await agent.execute({
        "url": "https://example.com/form",
        "municipality": "test"
    })

    assert result["success"] is True
    assert len(result["schema"]["fields"]) > 0

@pytest.mark.asyncio
async def test_form_discovery_select2_dropdowns():
    """Test detection of Select2 dropdowns"""
    # Test implementation
    pass
```

### Test Categories

- **Unit tests** (`tests/unit/`) - Test individual components in isolation
- **Integration tests** (`tests/integration/`) - Test agent interactions
- **E2E tests** (`tests/e2e/`) - Test complete workflows
- **Live tests** - Test against real portals (run manually)

## 📊 Contribution Areas

### High Priority

1. **Portal Coverage**
   - Test on portals from different countries
   - Document success rates and challenges
   - Add portal configurations to known URLs

2. **Pattern Detection**
   - Improve Select2/Chosen.js detection
   - Better cascading dropdown handling
   - AJAX pattern recognition

3. **Self-Healing**
   - Improve code validation logic
   - Better error diagnosis
   - Smarter code fixing strategies

### Medium Priority

1. **Performance**
   - Optimize AI calls (reduce tokens)
   - Faster form discovery
   - Parallel agent execution

2. **Documentation**
   - More examples
   - Video tutorials
   - Architecture diagrams

3. **Testing**
   - Increase test coverage
   - Add more integration tests
   - Mock external dependencies

### Lower Priority

1. **UI/Dashboard**
   - Web interface for training
   - Progress monitoring
   - Visual form editor

2. **Advanced Features**
   - Multi-language support
   - Custom JS execution
   - Plugin system

## 🐛 Bug Reports

When reporting bugs, include:

1. **Environment**
   - Python version
   - Operating system
   - Grivredr version/commit

2. **Steps to Reproduce**
   - Exact commands run
   - Portal URL (if public)
   - Configuration used

3. **Expected vs Actual Behavior**
   - What you expected to happen
   - What actually happened

4. **Logs and Artifacts**
   - Training session JSON
   - Error messages
   - Screenshots if relevant

5. **Additional Context**
   - Have you tried with --browser-use-first?
   - Does it work with --headless=false?
   - Any custom modifications?

## 🎯 Feature Requests

When requesting features:

1. **Use Case** - Describe the problem you're trying to solve
2. **Proposed Solution** - How would you like it to work?
3. **Alternatives** - What other approaches have you considered?
4. **Portal Examples** - Which portals need this feature?

## 📜 Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Assume good intentions
- Help others learn

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or inflammatory comments
- Publishing others' private information
- Unethical use of the tool

## 🏆 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Given credit in documentation

Significant contributions may earn:
- Maintainer status
- Special recognition badge
- Featured in project showcase

## 📞 Questions?

- **General questions**: [GitHub Discussions](https://github.com/yourusername/grivredr/discussions)
- **Bug reports**: [GitHub Issues](https://github.com/yourusername/grivredr/issues)
- **Security issues**: Email security@example.com

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to Grivredr! Together we can make government portals more accessible.**
