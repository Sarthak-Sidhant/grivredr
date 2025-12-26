# Grivredr - System Architecture

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │   Web    │  │ WhatsApp │  │   API    │  │  Python  │       │
│  │Interface │  │   Bot    │  │  Client  │  │  Script  │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       └─────────────┴─────────────┴──────────────┘             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FASTAPI REST API (main.py)                    │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │
│  │ /api/learn    │  │ /api/submit   │  │ /api/status   │      │
│  │ /api/scrapers │  │ /api/batch    │  │ /api/munic.   │      │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘      │
└──────────┼──────────────────┼──────────────────┼───────────────┘
           │                  │                  │
           ▼                  ▼                  ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Website Learner  │  │ Scraper Executor │  │ Status Checker   │
│  (learner.py)    │  │  (runner.py)     │  │  (runner.py)     │
│                  │  │                  │  │                  │
│ • Playwright     │  │ • Load scraper   │  │ • Run status     │
│ • Browser auto   │  │ • Execute        │  │   scraper        │
│ • Screenshots    │  │ • Handle retry   │  │ • Parse status   │
│ • HTML extract   │  │ • Save results   │  │                  │
└────────┬─────────┘  └────────┬─────────┘  └──────────────────┘
         │                     │
         ▼                     │
┌──────────────────┐           │
│  Claude Vision   │           │
│   AI Analysis    │           │
│  (ai_client.py)  │           │
│                  │           │
│ • Analyze form   │           │
│ • Identify fields│           │
│ • Return JSON    │           │
└────────┬─────────┘           │
         │                     │
         ▼                     │
┌──────────────────┐           │
│ Scraper Generator│           │
│  (generator.py)  │           │
│                  │           │
│ • Call Claude    │           │
│ • Generate code  │           │
│ • Save to file   │           │
└────────┬─────────┘           │
         │                     │
         ▼                     │
┌──────────────────────────────┴───────────────────────────────┐
│              Generated Scrapers (Python Files)                │
│  generated_scrapers/                                          │
│    ├── ranchi/                                                │
│    │   ├── ranchi_complaint_form_scraper.py                   │
│    │   ├── ranchi_status_checker_scraper.py                   │
│    │   └── __init__.py                                        │
│    ├── patna/                                                 │
│    └── ...                                                    │
└───────────────────────────────────────────────────────────────┘
         │                     ▲
         └─────────────────────┘
           (Executor loads and runs scrapers)
```

## 🔄 Data Flow

### Flow 1: Learning & Generation (One-time)

```
Municipality URL
       │
       ▼
┌──────────────────┐
│ WebsiteLearner   │ ──► Open browser (Playwright)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Navigate & Click │ ──► Find grievance form
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Take Screenshot  │ ──► Full page PNG + HTML
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Claude Vision    │ ──► Analyze structure
│ (Sonnet 4.5)     │     Return JSON
└──────┬───────────┘
       │
       ▼
{
  "form_fields": [
    {"label": "Name", "selector": "#name", ...},
    {"label": "Phone", "selector": "#phone", ...}
  ],
  "submit_button": {"selector": "#submit"},
  ...
}
       │
       ▼
┌──────────────────┐
│ Claude Opus      │ ──► Generate Python code
│ (Code Gen)       │
└──────┬───────────┘
       │
       ▼
class RanchiScraper:
    async def submit_grievance(self, data):
        # AI-generated Playwright automation
        ...
        return {"success": True, "tracking_id": "..."}
       │
       ▼
┌──────────────────┐
│ Save to File     │ ──► generated_scrapers/ranchi/...
└──────────────────┘
```

### Flow 2: Grievance Submission (Repeated, Fast)

```
User Grievance Data
{
  "name": "John",
  "complaint": "...",
  ...
}
       │
       ▼
