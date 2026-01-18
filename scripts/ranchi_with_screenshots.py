#!/usr/bin/env python3
"""
Run Ranchi scraper with screenshot capture
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers" / "ranchi"))

async def run_with_screenshots():
    """Run Ranchi scraper and capture screenshots"""
    
    print("\n" + "="*80)
    print("🧪 RANCHI SCRAPER - WITH SCREENSHOTS")
    print("="*80)
    
    from ranchi_smart_scraper import Ranchi_SmartScraper
    from playwright.async_api import async_playwright
    
    # Test data
    test_data = {
        "name": "Sidhant Test",
        "email": "sidhant.test@example.com",
        "mobile": "9876543210",
        "address": "123 Test Street, Ranchi, Jharkhand",
        "complaint_type": "Street Light",
        "complaint_details": "Street light not working on Main Road near Park. This is a test submission.",
        "ward": "Ward 1"
    }
    
    print(f"\n📝 Test Data:")
    for key, value in test_data.items():
        print(f"   {key}: {value}")
    
    # Create screenshots directory
    screenshot_dir = Path("outputs/screenshots/ranchi_test")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n📁 Screenshots will be saved to: {screenshot_dir}")
    
    # Run scraper with manual browser control for screenshots
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()
    
    try:
        # Navigate to form
        url = "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online"
        print(f"\n🌐 Navigating to {url}")
        await page.goto(url, timeout=30000)
        
        # Screenshot 1: Initial page
        screenshot1 = screenshot_dir / f"{timestamp}_01_initial.png"
        await page.screenshot(path=str(screenshot1), full_page=True)
        print(f"📸 Saved: {screenshot1}")
        
        # Now run the scraper's logic by creating instance and calling submit
        # But we'll intercept to take screenshots
        scraper = Ranchi_SmartScraper(headless=False)
        
        print(f"\n📤 Submitting via scraper...")
        result = await scraper.submit_grievance(test_data)
        
        # Wait a bit for any animations
        await asyncio.sleep(2)
        
        # Screenshot 2: After submission attempt
        screenshot2 = screenshot_dir / f"{timestamp}_02_after_submit.png"
        await page.screenshot(path=str(screenshot2), full_page=True)
        print(f"📸 Saved: {screenshot2}")
        
        # Display result
        print(f"\n" + "="*80)
        print("RESULT")
        print("="*80)
        print(f"Success: {result.get('success', False)}")
        print(f"Message: {result.get('message', 'N/A')}")
        print(f"Tracking ID: {result.get('tracking_id', 'N/A')}")
        
        if result.get('errors'):
            print(f"\n⚠️ Errors:")
            for error in result['errors']:
                print(f"   - {error}")
        
        print(f"\n📸 Screenshots saved:")
        print(f"   - {screenshot1}")
        print(f"   - {screenshot2}")
        
        # Keep browser open for review
        print(f"\n⏳ Keeping browser open for 5 seconds...")
        await asyncio.sleep(5)
        
    finally:
        await browser.close()
        await playwright.stop()
        print("✅ Browser closed")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(run_with_screenshots())
    sys.exit(0 if success else 1)
