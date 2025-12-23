# 🚀 Quick Start Guide

## Get Running in 5 Minutes

### Step 1: Install Dependencies (2 minutes)
```bash
cd /home/sidhant/Desktop/grivredr

# Install Python packages
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### Step 2: Verify AI Connection (30 seconds)
```bash
python test_ai_client.py
```

Expected output:
```
✅ Success! Response: Hello from Claude!
```

### Step 3: Train on Smart Ranchi (3-5 minutes)
```bash
python train_cli.py ranchi_smart
```

**What happens**:
1. Browser opens (you'll see it)
2. Agent explores the form
3. Takes screenshots
4. Claude analyzes structure
5. Tests submission
6. Generates Python scraper
7. Shows cost breakdown

**Expected output**:
```
✅ TRAINING SUCCESSFUL!
Session ID: ranchi_smart_20241223_143022
Scraper: generated_scrapers/ranchi_smart/ranchi_smart_scraper.py
Total Cost: $0.85
Human Interventions: 0
```

### Step 4: Test Generated Scraper (1 minute)
```bash
# View the generated code
cat generated_scrapers/ranchi_smart/ranchi_smart_scraper.py

# Run the tests
cd generated_scrapers/ranchi_smart
pytest tests/ -v
```

---

## 🎯 What You Just Built

A production-ready scraper that can:
- ✅ Submit grievances automatically
- ✅ Handle validation
- ✅ Extract tracking IDs
- ✅ Take debug screenshots
- ✅ Run forever without AI costs

---

## 💡 Next Steps

### Use the Scraper
```python
import asyncio
from generated_scrapers.ranchi_smart.ranchi_smart_scraper import RanchiSmartScraper

async def submit():
    scraper = RanchiSmartScraper(headless=True)

    result = await scraper.submit_grievance({
        "mobile": "9876543210",
        "email": "user@example.com",
        "select_type": "Street Lights",
        "problem": "Not working",
        "address": "Sector 5, Ranchi",
        "remarks": "Street light near my house has been broken for 2 weeks"
    })

    if result["success"]:
        print(f"✅ Submitted! Tracking ID: {result['tracking_id']}")
    else:
        print(f"❌ Failed: {result['message']}")

asyncio.run(submit())
```

### Train More Municipalities
```bash
# Jharkhand state portal
python train_cli.py jharkhand_state

# Ranchi main website
python train_cli.py ranchi_main

# Custom municipality
python train_cli.py patna https://patna.gov.in/complaints
```

### Review Training Session
```bash
# View session details
cat training_sessions/ranchi_smart_20241223_143022.json

# Check screenshots
ls dashboard/static/screenshots/
```

---

## 🐛 Troubleshooting

### "Playwright not found"
```bash
playwright install chromium
```

### "API key error"
- Check `.env` file exists
- Verify `api_key=sk-mega-...` is set

### "Low confidence score"
- Normal for first attempt
- Agent will ask for human review
- Provide corrections via CLI prompts

### "Tests failing"
- Check website hasn't changed
- Re-run training: `python train_cli.py municipality_name`

---

## 📖 Learn More

- **Full Architecture**: Read `IMPLEMENTATION_ROADMAP.md`
- **How Agents Work**: Read `AGENTIC_EXAMPLE.md`
- **Project Status**: Read `PROJECT_STATUS.md`
- **Code**: Explore `agents/` directory

---

## 🎉 You're Done!

You now have:
- ✅ A working AI training system
- ✅ Auto-generated scrapers
- ✅ Production-ready code
- ✅ ~$1 per website cost
- ✅ $0 ongoing costs

**Start building your grievance automation platform!** 🚀
