#!/usr/bin/env python3
"""
Quick test to run Ranchi scraper and capture form filling
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the scraper (bypassing gitignore by direct import)
sys.path.insert(0, str(Path(__file__).parent.parent / "scrapers" / "ranchi"))

async def test_ranchi_scraper():
    """Test Ranchi scraper with visible browser"""
    
    print("\n" + "="*80)
    print("🧪 TESTING RANCHI SMART CITY SCRAPER")
    print("="*80)
    
    try:
        # Import scraper
        from ranchi_smart_scraper import Ranchi_SmartScraper
        
        print("✅ Loaded Ranchi_SmartScraper")
        
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
        
        # Initialize scraper in non-headless mode
        print(f"\n🚀 Starting scraper (visible browser)...")
        scraper = Ranchi_SmartScraper(headless=False)
        
        # Submit grievance (scraper handles browser lifecycle internally)
        print(f"\n📤 Submitting grievance...")
        result = await scraper.submit_grievance(test_data)
        
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
        
        if result.get('screenshots'):
            print(f"\n📸 Screenshots:")
            for screenshot in result['screenshots']:
                print(f"   - {screenshot}")
        
        return result.get('success', False)
        
    except ImportError as e:
        print(f"❌ Could not import scraper: {e}")
        print(f"\nMake sure the Ranchi scraper exists at:")
        print(f"   scrapers/ranchi/ranchi_smart_scraper.py")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_ranchi_scraper())
    sys.exit(0 if success else 1)
