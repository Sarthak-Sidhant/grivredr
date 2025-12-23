# Grivredr Usage Guide

## 🎯 Quick Start (5 Minutes)

### Step 1: Test AI Connection
```bash
python3 test_ai_client.py
```

You should see: `✅ Success! Response: Hello from Claude!`

### Step 2: Learn Ranchi Websites (First Time Only)
```bash
python3 learn_ranchi.py
```

**What happens:**
- Opens Chromium browser (you'll see it)
- Visits 3 Ranchi government websites
- Takes screenshots and analyzes with AI
- Generates Python scraper code
- Saves to `generated_scrapers/ranchi/`

**Duration:** 2-5 minutes per website

### Step 3: Test Generated Scrapers
```bash
python3 test_scrapers.py
```

**What happens:**
- Loads generated scrapers
- Submits test grievance
- Returns tracking ID (if successful)

### Step 4: Start API Server
```bash
python3 main.py
```

Server runs at: http://localhost:8000

Visit: http://localhost:8000/docs for interactive API documentation

## 📋 Detailed Workflows

### Workflow A: Onboard New Municipality

**Scenario:** You want to add support for a new city (e.g., Patna)

#### Method 1: Via Python Script

```python
# add_patna.py
import asyncio
from website_learner.learner import WebsiteLearner
from scraper_generator.generator import ScraperGenerator

async def add_patna():
    patna_websites = [
        {
            "url": "https://patna.gov.in/complaint-form",
            "type": "complaint_form",
            "description": "Patna Municipal Corporation complaint form"
        }
    ]

    # Learn
    async with WebsiteLearner(headless=False) as learner:
        results = await learner.learn_multiple_websites(
            websites=patna_websites,
            municipality_name="patna"
        )

    # Generate scrapers
    generator = ScraperGenerator()
    generation = generator.generate_scrapers_for_municipality(
        learning_results=results,
        municipality_name="patna"
    )

    print(f"Generated {generation['generated_count']} scrapers")

asyncio.run(add_patna())
```

Run: `python3 add_patna.py`

#### Method 2: Via API

```bash
curl -X POST http://localhost:8000/api/learn \
  -H "Content-Type: application/json" \
  -d '{
    "municipality_name": "patna",
    "websites": [
      {
        "url": "https://patna.gov.in/complaint-form",
        "type": "complaint_form",
        "description": "Patna complaint form"
      }
    ],
    "headless": true,
    "generate_scrapers": true
  }'
```

### Workflow B: Submit Grievance

#### Method 1: Via API

```bash
curl -X POST http://localhost:8000/api/submit \
  -H "Content-Type: application/json" \
  -d '{
    "municipality": "ranchi",
    "website_type": "complaint_form",
    "grievance_data": {
      "name": "Rajesh Kumar",
      "phone": "9876543210",
      "email": "rajesh@example.com",
      "complaint": "Broken footpath causing accidents",
      "category": "Roads & Infrastructure",
      "address": "Main Road, Doranda, Ranchi"
    }
  }'
```

Response:
```json
{
  "success": true,
  "tracking_id": "RMC20231223001",
  "message": "Grievance submitted successfully",
  "municipality": "ranchi",
  "execution_time": 5.2,
  "screenshots": ["path/to/screenshot.png"]
}
```

#### Method 2: Via Python

```python
import asyncio
from executor.runner import ScraperExecutor

async def submit():
    executor = ScraperExecutor()

    result = await executor.execute_scraper(
        municipality_name="ranchi",
        website_type="complaint_form",
        grievance_data={
            "name": "Rajesh Kumar",
            "phone": "9876543210",
            "complaint": "Broken footpath",
            "category": "Infrastructure"
        }
    )

    if result['success']:
        print(f"✅ Submitted! Tracking ID: {result['tracking_id']}")
    else:
        print(f"❌ Failed: {result['error']}")

asyncio.run(submit())
```

### Workflow C: Batch Submission

Submit multiple grievances at once:

```bash
curl -X POST http://localhost:8000/api/submit/batch \
  -H "Content-Type: application/json" \
  -d '{
    "submissions": [
      {
        "municipality": "ranchi",
        "website_type": "complaint_form",
        "grievance_data": {"name": "Person 1", "complaint": "Issue 1"}
      },
      {
        "municipality": "ranchi",
        "website_type": "complaint_form",
        "grievance_data": {"name": "Person 2", "complaint": "Issue 2"}
      }
    ]
  }'
```

### Workflow D: Check Status

```bash
curl -X POST http://localhost:8000/api/status \
  -H "Content-Type: application/json" \
  -d '{
    "municipality": "ranchi",
    "tracking_id": "RMC20231223001"
  }'
```

## 🔍 Understanding the System

### How AI Learning Works

```
User provides URL
       ↓
Playwright opens browser
       ↓
Navigate to website, click relevant links
       ↓
Take full-page screenshot
       ↓
Extract HTML form structure
       ↓
Send to Claude Vision:
  - Screenshot (base64)
  - HTML snippet
  - URL context
       ↓
Claude analyzes and returns JSON:
  {
    "form_fields": [...],
    "submit_button": {...},
    "navigation_steps": [...]
  }
       ↓
Claude Opus generates Python code:
  - Playwright automation script
  - Error handling
  - Screenshot capture
  - Retry logic
       ↓
Save as Python file
```

### Generated Scraper Structure

Each scraper is a Python class:

```python
class RanchiScraper:
    async def submit_grievance(self, data: dict) -> dict:
        """
        Args:
            data: {
                "name": str,
                "phone": str,
                "complaint": str,
                ...
            }

        Returns:
            {
                "success": bool,
                "tracking_id": str,
                "screenshots": list,
                "error": str (if failed)
            }
        """
        # AI-generated automation code
        pass
```

### Cost Breakdown

#### Learning Phase (One-time per website)
- Website analysis: ~$0.02 per website (Sonnet + Vision)
- Code generation: ~$0.10 per website (Opus)
- **Total: ~$0.12 per website**

#### Execution Phase (Repeated)
- **$0.00** - No AI calls needed!
- Just Playwright browser automation

**Example:** Learning 10 websites = $1.20 one-time
Then submit 1000 grievances = $0.00 AI costs

## 🎛️ Configuration

### AI Models

Edit `config/ai_client.py` to change models:

```python
self.models = {
    "fast": "claude-haiku-4-5-20251001",      # Quick tasks
    "balanced": "claude-sonnet-4-5-20250929",  # Most tasks
    "powerful": "claude-opus-4-5-20251101",    # Code generation
}
```

### Browser Settings

In `website_learner/learner.py`:

```python
WebsiteLearner(headless=True)  # Set False to see browser
```

### Retries & Timeouts

In `executor/runner.py`:

```python
await executor.execute_scraper(
    ...,
    max_retries=2  # Change retry count
)
```

## 📊 Monitoring & Debugging

### View Available Scrapers

```bash
curl http://localhost:8000/api/scrapers
```

### Check Learning Results

```bash
cat website_learner/results_ranchi.json
```

### View Generated Code

```bash
cat generated_scrapers/ranchi/ranchi_complaint_form_scraper.py
```

### Execution Results

Saved in: `executor/results/`

```bash
ls -lt executor/results/ | head -5
```

### Screenshots

- Learning screenshots: `website_learner/screenshots/`
- Execution screenshots: Returned in API response

## 🐛 Troubleshooting

### Issue: "Scraper not found"

**Solution:** Run learning first:
```bash
python3 learn_ranchi.py
```

### Issue: "Failed to parse AI analysis"

**Cause:** AI returned non-JSON response

**Solution:** Check `website_learner/results_*.json` for raw response. Manually fix if needed, or re-run learning.

### Issue: Scraper fails during execution

**Solution 1:** Check screenshots to see where it failed

**Solution 2:** Refine scraper using AI feedback:

```python
from scraper_generator.generator import ScraperGenerator

generator = ScraperGenerator()
result = generator.refine_scraper_with_feedback(
    scraper_path="generated_scrapers/ranchi/ranchi_complaint_form_scraper.py",
    error_log="Error: Submit button not found",
    screenshot_base64="..."  # Optional
)
```

### Issue: Website structure changed

**Solution:** Re-learn the website:
```bash
# Deletes old scraper and regenerates
python3 learn_ranchi.py
```

## 🚀 Production Deployment

### 1. Use Docker

```dockerfile
FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium --with-deps

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Environment Variables

```bash
export api_key="your-api-key"
```

### 3. Add Rate Limiting

```python
from slowapi import Limiter

limiter = Limiter(key_func=lambda: "global")

@app.post("/api/submit")
@limiter.limit("10/minute")
async def submit_grievance(...):
    ...
```

### 4. Background Task Queue

Use Celery or RQ for long-running tasks:

```python
from celery import Celery

celery = Celery('grivredr', broker='redis://localhost:6379')

@celery.task
def learn_website_task(municipality, websites):
    # Learning logic
    pass
```

## 📈 Scaling

### For High Volume (1000+ submissions/day)

1. **Multiple Workers**
   ```bash
   uvicorn main:app --workers 4
   ```

2. **Browser Pool**
   - Pre-launch multiple browser instances
   - Reuse connections

3. **Caching**
   - Cache municipality configs
   - Cache generated scrapers in memory

4. **Database**
   - Store submissions in PostgreSQL
   - Track status checks

## 🔐 Security

### API Key Protection
- Never commit `.env` to git
- Use secrets management (Vault, AWS Secrets Manager)

### Input Validation
- Sanitize all user inputs
- Validate phone numbers, emails
- Limit file upload sizes

### Rate Limiting
- Implement per-IP rate limits
- Use CAPTCHA for public endpoints

## 📞 WhatsApp Integration (Future)

To add WhatsApp interface:

1. Use Twilio WhatsApp API
2. Parse incoming messages
3. Call `/api/submit` endpoint
4. Reply with tracking ID

```python
from twilio.rest import Client

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    data = await request.form()
    complaint = data['Body']

    # Submit to municipality
    result = await submit_grievance(...)

    # Reply to user
    client.messages.create(
        body=f"Submitted! Tracking: {result['tracking_id']}",
        from_='whatsapp:+14155238886',
        to=data['From']
    )
```

## 🎓 Learning Resources

- **Playwright Docs**: https://playwright.dev/python/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Claude API**: https://docs.anthropic.com/

## 💡 Tips & Best Practices

1. **Always run learning in non-headless mode first** to see what the AI sees
2. **Keep screenshots** - they're invaluable for debugging
3. **Test scrapers immediately** after generation
4. **Version control generated scrapers** - they're code assets
5. **Monitor success rates** - set up alerts for failures
6. **Backup municipality configs** regularly
7. **Document field mappings** for each municipality

## 🤝 Need Help?

1. Check `README.md` for overview
2. Review code comments in generated scrapers
3. Look at execution results JSON files
4. Check browser screenshots

---

**You're all set! Start with `python3 learn_ranchi.py` and go from there.** 🚀
