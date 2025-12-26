#!/usr/bin/env python3
"""
Test the abua_sathi scraper LIVE - let's prove Claude's worth!
"""
import asyncio
import sys
from pathlib import Path

# Import the scraper
sys.path.insert(0, str(Path(__file__).parent.parent))
from outputs.generated_scrapers.ranchi_district.portals.abua_sathi.abua_sathi_scraper import AbuaSathiScraper


async def test_live():
    """Test the scraper with real data"""
    
    print("=" * 80)
    print("🔥 TESTING CLAUDE'S SCRAPER - LET'S SEE IF IT'S REALLY THAT TOUGH")
    print("=" * 80)
    print()
    
    print("📋 Test Data:")
    test_data = {
        'name': 'Rahul Kumar Test',
        'contact': '9876543210',
        'village_name': 'Test Village, Ranchi',
        'block_id': '500107',  # Ranchi Municipal Corporation
        'jurisdiction_id': '600624',  # Ward-1 (cascading from Ranchi Municipal Corporation)
        'department_id': '500107',  # Ranchi Municipal Corporation
        'description': 'This is an automated test of the AI-generated scraper. Testing if Claude can really handle this form.'
    }
    
    for key, value in test_data.items():
        print(f"  {key}: {value}")
    print()
    
    print("🚀 Starting scraper (visible browser)...")
    print()
    
    scraper = AbuaSathiScraper(headless=False)
    
    try:
        result = await scraper.submit_grievance(test_data)
        
        print()
        print("=" * 80)
        print("📊 RESULT:")
        print("=" * 80)
        print(f"Success: {result.get('success', False)}")
        
        if result.get('success'):
            print(f"✅ IT WORKED! Claude delivered!")
            if result.get('tracking_id'):
                print(f"🎯 Tracking ID: {result['tracking_id']}")
            if result.get('message'):
                print(f"💬 Message: {result['message']}")
        else:
            print(f"❌ FAILED! Claude needs improvement...")
            if result.get('error'):
                print(f"Error: {result['error']}")
            if result.get('message'):
                print(f"Message: {result['message']}")
        
        print("=" * 80)
        
        return result
        
    except Exception as e:
        print()
        print("=" * 80)
        print(f"💥 EXCEPTION: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    result = asyncio.run(test_live())
    sys.exit(0 if result.get('success') else 1)
