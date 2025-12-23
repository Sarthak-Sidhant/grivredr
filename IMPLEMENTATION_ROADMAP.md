# Grivredr - Complete Implementation Roadmap

## 🎯 Project Vision

**Grivredr** is an AI-powered system that learns how to submit grievances to municipal websites through **iterative exploration and human-guided training**, then generates reliable, reusable scrapers that work without ongoing AI costs.

### The Problem We're Solving

Municipal grievance websites are:
- ❌ Different for every city (no standard API)
- ❌ Complex (multi-step forms, cascading dropdowns, validation)
- ❌ Dynamic (JavaScript-heavy, AJAX submissions)
- ❌ Undocumented (no API documentation)

Traditional scrapers are:
- ❌ Brittle (break when sites change)
- ❌ Manual (developer writes code for each site)
- ❌ Expensive to maintain

**Our Solution: Self-Learning AI Agents**

Instead of writing scrapers manually, we build agents that:
1. **Explore** forms like a human would
2. **Test** different approaches iteratively
3. **Reflect** on failures and adapt strategy
4. **Learn** from human corrections
5. **Generate** production-ready code
6. **Validate** through automated testing

---

## 🏗️ System Architecture (Detailed)

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLASK DASHBOARD (Port 5000)                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │
│  │  Training  │  │   Live     │  │   Scraper  │  │   Cost    │ │
│  │  Sessions  │  │ Monitoring │  │  Library   │  │ Dashboard │ │
│  │            │  │            │  │            │  │           │ │
│  │ • Guide    │  │ • Agent    │  │ • View all │  │ • Per-muni│ │
│  │   agent    │  │   status   │  │ • Test     │  │ • Per-    │ │
│  │ • Correct  │  │ • Actions  │  │ • Edit     │  │   agent   │ │
│  │   errors   │  │ • Costs    │  │ • Deploy   │  │ • Live $  │ │
│  └────────────┘  └────────────┘  └────────────┘  └───────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                            │
│  • Manages training sessions                                     │
│  • Coordinates sub-agents                                        │
│  • Handles human-in-loop workflow                                │
│  • Persists knowledge base                                       │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├──────────────┬──────────────┬──────────────┐
             ▼              ▼              ▼              ▼
   ┌─────────────────┐ ┌────────────┐ ┌─────────────┐ ┌──────────────┐
   │ FormDiscovery   │ │ TestAgent  │ │ JSAnalyzer  │ │ CodeGen      │
   │ Agent           │ │            │ │ Agent       │ │ Agent        │
   │                 │ │            │ │             │ │              │
   │ • Crawl form    │ │ • Submit   │ │ • Analyze   │ │ • Generate   │
   │ • Find fields   │ │   tests    │ │   JS logic  │ │   Python     │
   │ • Map types     │ │ • Validate │ │ • Detect    │ │ • Add error  │
   │ • Detect deps   │ │ • Capture  │ │   AJAX      │ │   handling   │
   │ • Screenshot    │ │   errors   │ │ • Extract   │ │ • Test it    │
   │ • Claude Vision │ │ • Retry    │ │   patterns  │ │              │
   └─────────────────┘ └────────────┘ └─────────────┘ └──────────────┘
             │              │              │              │
             └──────────────┴──────────────┴──────────────┘
                            │
                            ▼
                  ┌────────────────────┐
                  │  KNOWLEDGE BASE    │
                  │  (SQLite/JSON)     │
                  │                    │
                  │ • Field patterns   │
                  │ • Validation rules │
                  │ • JS patterns      │
                  │ • Success stories  │
                  │ • Human feedback   │
                  └────────────────────┘
                            │
                            ▼
                  ┌────────────────────┐
                  │ GENERATED SCRAPERS │
                  │ (Python files)     │
                  │                    │
                  │ • Validated code   │
                  │ • Test suite       │
                  │ • Documentation    │
                  └────────────────────┘
```

---

## 📦 Complete Component Breakdown

### 1. Core Agent Framework

**File**: `agents/base_agent.py` ✅ (DONE)

**Features**:
- Abstract base class for all agents
- Built-in reflection loop (retry 3x, then ask human)
- Cost tracking with real-time updates
- Action recording for debugging
- Status callbacks for Flask UI
- Strategy planning with Claude

**Usage**:
```python
class MyAgent(BaseAgent):
    async def _execute_attempt(self, task):
        # Your logic here
        return {"success": True, "data": "..."}

