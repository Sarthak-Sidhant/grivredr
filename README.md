# Grivredr - AI-Powered Grievance Automation System

Automate grievance submissions to municipal websites using AI-generated scrapers.

## 🚀 Features

- **AI Website Learning**: Automatically explores and understands grievance portals using Claude Vision
- **Scraper Generation**: Generates production-ready Python scrapers from website analysis
- **Fast Execution**: Runs generated scrapers without AI costs (only used during learning)
- **Resilient**: Handles retries, errors, and various website structures
- **FastAPI Backend**: REST API for easy integration
- **Multi-Municipality**: Support for multiple municipalities and websites

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  1. Website Learning (AI-Powered, One-time)             │
│     - Playwright browser automation                     │
│     - Claude Vision analysis                            │
│     - Form structure extraction                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  2. Scraper Generation (AI-Powered, One-time)           │
│     - Claude generates Python code                      │
│     - Saves reusable scraper scripts                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  3. Execution (Fast, No AI needed)                      │
│     - Runs generated scrapers                           │
│     - Submits real grievances                           │
│     - Returns tracking IDs                              │
└─────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
grivredr/
├── config/
│   ├── ai_client.py          # Claude API client
│   └── municipalities.json   # Municipality configurations
├── website_learner/
│   ├── learner.py           # AI website exploration
│   └── screenshots/         # Website screenshots
├── scraper_generator/
│   └── generator.py         # Scraper code generator
├── generated_scrapers/
│   └── ranchi/              # Generated scrapers by municipality
├── executor/
│   ├── runner.py            # Scraper execution engine
│   └── results/             # Submission results
├── main.py                  # FastAPI backend
├── learn_ranchi.py          # Quick start script
├── test_scrapers.py         # Testing script
└── requirements.txt
```

## 🛠️ Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

### 3. Configure API Key

Your `.env` file is already configured:

```env
api_key=sk-mega-1100253245ae4c908dec293b5fc3b8ee95728a7e19269694d5a383ed2ca4b984
```

## 🎯 Quick Start - Ranchi Municipality

### Step 1: Learn Ranchi Websites & Generate Scrapers

```bash
python learn_ranchi.py
```

This will:
- Open browser and explore 3 Ranchi websites
- Analyze forms using Claude Vision
- Generate reusable scraper code
- Save scrapers to `generated_scrapers/ranchi/`

**Target Websites:**
1. https://www.ranchimunicipal.com/
2. https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online
3. https://jharkhandegovernance.com/grievance/main

### Step 2: Test Generated Scrapers

```bash
python test_scrapers.py
```

### Step 3: Start FastAPI Backend

```bash
python main.py
```

Server will start at: http://localhost:8000

## 📡 API Endpoints

### 1. Learn New Municipality

**POST** `/api/learn`

```json
{
  "municipality_name": "ranchi",
  "websites": [
    {
      "url": "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online",
      "type": "complaint_form",
      "description": "Smart Ranchi complaint registration"
    }
  ],
  "headless": true,
  "generate_scrapers": true
}
```

### 2. Submit Grievance

**POST** `/api/submit`

```json
{
  "municipality": "ranchi",
  "website_type": "complaint_form",
  "grievance_data": {
    "name": "John Doe",
    "phone": "9876543210",
    "email": "john@example.com",
    "complaint": "Street light not working",
    "category": "Electricity",
    "address": "Sector 5, Ranchi"
  }
}
```

### 3. Check Status

**POST** `/api/status`

```json
{
  "municipality": "ranchi",
  "tracking_id": "RMC12345"
}
```

### 4. List Available Scrapers

**GET** `/api/scrapers`

Returns all municipalities with ready-to-use scrapers.

### 5. List Municipalities

**GET** `/api/municipalities`

Returns configured municipalities and their websites.

## 🔧 How It Works

### Phase 1: Learning (One-time per website)

1. **Website Exploration**
   - Playwright navigates to grievance portal
   - Clicks on relevant links (complaint, grievance, etc.)
   - Takes full-page screenshots

2. **AI Analysis**
   - Claude Vision analyzes screenshots
   - Identifies form fields, types, selectors
   - Detects navigation steps and submit buttons
   - Returns structured JSON

3. **Code Generation**
   - Claude Opus generates Python scraper class
   - Includes error handling, retries, screenshots
   - Production-ready code

### Phase 2: Execution (Repeated use, fast & cheap)

1. **Load Scraper**
   - Dynamically import generated Python file
   - No AI calls needed

2. **Execute**
   - Fill form with user data
   - Handle navigation, captcha (if any)
   - Submit and capture tracking ID

3. **Return Result**
   - Success/failure status
   - Tracking ID
   - Screenshots for debugging

## 💡 Usage Examples

### Python

```python
import asyncio
from executor.runner import ScraperExecutor

