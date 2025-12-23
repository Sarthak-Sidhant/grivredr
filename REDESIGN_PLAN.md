# Grivredr Redesign - Agentic Architecture

## 🎯 Core Problem with Current Approach

The initial implementation was a **one-shot code generator**. It won't handle:
- ❌ Dynamic dropdowns populated by JavaScript
- ❌ Required fields discovered only on validation
- ❌ Multi-step forms with state management
- ❌ AJAX submissions and complex form logic
- ❌ Learning from failures and self-improvement

## 🤖 New Approach: True Agentic System

### Design Principles

1. **Iterative Discovery** - Agent explores forms through trial-and-error
2. **Human-in-the-Loop Training** - Learns from corrections
3. **Test-Driven** - Validates each approach before committing
4. **Self-Reflecting** - Analyzes failures and adapts strategy
5. **Knowledge Building** - Accumulates learned patterns

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLASK DASHBOARD                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ Training │  │ Monitor  │  │  Cost    │  │ Scraper  │       │
│  │ Sessions │  │ Agents   │  │ Tracking │  │ Library  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               ORCHESTRATOR (Main Agent)                          │
│  • Spawns specialized sub-agents                                 │
│  • Coordinates training sessions                                 │
│  • Manages feedback loops                                        │
└───────────────────────────────────────────────────────────────┬─┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ FORM AGENT   │    │ TEST AGENT   │    │ JS ANALYZER  │
│              │    │              │    │              │
│ • Crawl form │    │ • Try submit │    │ • Analyze JS │
│ • Discover   │    │ • Catch errs │    │ • Find AJAX  │
│ • Map fields │    │ • Validate   │    │ • Track state│
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
                ┌─────────────────────┐
                │  REFLECTION LOOP    │
                │  • What worked?     │
                │  • What failed?     │
                │  • Try new approach │
                │  • Ask human?       │
                └─────────┬───────────┘
                          │
                          ▼
                ┌─────────────────────┐
                │ KNOWLEDGE BASE      │
                │ • Field patterns    │
                │ • Validation rules  │
                │ • JS patterns       │
                │ • Success strategies│
                └─────────────────────┘
```

## 📋 Detailed Component Design

### 1. Form Discovery Agent (Agentic)

**Capabilities:**
- **Visual analysis** with Claude Vision
- **DOM exploration** - recursive field discovery
- **JavaScript monitoring** - track dynamic changes
- **Validation detection** - submit empty form to find required fields
- **Dropdown population** - trigger events to populate options
- **Multi-step detection** - identify wizard patterns

**Workflow:**
```python
class FormDiscoveryAgent:
    async def explore_form(self, url):
        # Phase 1: Static analysis
        static_fields = await self.analyze_static_html()

        # Phase 2: Dynamic interaction
        for field in static_fields:
            await self.trigger_events(field)  # Populate dropdowns
            await self.observe_changes()

        # Phase 3: Validation discovery
        validation_errors = await self.submit_empty_form()

        # Phase 4: JavaScript analysis
        js_logic = await self.analyze_form_scripts()

        # Phase 5: Reflection
        if not self.is_complete():
            await self.ask_claude_for_strategy()
            return await self.explore_form(url)  # Retry with new strategy

        return FormSchema(fields, validation, js_logic)
```

### 2. Test-Driven Validation Agent

**Capabilities:**
- Test each field type independently
- Validate required vs optional
- Test dropdown selections
- Test file uploads
- Verify form submission success

**Workflow:**
```python
class ValidationAgent:
    async def validate_form_schema(self, schema):
        test_results = []

        # Test 1: Required fields
        result = await self.test_with_missing_required()
        if result.failed:
            await self.refine_schema(result.errors)

        # Test 2: Field types
        result = await self.test_field_types()

        # Test 3: Submission
        result = await self.test_full_submission()

        # If any test fails, reflect and retry
        if not all(test_results):
            strategy = await self.ask_claude_how_to_fix(test_results)
            return await self.validate_form_schema(updated_schema)

        return SuccessfulSchema(schema)