agent = MyAgent("MyAgent", max_attempts=3)
result = await agent.execute(task)
```

---

### 2. Form Discovery Agent

**File**: `agents/form_discovery_agent.py`

**Purpose**: Intelligently explore and understand grievance forms

**Capabilities**:
1. **Visual Analysis** (Claude Vision)
   - Take full-page screenshot
   - Identify form sections, fields, buttons
   - Detect required field markers (*, "Required", red text)

2. **DOM Exploration**
   - Recursive field discovery
   - Find hidden/lazy-loaded fields
   - Detect input types (text, dropdown, file, etc.)

3. **Interactive Discovery**
   - Click dropdowns to see options
   - Trigger events to populate dynamic fields
   - Detect cascading dependencies (Type → Problem)

4. **Validation Discovery**
   - Submit empty form
   - Capture validation messages
   - Identify required vs optional fields

5. **Reflection**
   - "Did I find all fields?"
   - "Are there fields below the fold?"
   - "Are there multi-step wizards?"

**Output**:
```python
FormSchema(
    url="https://smartranchi.in/...",
    fields=[
        Field(
            name="select_type",
            label="Select Type",
            type="dropdown",
            required=True,
            options=["Electrical", "Water", ...],
            validation="required"
        ),
        Field(
            name="problem",
            label="Problem",
            type="dropdown",
            required=True,
            depends_on="select_type",  # Cascading!
            validation="required"
        ),
        # ... more fields
    ],
    submit_button=Button(selector="button.submit", text="Register Complaint"),
    submission_type="ajax",  # vs "form_post"
    success_indicator={"type": "text", "contains": "Complaint registered"}
)
```

---

### 3. Test Validation Agent

**File**: `agents/test_agent.py`

**Purpose**: Validate discovered form schema through actual testing

**Test Suite**:

1. **Test Empty Submission**
   ```python
   async def test_empty_form():
       result = await submit_form({})
       assert "Mobile No is required" in result.errors
       assert "Select Type is required" in result.errors
   ```

2. **Test Required Fields Only**
   ```python
   async def test_minimal_valid():
       result = await submit_form({
           "mobile": "9876543210",
           "select_type": "Electrical",
           "problem": "Street light"
       })
       assert result.success or has_new_errors(result)
   ```

3. **Test Field Types**
   ```python
   async def test_mobile_validation():
       result = await submit_form({"mobile": "123"})  # Invalid
       assert "invalid mobile" in result.errors.lower()
   ```

4. **Test Cascading Dropdowns**
   ```python
   async def test_problem_depends_on_type():
       # Select type first
       await select_dropdown("select_type", "Electrical")
       await wait_for_update()

       # Check if problem dropdown populated
       options = await get_dropdown_options("problem")
       assert len(options) > 0
   ```

5. **Test Full Submission**
   ```python
   async def test_complete_submission():
       result = await submit_form(complete_test_data)
       assert result.success
       assert result.tracking_id is not None
   ```

**Output**:
```python
TestResults(
    total_tests=8,
    passed=7,
    failed=1,
    failures=[
        TestFailure(
            test="test_file_upload",
            error="File type dropdown not populated",
            suggestion="May need to trigger change event on previous field"
        )
    ],
    validated_schema=FormSchema(...),  # Updated based on tests
    confidence_score=0.875  # 7/8 tests passed
)
```

---

### 4. JavaScript Analyzer Agent

**File**: `agents/js_analyzer_agent.py`

**Purpose**: Understand JavaScript form logic

**Analysis Steps**:

1. **Inject Monitoring Code**
   ```javascript
   // Injected into page
   window._grivredr_monitor = {
       xhr_calls: [],
       form_events: [],
       validations: []
   };

   // Hook into XMLHttpRequest
   const oldXHR = window.XMLHttpRequest;
   window.XMLHttpRequest = function() {
       const xhr = new oldXHR();
       // Track all AJAX calls
   };
   ```

2. **Detect Form Submission Method**
   - Standard form POST?
   - AJAX with fetch()?
   - jQuery $.ajax()?
   - Custom framework?

3. **Extract Validation Logic**
   ```javascript
   // Find validation functions
   if (form.onsubmit) {
       // Analyze onsubmit handler
   }

   // Check for validation libraries
   if (window.jQuery && $.validator) {
       // jQuery Validation plugin
   }
   ```

4. **Identify Dynamic Behaviors**
   - Which fields trigger onChange events?
   - Which dropdowns populate others?
   - Are there AJAX calls to fetch data?

5. **Claude Analysis**
   ```python
   # Send captured JS events to Claude
   prompt = """Analyze this JavaScript form behavior:

   XHR Calls: {xhr_calls}
   Form Events: {form_events}

   Explain:
   1. How is this form submitted?
   2. What validation happens client-side?
   3. What can be replicated in Python vs needs browser?
   """
   ```

**Output**:
```python
JSAnalysis(
    submission_method="ajax_post",
    endpoint="/Portal/Ajax/RegisterComplaint",
    validation_type="client_side_then_server",
    replicable_in_python=True,  # or False if too complex

    python_equivalent="""
    # Generated Python code
    response = requests.post(
        url=endpoint,
        data=form_data,
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    """,

    requires_browser=False,  # Can use requests library

    complex_behaviors=[
        "Problem dropdown populated via AJAX when Type selected",
        "File upload requires csrf token from page"
    ]
)
```

---

### 5. Code Generator Agent

**File**: `agents/code_generator_agent.py`

**Purpose**: Generate production-ready scraper from validated schema

**Generation Process**:

1. **Template Selection**
   - Simple form (requests library)
   - Complex form (Playwright needed)
   - Hybrid (requests + Playwright for specific parts)

2. **Code Generation with Claude Opus**
   ```python
   prompt = """Generate a production-ready Python scraper.

   Form Schema: {validated_schema}
   JS Analysis: {js_analysis}
   Test Results: {test_results}

   Requirements:
   - Handle cascading dropdowns
   - Implement proper error handling
   - Add retries for network issues
   - Take screenshots on failure
   - Return structured result with tracking ID
   - Include docstrings and type hints

   Generate complete Python code."""
   ```

3. **Code Validation**
   - Syntax check (ast.parse)
   - Run through black formatter
   - Add to test suite

4. **Self-Testing**
   ```python
   # Generated code must pass these tests
   async def test_generated_scraper():
       scraper = load_scraper("ranchi_smart_portal")
       result = await scraper.submit(test_data)
       assert result.success
       assert result.tracking_id
   ```

**Output**: Production-ready Python file
```python
# generated_scrapers/ranchi/smart_portal_scraper.py