async def submit():
    executor = ScraperExecutor()

    result = await executor.execute_scraper(
        municipality_name="ranchi",
        website_type="complaint_form",
        grievance_data={
            "name": "John Doe",
            "complaint": "Issue description"
        }
    )

    print(f"Tracking ID: {result['tracking_id']}")

asyncio.run(submit())
```

### cURL

```bash
curl -X POST http://localhost:8000/api/submit \
  -H "Content-Type: application/json" \
  -d '{
    "municipality": "ranchi",
    "website_type": "complaint_form",
    "grievance_data": {
      "name": "John Doe",
      "complaint": "Street light issue"
    }
  }'
```

## 🎨 AI Models Used

Via MegaLLM API (OpenAI-compatible):

- **Claude Haiku 4.5**: Fast status extraction ($1/$5 per 1M tokens)
- **Claude Sonnet 4.5**: Website analysis ($3/$15 per 1M tokens)
- **Claude Opus 4.5**: Code generation ($5/$25 per 1M tokens)

## 🔒 Security Considerations

- Scrapers run in sandboxed Playwright context
- No credentials stored (users provide data per request)
- Screenshots saved for debugging only
- Rate limiting recommended for production

## 🚧 Limitations & Future Work

**Current Limitations:**
- Captcha handling may require manual intervention
- OTP-based forms need real phone numbers
- Multi-step forms with complex logic may need refinement

**Future Enhancements:**
- Captcha solving integration (2Captcha, etc.)
- SMS OTP automation via APIs
- Automatic scraper self-healing when websites change
- WhatsApp bot integration
- Social media posting automation

## 📝 Adding New Municipalities

### Option 1: Via API

```bash
curl -X POST http://localhost:8000/api/learn \
  -H "Content-Type: application/json" \
  -d '{
    "municipality_name": "new_city",
    "websites": [
      {
        "url": "https://newcity.gov.in/complaints",
        "type": "complaint_form"
      }
    ]
  }'
```

### Option 2: Via Python Script

```python
import asyncio
from website_learner.learner import WebsiteLearner
from scraper_generator.generator import ScraperGenerator

async def add_new_city():
    websites = [{"url": "...", "type": "complaint_form"}]

    async with WebsiteLearner(headless=False) as learner:
        results = await learner.learn_multiple_websites(
            websites=websites,
            municipality_name="new_city"
        )

    generator = ScraperGenerator()
    generator.generate_scrapers_for_municipality(results, "new_city")

asyncio.run(add_new_city())
```

## 🐛 Debugging

### View Learning Results

```bash
cat website_learner/results_ranchi.json
```

### Check Scraper Code

```bash
cat generated_scrapers/ranchi/ranchi_complaint_form_scraper.py
```

### View Execution Logs

Logs are printed to console. For file logging, modify `logging.basicConfig()` in `main.py`.

### Screenshots

Saved in:
- Learning: `website_learner/screenshots/`
- Execution: Returned in API response

## 📄 License

MIT

## 🤝 Contributing

This is a proof-of-concept system. Contributions welcome!

## ⚖️ Legal

This tool is for legitimate civic engagement. Ensure compliance with website Terms of Service before use. No warranty provided.

---

**Built with ❤️ using Claude AI, Playwright, and FastAPI**