```

### 3. Human-in-the-Loop Training

**Capabilities:**
- Show agent's understanding to human
- Collect corrections
- Store correction patterns
- Apply patterns to similar forms

**Workflow:**
```python
class TrainingSession:
    async def train_on_form(self, url):
        # Agent's attempt
        discovered = await form_agent.explore_form(url)

        # Show to human via Flask UI
        human_feedback = await self.request_human_review(discovered)

        if human_feedback.has_corrections:
            # Learn from corrections
            patterns = self.extract_patterns(human_feedback)
            await self.knowledge_base.store(patterns)

            # Retry with learned patterns
            discovered = await form_agent.explore_form(url, hints=patterns)

        # Test until it works
        while not await test_agent.validate(discovered):
            strategy = await self.ask_claude_what_to_try_next()
            discovered = await form_agent.apply_strategy(strategy)

        # Generate scraper only after validation
        scraper = await self.generate_validated_scraper(discovered)
        return scraper
```

### 4. JavaScript Analyzer Agent

**Capabilities:**
- Detect AJAX form submissions
- Understand form state management
- Identify dynamic field population
- Reverse-engineer validation logic

**Workflow:**
```python
class JavaScriptAnalyzer:
    async def analyze_form_js(self, page):
        # Inject monitoring code
        await page.add_script_tag(content="""
            window._formEvents = [];
            // Monitor all form-related JS
        """)

        # Interact with form
        await self.fill_and_submit()

        # Collect JS execution traces
        js_events = await page.evaluate("window._formEvents")

        # Ask Claude to understand the logic
        explanation = await claude.analyze_js_logic(js_events)

        return JSFormLogic(events, explanation)
```

### 5. Cost Tracker

**Tracks:**
- Claude API calls (by model/type)
- Token usage
- Training cost per municipality
- Execution cost per submission
- ROI metrics

### 6. Flask Dashboard

**Features:**
- **Training UI** - Guide agent through form
- **Live Monitoring** - Watch agents work
- **Cost Dashboard** - Real-time cost tracking
- **Scraper Library** - View/edit generated scrapers
- **Test Suite** - Run validation tests
- **Knowledge Base** - View learned patterns

## 🔄 Training Flow Example

```
1. Human: "Learn smartranchi.in complaint form"
   ↓
2. Form Agent: Explores form
   - Finds: name, mobile, email, address, remarks
   - Finds: Select Type dropdown (empty initially)
   - Finds: Tenament No, Contact Person fields
   - Takes screenshot
   ↓
3. Form Agent: "I found these fields, but dropdown is empty"
   ↓
4. Form Agent: Clicks dropdown, observes options populate
   - Discovers: Options loaded via AJAX
   - Captures: Network request to get options
   ↓
5. Test Agent: Submits test form
   - Error: "Mobile number required"
   - Error: "Please select file type"
   ↓
6. Form Agent: Updates schema with required fields
   ↓
7. Flask UI: Shows agent's understanding to human
   Human: "You missed 'Contact Person Name' field"
   ↓
8. Form Agent: Re-explores, finds missed field
   Knowledge Base: Stores pattern "Contact fields often in pairs"
   ↓
9. Test Agent: Tries submission again
   - Success! Captures tracking ID
   ↓
10. Generator: Creates scraper code with all learned logic
    ↓
11. Test Agent: Runs scraper 3 times to verify
    - All successful
    ↓
12. System: Marks scraper as "validated" and saves
```

## 🧪 Test-Driven Development

### Test Hierarchy

```
tests/
├── unit/
│   ├── test_form_discovery.py
│   ├── test_field_detection.py
│   ├── test_js_analyzer.py
│   └── test_validation.py
├── integration/
│   ├── test_training_flow.py
│   ├── test_agent_coordination.py
│   └── test_scraper_generation.py
└── e2e/
    ├── test_smart_ranchi.py
    ├── test_jharkhand_portal.py
    └── test_rmc_website.py