class SmartRanchiScraper:
    """
    Auto-generated scraper for Smart Ranchi complaint portal
    Generated: 2024-01-15 14:30:00
    Validated: ✅ All tests passed
    """

    async def submit_grievance(self, data: dict) -> dict:
        """
        Submit a complaint to Smart Ranchi portal

        Args:
            data: {
                "name": str,
                "mobile": str (10 digits),
                "select_type": str (Electrical|Water|Roads|...),
                "problem": str,
                "email": str (optional),
                "address": str (optional),
                ...
            }

        Returns:
            {
                "success": bool,
                "tracking_id": str,
                "message": str,
                "screenshots": list,
                "cost": 0.0  # No AI cost!
            }
        """
        # Full implementation...
```

---

### 6. Orchestrator

**File**: `agents/orchestrator.py`

**Purpose**: Coordinate all agents and manage training sessions

**Workflow**:
```python
class Orchestrator:
    async def train_on_municipality(self, url: str, municipality: str):
        """Main training workflow"""

        # Step 1: Discovery
        form_schema = await self.form_agent.execute({
            "url": url,
            "municipality": municipality
        })

        if not form_schema["success"]:
            # Agent failed 3x, ask human
            human_input = await self.request_human_guidance()
            form_schema = await self.form_agent.execute({
                ...form_schema,
                "hints": human_input
            })

        # Step 2: JS Analysis
        js_analysis = await self.js_agent.execute({
            "url": url,
            "form_schema": form_schema
        })

        # Step 3: Validation
        test_results = await self.test_agent.execute({
            "form_schema": form_schema,
            "js_analysis": js_analysis
        })

        if test_results["confidence_score"] < 0.8:
            # Tests failing, show to human
            human_corrections = await self.show_to_human(
                form_schema, test_results
            )

            # Retry with corrections
            form_schema = await self.refine_schema(
                form_schema, human_corrections
            )

        # Step 4: Code Generation
        scraper = await self.codegen_agent.execute({
            "form_schema": form_schema,
            "js_analysis": js_analysis,
            "test_results": test_results
        })

        # Step 5: Final Validation
        final_tests = await self.test_agent.test_scraper(scraper)

        if final_tests["all_passed"]:
            await self.save_scraper(scraper)
            await self.update_knowledge_base(form_schema)
            return {"success": True, "scraper_path": scraper.path}
        else:
            # Back to human
            return await self.request_human_help()