┌──────────────────┐
│ FastAPI Endpoint │ ──► /api/submit
│ (main.py)        │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ ScraperExecutor  │ ──► Load generated scraper
│ (runner.py)      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Dynamic Import   │ ──► Import RanchiScraper class
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Execute Scraper  │ ──► scraper.submit_grievance(data)
│ (No AI calls!)   │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Playwright       │ ──► Open browser
│ Automation       │     Fill form
│                  │     Submit
│                  │     Capture tracking ID
└──────┬───────────┘
       │
       ▼
{
  "success": true,
  "tracking_id": "RMC123",
  "screenshots": [...],
  "execution_time": 5.2
}
       │
       ▼
┌──────────────────┐
│ Save Result      │ ──► executor/results/ranchi_...json
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Return to User   │
└──────────────────┘
```

## 📦 Module Breakdown

### 1. config/ai_client.py
**Purpose:** Unified Claude API client

**Key Functions:**
- `analyze_website_structure()` - Vision analysis
- `generate_scraper_code()` - Code generation
- `improve_scraper_with_feedback()` - Self-healing
- `extract_status_from_page()` - Status parsing

**Models Used:**
- Haiku (fast/cheap)
- Sonnet (balanced)
- Opus (powerful)

### 2. website_learner/learner.py
**Purpose:** AI-powered website exploration

**Key Class:** `WebsiteLearner`

**Methods:**
- `learn_website()` - Explore single site
- `learn_multiple_websites()` - Batch learning
- `take_screenshot()` - Capture page
- `extract_form_html()` - Get form structure

**Output:** JSON with analysis + screenshots

### 3. scraper_generator/generator.py
**Purpose:** Convert analysis → Python code

**Key Class:** `ScraperGenerator`

**Methods:**
- `generate_scraper()` - Create scraper file
- `refine_scraper_with_feedback()` - Fix errors
- `generate_scrapers_for_municipality()` - Batch gen

**Output:** Python files in `generated_scrapers/`

### 4. executor/runner.py
**Purpose:** Run generated scrapers

**Key Class:** `ScraperExecutor`

**Methods:**
- `execute_scraper()` - Run single scraper
- `execute_batch()` - Parallel execution
- `check_grievance_status()` - Status lookup
- `list_available_scrapers()` - Inventory

**Output:** Submission results + tracking IDs

### 5. main.py
**Purpose:** FastAPI REST API

**Endpoints:**
- `POST /api/learn` - Learn new municipality
- `POST /api/submit` - Submit grievance
- `POST /api/submit/batch` - Batch submit
- `POST /api/status` - Check status
- `GET /api/scrapers` - List scrapers
- `GET /api/municipalities` - List configs

## 🗄️ Data Storage

### File System Structure

```
grivredr/
├── config/
│   └── municipalities.json          # Municipality configurations
│
├── website_learner/
│   ├── screenshots/                 # Learning screenshots
│   │   ├── ranchi_main_portal.png
│   │   └── ranchi_complaint_form.png
│   └── results_ranchi.json          # Raw learning results
│
├── generated_scrapers/              # AI-generated code
│   ├── ranchi/
│   │   ├── ranchi_complaint_form_scraper.py
│   │   ├── ranchi_status_checker_scraper.py
│   │   └── __init__.py
│   └── patna/
│       └── ...
│
└── executor/
    └── results/                     # Execution results
        ├── ranchi_complaint_form_20231223_120045.json
        └── ranchi_status_check_20231223_120145.json
