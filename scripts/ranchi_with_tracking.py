#!/usr/bin/env python3
"""
Enhanced Ranchi scraper that captures screenshots AND extracts tracking ID
"""
import asyncio
import sys
import re
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent.parent))

async def run_with_tracking():
    """Run Ranchi scraper with screenshot and tracking ID extraction"""
    
    print("\n" + "="*80)
    print("🧪 RANCHI SCRAPER - WITH TRACKING ID & SCREENSHOTS")
    print("="*80)
    
    # Test data
    test_data = {
        "name": "Sidhant Test User",
        "email": "sidhant.test@example.com",
        "mobile": "9876543210",
        "address": "123 Test Street, Ranchi, Jharkhand - 834001",
        "complaint_type": "Street Light",
        "complaint_details": "Street light not working on Main Road near Central Park. Requires immediate attention. This is a test submission.",
        "ward": "Ward 1"
    }
    
    print(f"\n📝 Test Data:")
    for key, value in test_data.items():
        val_str = value if len(str(value)) < 60 else str(value)[:57] + "..."
        print(f"   {key}: {val_str}")
    
    # Create screenshots directory
    screenshot_dir = Path("outputs/screenshots/ranchi_tracking")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\n📁 Screenshots: {screenshot_dir}")
    
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    
    tracking_id = None
    success = False
    
    try:
        url = "https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online"
        print(f"\n🌐 Navigating to form...")
        await page.goto(url, timeout=30000)
        await asyncio.sleep(2)
        
        # Screenshot 1: Initial form
        ss1 = screenshot_dir / f"{timestamp}_01_initial_form.png"
        await page.screenshot(path=str(ss1), full_page=True)
        print(f"📸 {ss1.name}")
        
        # Fill form fields
        print(f"\n📝 Filling form...")
        
        # Select problem type dropdown
        try:
            await page.select_option("select#ContentPlaceHolder1_ddlProblemType", label="Street Light")
            print("✓ Selected: Street Light")
            await asyncio.sleep(1)
        except:
            print("⚠️ Could not select problem type")
        
        # Select area
        try:
            await page.select_option("select#ContentPlaceHolder1_ddlArea", index=1)
            print("✓ Selected: Area")
            await asyncio.sleep(1)
        except:
            print("⚠️ Could not select area")
        
        # Fill text fields
        fields = {
            "ContentPlaceHolder1_txtName": test_data["name"],
            "ContentPlaceHolder1_txtMobile": test_data["mobile"],
            "ContentPlaceHolder1_txtEmail": test_data["email"],
            "ContentPlaceHolder1_txtContact": test_data["mobile"],
            "ContentPlaceHolder1_txtAddress": test_data["address"],
            "ContentPlaceHolder1_txtRemarks": test_data["complaint_details"]
        }
        
        for field_id, value in fields.items():
            try:
                await page.fill(f"#{field_id}", str(value))
                field_name = field_id.split("_")[-1]
                print(f"✓ Filled: {field_name}")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"⚠️ Could not fill {field_id}: {e}")
        
        # Screenshot 2: Filled form
        ss2 = screenshot_dir / f"{timestamp}_02_filled_form.png"
        await page.screenshot(path=str(ss2), full_page=True)
        print(f"📸 {ss2.name}")
        
        # Submit form
        print(f"\n📤 Submitting form...")
        try:
            await page.click("input#ContentPlaceHolder1_btnSubmit")
            print("✓ Clicked submit button")
            
            # Wait for response
            await asyncio.sleep(5)
            
            # Screenshot 3: After submission
            ss3 = screenshot_dir / f"{timestamp}_03_after_submit.png"
            await page.screenshot(path=str(ss3), full_page=True)
            print(f"📸 {ss3.name}")
            
            # Try to extract tracking ID from page
            page_content = await page.content()
            page_text = await page.inner_text("body")
            
            # Look for tracking/reference number patterns
            patterns = [
                r'tracking\s*(?:id|number|no\.?)[\s:]*([A-Z0-9-]+)',
                r'reference\s*(?:id|number|no\.?)[\s:]*([A-Z0-9-]+)',
                r'complaint\s*(?:id|number|no\.?)[\s:]*([A-Z0-9-]+)',
                r'registration\s*(?:id|number|no\.?)[\s:]*([A-Z0-9-]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    tracking_id = match.group(1)
                    print(f"✅ Found tracking ID: {tracking_id}")
                    break
            
            if not tracking_id:
                print("⚠️ Could not extract tracking ID from page")
                print(f"\nPage text preview:\n{page_text[:500]}")
            
            success = True
            
        except Exception as e:
            print(f"❌ Submission error: {e}")
        
        # Final screenshot
        ss4 = screenshot_dir / f"{timestamp}_04_final.png"
        await page.screenshot(path=str(ss4), full_page=True)
        print(f"📸 {ss4.name}")
        
    finally:
        await browser.close()
        await playwright.stop()
    
    # Results
    print(f"\n" + "="*80)
    print("FINAL RESULT")
    print("="*80)
    print(f"✅ Success: {success}")
    print(f"🎫 Tracking ID: {tracking_id or 'Not found'}")
    print(f"\n📸 Screenshots saved to: {screenshot_dir}")
    print(f"   Total: {len(list(screenshot_dir.glob('*.png')))} files")
    
    return {
        "success": success,
        "tracking_id": tracking_id,
        "screenshots": list(screenshot_dir.glob(f"{timestamp}_*.png"))
    }

if __name__ == "__main__":
    result = asyncio.run(run_with_tracking())
    sys.exit(0 if result["success"] else 1)