```

---

### 7. Knowledge Base

**File**: `knowledge/knowledge_base.py`

**Purpose**: Store and retrieve learned patterns

**Schema**:
```sql
CREATE TABLE learned_patterns (
    id INTEGER PRIMARY KEY,
    pattern_type TEXT,  -- 'field_type', 'validation', 'js_pattern'
    pattern_data JSON,
    confidence FLOAT,
    times_seen INTEGER,
    success_rate FLOAT
);

CREATE TABLE municipalities (
    id INTEGER PRIMARY KEY,
    name TEXT,
    trained_date TEXT,
    scraper_path TEXT,
    success_rate FLOAT,
    total_submissions INTEGER
);

CREATE TABLE training_sessions (
    id INTEGER PRIMARY KEY,
    municipality TEXT,
    start_time TEXT,
    end_time TEXT,
    total_cost FLOAT,
    human_interventions INTEGER,
    success BOOLEAN
);
```

**Learned Patterns Examples**:
```python
{
    "pattern_type": "cascading_dropdown",
    "pattern": {
        "parent_field": "select_type",
        "child_field": "problem",
        "trigger_event": "change",
        "population_method": "ajax"
    },
    "confidence": 0.95,
    "times_seen": 12
}

{
    "pattern_type": "mobile_validation",
    "pattern": {
        "regex": "^[0-9]{10}$",
        "error_message": "Please enter valid 10 digit mobile number"
    },
    "confidence": 0.98,
    "times_seen": 50
}
```

---

### 8. Flask Dashboard

**File**: `dashboard/app.py`

**Pages**:

1. **Home** (`/`)
   - Overview stats
   - Active training sessions
   - Total municipalities
   - Cost today/week/month

2. **Training** (`/train`)
   - Start new training session
   - Enter URL, municipality name
   - Live progress view
   - Human intervention UI

3. **Monitor** (`/monitor`)
   - WebSocket real-time updates
   - Agent status cards
   - Action log stream
   - Cost ticker

4. **Scrapers** (`/scrapers`)
   - List all municipalities
   - View generated code
   - Run tests
   - Deploy/undeploy

5. **Costs** (`/costs`)
   - Per-municipality breakdown
   - Per-agent breakdown
   - Daily/weekly/monthly charts
   - ROI calculator

6. **Knowledge** (`/knowledge`)
   - Browse learned patterns
   - Search patterns
   - Pattern confidence scores

**Tech Stack**:
- Flask + Flask-SocketIO (real-time)
- Bootstrap 5 (UI)
- Chart.js (cost charts)
- DataTables (scraper library)

---

## 📋 Complete File Structure

```
grivredr/
├── agents/
│   ├── __init__.py
│   ├── base_agent.py              ✅ DONE
│   ├── form_discovery_agent.py    ⏳ NEXT
│   ├── test_agent.py
│   ├── js_analyzer_agent.py
│   ├── code_generator_agent.py
│   └── orchestrator.py
│
├── config/
│   ├── __init__.py
│   ├── ai_client.py               ✅ DONE (needs update for cost tracking)
│   └── municipalities.json
│
├── knowledge/
│   ├── __init__.py
│   ├── knowledge_base.py
│   ├── patterns.py
│   └── grivredr.db                (SQLite database)
│
├── dashboard/
│   ├── app.py                     (Flask app)
│   ├── routes.py
│   ├── socketio_events.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── home.html
│   │   ├── train.html
│   │   ├── monitor.html
│   │   ├── scrapers.html
│   │   └── costs.html
│   └── static/
│       ├── css/
│       ├── js/
│       └── img/
│
├── generated_scrapers/
│   └── ranchi/
│       ├── smart_portal_scraper.py
│       └── tests/
│           └── test_smart_portal.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── utils/
│   ├── screenshot.py
│   ├── dom_parser.py
│   └── validators.py
│
├── requirements.txt
├── pytest.ini
├── README.md
├── IMPLEMENTATION_ROADMAP.md      ✅ THIS FILE
└── main.py                        (Entry point)
```

---

## 🎯 Implementation Phases

### Phase 1: Core Agent Framework (Week 1)
- [x] BaseAgent with reflection
- [ ] FormDiscoveryAgent
- [ ] TestAgent
- [ ] Orchestrator
- [ ] Knowledge base
- [ ] Basic Flask dashboard

### Phase 2: Intelligence Layer (Week 2)
- [ ] JSAnalyzerAgent
- [ ] CodeGeneratorAgent
- [ ] Human-in-loop UI
- [ ] Pattern learning
- [ ] Cost tracking dashboard

### Phase 3: Testing & Validation (Week 3)
- [ ] TDD framework with pytest
- [ ] Train on Smart Ranchi
- [ ] Train on Jharkhand portal
- [ ] Validate reliability
- [ ] Performance optimization

### Phase 4: Production (Week 4)
- [ ] FastAPI integration
- [ ] Monitoring & alerting
- [ ] Deployment automation
- [ ] Documentation

---

## 💰 Estimated Costs

### Training Phase (Per Municipality)

| Component | API Calls | Est. Cost |
|-----------|-----------|-----------|
| Form Discovery | 3-5 Vision + 5-8 Sonnet | $0.30 |
| JS Analysis | 2-3 Opus | $0.20 |
| Test Validation | 5-10 Haiku | $0.03 |
| Code Generation | 1-2 Opus | $0.15 |
| Refinement (if needed) | 2-3 Sonnet | $0.10 |
| **Total per website** | | **~$0.78** |

### With Human Training
- First website in a region: **~$1.20**
- Similar websites (patterns learned): **~$0.30**
- Execution forever: **$0.00**

### ROI Example
```
10 municipalities, 2 websites each = 20 websites