```

### municipalities.json Schema

```json
{
  "ranchi": {
    "name": "Ranchi Municipal Corporation",
    "websites": [
      {
        "url": "https://...",
        "type": "complaint_form",
        "description": "..."
      }
    ],
    "generated_scrapers": [
      {
        "file_path": "generated_scrapers/ranchi/...",
        "metadata": {
          "generated_at": "2023-12-23T12:00:00",
          "url": "...",
          "website_type": "complaint_form"
        }
      }
    ],
    "last_updated": "2023-12-23T12:00:00"
  }
}
```

### Execution Result Schema

```json
{
  "timestamp": "20231223_120045",
  "municipality": "ranchi",
  "website_type": "complaint_form",
  "input_data": {
    "name": "John Doe",
    "complaint": "..."
  },
  "result": {
    "success": true,
    "tracking_id": "RMC123",
    "screenshots": ["path/to/screenshot.png"],
    "execution_time": 5.2,
    "attempts": 1
  }
}
```

## 🔐 Security Architecture

### API Key Management
- Stored in `.env` (gitignored)
- Loaded via `python-dotenv`
- Used only by `ai_client.py`

### Input Validation
- Pydantic models validate all API inputs
- Municipality names sanitized
- File paths checked for directory traversal

### Browser Security
- Playwright runs in isolated context
- No persistent cookies/storage
- Each execution starts fresh

### Rate Limiting (Recommended)
```python
from slowapi import Limiter

@app.post("/api/submit")
@limiter.limit("10/minute")
async def submit_grievance(...):
    ...
```

## ⚡ Performance Characteristics

### Learning Phase
- **Time:** 30-120 seconds per website
- **Cost:** ~$0.12 per website (AI costs)
- **Frequency:** One-time (or when site changes)

### Execution Phase
- **Time:** 5-15 seconds per submission
- **Cost:** $0.00 (no AI calls)
- **Frequency:** Every submission

### Scalability
- **Concurrency:** Limited by browser instances
- **Bottleneck:** Playwright automation (CPU-bound)
- **Solution:** Horizontal scaling with multiple workers

## 🔄 Error Handling & Resilience

### Retry Logic
```python
for attempt in range(max_retries + 1):
    try:
        result = await scraper.submit_grievance(data)
        if result['success']:
            return result
        await asyncio.sleep(2)  # Wait before retry
    except Exception as e:
        if attempt < max_retries:
            continue
        return error_result
```

### Self-Healing
When scraper fails:
1. Capture error log
2. Take screenshot at failure point
3. Send to Claude with original code
4. Generate improved version
5. Save as new version (backup old)

### Failure Modes
| Failure | Cause | Recovery |
|---------|-------|----------|
| Selector not found | Website changed | Re-learn site |
| Timeout | Slow site | Increase timeout |
| Submit failed | Form validation | Check data format |
| AI API error | Network/quota | Retry with backoff |
| Import error | Scraper not found | Run learning |

## 🚀 Deployment Options

### Option 1: Single Server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Option 2: Docker
```dockerfile
FROM python:3.11
RUN playwright install chromium --with-deps
CMD ["uvicorn", "main:app"]
```

### Option 3: Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grivredr
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: grivredr
        image: grivredr:latest
        env:
        - name: api_key
          valueFrom:
            secretKeyRef:
              name: grivredr-secrets
              key: api-key
```

## 📊 Monitoring & Observability

### Metrics to Track
- Submissions per municipality
- Success rate by municipality
- Average execution time
- AI API costs
- Scraper failure rate

### Logging
```python
import logging

logger.info(f"Submitting to {municipality}")
logger.warning(f"Retry attempt {attempt}")
logger.error(f"Submission failed: {error}")
```

### Health Checks
```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "scrapers_count": len(list_scrapers()),
        "ai_client": "connected"
    }
```

## 🔮 Future Enhancements

### 1. Auto-Healing Scrapers
- Monitor success rates
- Auto-regenerate on repeated failures
- A/B test scraper versions

### 2. Scraper Versioning
- Git-based version control
- Rollback to previous versions
- Track performance over time

### 3. Multi-Model Support
- Try GPT-4V for comparison
- Fallback between models
- Cost optimization

### 4. Browser Pool
- Pre-launch browser instances
- Reuse connections
- Faster execution

### 5. Database Integration
- PostgreSQL for submissions
- Redis for caching
- Elasticsearch for search

---

**This architecture prioritizes:**
- ✅ Cost efficiency (AI only during learning)
- ✅ Scalability (generated code runs without AI)
- ✅ Resilience (retries, self-healing)
- ✅ Maintainability (clear separation of concerns)
