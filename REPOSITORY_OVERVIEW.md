# Grivredr Repository Overview

## 📂 Root Directory Files

### Documentation (Read First!)
- **README.md** - Main project documentation (start here)
- **GETTING_STARTED.md** - Quick start tutorial
- **PROJECT_STRUCTURE.md** - Codebase organization guide
- **CONTRIBUTING.md** - How to contribute
- **CLAUDE.md** - Guide for Claude Code assistant
- **LICENSE** - MIT License
- **PUBLICATION_READY_SUMMARY.md** - Publication preparation summary
- **PUBLICATION_CHECKLIST.md** - Pre-publication checklist

### Setup & Configuration
- **quickstart.sh** - One-command automated setup
- **verify_setup.py** - Verify installation
- **requirements.txt** - Python dependencies
- **pyproject.toml** - Modern Python project config
- **.env.example** - Environment variables template
- **.gitignore** - Git ignore rules

## 🏗️ Core Directories

### agents/
**The AI Agent System** - 4-phase training pipeline

Key files:
- `orchestrator.py` - Coordinates all agents
- `form_discovery_agent.py` - Phase 1: Form exploration
- `js_analyzer_agent.py` - Phase 2: JavaScript analysis
- `test_agent.py` - Phase 3: Validation testing
- `code_generator_agent.py` - Phase 4: Code generation
- `hybrid_discovery_strategy.py` - Playwright + Browser Use AI
- `base_agent.py` - Base class for all agents

### cli/
**Command-line Interfaces**

Key files:
- `train_cli.py` - Main training CLI (primary entry point)
- `record_cli.py` - Human recording mode
- `train_from_recording.py` - Generate from recording

### config/
**Configuration & AI Client**

Key files:
- `ai_client.py` - Anthropic SDK wrapper with MegaLLM
- `healing_prompts.py` - Self-healing prompt templates

### knowledge/
**Pattern Library** - Learns from successful scrapers

Key files:
- `pattern_library.py` - SQLite + vector store
- `code_templates.py` - UI framework templates
- `framework_detector.py` - Detect UI frameworks

### utils/
**Utility Modules**

Key files:
- `scraper_validator.py` - Validates generated scrapers
- `js_runtime_monitor.py` - Monitors JavaScript behavior
- `ai_cache.py` - AI response caching
- `portal_manager.py` - Portal configuration

### tests/
**Test Suite**

Structure:
- `unit/` - Unit tests
- `integration/` - Integration tests
- `e2e/` - End-to-end tests
- `test_*_live.py` - Live scraper tests

### docs/
**Additional Documentation**

Key files:
- `ARCHITECTURE.md` - System design
- `STATUS.md` - Current features
- `QUICK_START.md` - Quick start guide
- `USAGE_GUIDE.md` - Usage documentation

## 🗂️ Other Directories

### legacy/
Deprecated code (kept for reference only)
- Old learner, generator, executor implementations

### intelligence/
Experimental/advanced features
- LangChain integration
- Form clustering
- Smart recommenders

### batch/
Batch processing utilities

### scripts/
Helper scripts
- `check_discovery_results.py` - Debug discovery
- `validate_system.py` - System validation

## 🚫 Gitignored Directories

These are created during usage but not committed:

- **.venv/** - Virtual environment
- **.archive/** - Archived temp files
- **outputs/** - Generated scrapers and screenshots
- **data/** - Training sessions and recordings
- **cache/** - Runtime cache
- **portals/** - Portal configurations (runtime)
- **scrapers/** - Scrapers (runtime)
- **screenshots/** - Screenshots (runtime)

## 🎯 Quick Start

```bash
# 1. Setup
./quickstart.sh

# 2. Train a portal
python cli/train_cli.py abua_sathi --district ranchi

# 3. Test it
python tests/test_abua_sathi_live.py
```

## 📚 Documentation Hierarchy

1. **README.md** ← Start here
2. **GETTING_STARTED.md** ← Follow the tutorial
3. **PROJECT_STRUCTURE.md** ← Understand the codebase
4. **docs/ARCHITECTURE.md** ← Deep dive into design
5. **CONTRIBUTING.md** ← Ready to contribute
6. **CLAUDE.md** ← Using Claude Code assistant

## 🔧 Development Workflow

1. Read **CONTRIBUTING.md**
2. Setup dev environment: `./quickstart.sh`
3. Create branch: `git checkout -b feature/your-feature`
4. Make changes
5. Run tests: `pytest`
6. Format code: `black .`
7. Commit and push
8. Create Pull Request

## 📞 Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Documentation**: See docs/ directory

---

**Built with ❤️ using Claude AI, Playwright, and Python**