```

### Testing Strategy

```python
# TDD Example
def test_discover_required_fields():
    """Agent should find all required fields through validation errors"""
    agent = FormDiscoveryAgent()

    # Test: Submit empty form
    errors = await agent.submit_empty_form(SMART_RANCHI_URL)

    # Assert: Should catch required fields
    assert "Mobile number" in errors
    assert "Email" in errors

    # Agent should update schema
    schema = agent.schema
    assert schema.get_field("mobile").required == True

def test_retry_on_failure():
    """Agent should retry with new strategy if test fails"""
    agent = FormDiscoveryAgent()

    with patch.object(agent, 'ask_claude_for_strategy') as mock:
        mock.return_value = Strategy("Try clicking dropdown first")

        # First attempt fails
        schema = await agent.explore_form(url)

        # Should have called Claude for strategy
        assert mock.called

        # Should have retried
        assert agent.attempt_count > 1
```

## 💰 Cost Estimation

### Training Phase (Per Municipality)

| Task | API Calls | Est. Cost |
|------|-----------|-----------|
| Initial exploration | 2-3 Claude Vision | $0.06 |
| Field discovery iterations | 5-10 Sonnet | $0.15 |
| JS analysis | 2-3 Opus | $0.30 |
| Test validation | 3-5 Haiku | $0.02 |
| Scraper generation | 1 Opus | $0.10 |
| **Total per website** | | **~$0.63** |

### With Human Training (First Time)
| Phase | Cost |
|-------|------|
| Agent exploration | $0.63 |
| Human corrections (2-3 rounds) | $0.30 |
| Knowledge base building | $0.10 |
| **Total first website** | **~$1.03** |

### Subsequent Similar Forms
- Agent uses learned patterns: **~$0.20**
- Knowledge compounds over time

### Execution (After Training)
- **$0.00** - No AI calls needed

## 🎯 Success Metrics

- **Field Discovery Rate**: % of fields correctly identified
- **Validation Success Rate**: % of submissions that work first try
- **Training Efficiency**: Cost reduction over time
- **Human Intervention Rate**: How often human help needed
- **Scraper Reliability**: % uptime after deployment

## 📅 Implementation Plan

### Phase 1: Foundation (Week 1)
- [x] Basic architecture design
- [ ] Form discovery agent core
- [ ] Test agent framework
- [ ] Flask dashboard skeleton
- [ ] Cost tracking

### Phase 2: Agentic Intelligence (Week 2)
- [ ] Reflection loops
- [ ] Human-in-the-loop UI
- [ ] Knowledge base
- [ ] JS analyzer
- [ ] TDD framework

### Phase 3: Training & Validation (Week 3)
- [ ] Train on Smart Ranchi
- [ ] Train on Jharkhand portal
- [ ] Train on RMC website
- [ ] Validate reliability
- [ ] Performance optimization

### Phase 4: Production (Week 4)
- [ ] API integration
- [ ] Monitoring & alerting
- [ ] Documentation
- [ ] Deployment

## 🔧 Technology Choices

### Why These?
- **Playwright** - Best browser automation, supports stealth
- **Claude Sonnet/Opus** - Best reasoning for agentic tasks
- **Flask** - Lightweight, easy admin dashboard
- **pytest** - Industry standard TDD
- **SQLite → PostgreSQL** - Start simple, scale later
- **Redis** - For agent state and caching

## 🎓 Learning from Screenshot

Looking at the Smart Ranchi form, the agent needs to:

1. ✅ Detect "Problem *" dropdown (required, asterisk)
2. ✅ Understand it's populated by "Select Type" choice
3. ✅ Find "Mobile No *" (required, with validation)
4. ✅ Discover "Contact Person No *" and "Contact Person Name *"
5. ✅ Handle "Tenament No" (optional)
6. ✅ Handle file upload with "Select File Type" dependency
7. ✅ Test "Register Complaint" button submission
8. ✅ Verify success by checking for tracking ID

**Old approach would miss**: The dropdown dependencies, validation logic, and the distinction between required/optional fields.

**New approach**: Iteratively discovers through interaction and testing.

---

**This is the proper architecture. Shall I now implement it?**
