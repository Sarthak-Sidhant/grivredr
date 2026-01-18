#!/usr/bin/env python3
"""
Run Ranchi scraper to COMPLETION and capture final screenshot with reference number
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers" / "ranchi"))

async def run_to_completion():
    """Run Ranchi scraper and capture final result"""
    
    print("\n" + "="*80)
    print("🧪 RANCHI SCRAPER - COMPLETE SUBMISSION")
    print("="*80)
    
    from ranchi_smart_scraper import Ranchi_SmartScraper
    
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
    screenshot_dir = Path("outputs/screenshots/ranchi_final")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📁 Screenshots directory: {screenshot_dir}")
    print(f"\n🚀 Running scraper...")
    
    try:
        # Run scraper
        scraper = Ranchi_SmartScraper(headless=False)
        result = await scraper.submit_grievance(test_data)
        
        # Display full result
        print(f"\n" + "="*80)
        print("SUBMISSION RESULT")
        print("="*80)
        print(f"Success: {result.get('success', False)}")
        print(f"Message: {result.get('message', 'N/A')}")
        print(f"Tracking ID: {result.get('tracking_id', 'N/A')}")
        print(f"Reference Number: {result.get('reference_number', 'N/A')}")
        
        if result.get('errors'):
            print(f"\n⚠️ Errors ({len(result['errors'])}):")
            for error in result['errors']:
                print(f"   - {error}")
        
        if result.get('screenshots'):
            print(f"\n📸 Screenshots captured by scraper:")
            for screenshot in result['screenshots']:
                print(f"   - {screenshot}")
        
        # Print full result dict
        print(f"\n📋 Full Result Dictionary:")
        import json
        print(json.dumps(result, indent=2, default=str))
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(run_to_completion())
    
    if result and result.get('success'):
        print(f"\n✅ SUCCESS - Tracking ID: {result.get('tracking_id', 'N/A')}")
        sys.exit(0)
    else:
        print(f"\n❌ FAILED")
        sys.exit(1)