Training cost: $15-20 (one-time)
Annual submissions: 10,000
Execution cost: $0 (vs Skyvern: $1,000)

ROI: 98% savings
```

---

## 🧪 Testing Strategy

### Unit Tests
```python
# tests/unit/test_form_discovery.py
def test_detect_required_fields():
    agent = FormDiscoveryAgent()
    html = "<input required name='mobile'>"
    fields = agent.parse_fields(html)
    assert fields[0].required == True

def test_cascading_dropdown_detection():
    # Test pattern recognition
    pass
```

### Integration Tests
```python
# tests/integration/test_training_flow.py
async def test_full_training_session():
    orchestrator = Orchestrator()
    result = await orchestrator.train_on_municipality(
        url=SMART_RANCHI_URL,
        municipality="ranchi"
    )
    assert result["success"]
    assert result["scraper_path"].exists()
```

### E2E Tests
```python
# tests/e2e/test_smart_ranchi.py
async def test_smart_ranchi_submission():
    """Test generated scraper works end-to-end"""
    scraper = load_scraper("ranchi/smart_portal")
    result = await scraper.submit_grievance(test_data)
    assert result["success"]
    assert result["tracking_id"]
```

---

## 🚀 Getting Started (After Implementation)

```bash
# 1. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2. Start Flask dashboard
python dashboard/app.py

# 3. Open browser
# http://localhost:5000

# 4. Start training session
# Click "New Training" → Enter Smart Ranchi URL → Watch agents work

# 5. Test generated scraper
python -m pytest tests/e2e/test_smart_ranchi.py
```

---

**This is the complete roadmap. Now I'll build it piece by piece!** 🚀
