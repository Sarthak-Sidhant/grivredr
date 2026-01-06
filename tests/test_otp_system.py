"""
OTP System Test Script

Tests the OTP automation system without needing a full portal.
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


async def test_gmail_otp():
    """Test Gmail OTP provider"""
    print("="*80)
    print("Testing Gmail OTP Provider")
    print("="*80)
    
    # Check if credentials are set
    if not os.getenv('GMAIL_EMAIL') or not os.getenv('GMAIL_APP_PASSWORD'):
        print("❌ Gmail credentials not set in .env")
        print("   Set GMAIL_EMAIL and GMAIL_APP_PASSWORD")
        return False
    
    try:
        from utils.otp_handler import get_otp_handler
        from utils.otp_providers.gmail_provider import GmailOTPProvider
        
        # Initialize
        handler = get_otp_handler()
        gmail_provider = GmailOTPProvider()
        handler.register_provider('email', gmail_provider)
        
        print(f"\n✅ Gmail provider initialized")
        print(f"   Email: {os.getenv('GMAIL_EMAIL')}")
        print("\n📧 Waiting for OTP email (timeout: 60s)...")
        print("   → Send yourself a test email with OTP now!")
        print("   → Subject: Test OTP")
        print("   → Body: Your OTP is 123456")
        print()
        
        # Wait for OTP
        otp = await handler.get_otp(otp_type='email', timeout=60)
        
        if otp:
            print(f"\n✅ SUCCESS! Received OTP: {otp}")
            return True
        else:
            print(f"\n❌ FAILED: No OTP received within 60 seconds")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_sms_otp():
    """Test SMS OTP provider (Fast2SMS)"""
    print("\n" + "="*80)
    print("Testing Fast2SMS OTP Provider")
    print("="*80)
    
    # Check if credentials are set
    if not os.getenv('FAST2SMS_API_KEY') or not os.getenv('FAST2SMS_NUMBER'):
        print("❌ Fast2SMS credentials not set in .env")
        print("   Set FAST2SMS_API_KEY and FAST2SMS_NUMBER")
        print("   (Optional - only if you have Fast2SMS account)")
        return None
    
    try:
        from utils.otp_handler import get_otp_handler
        from utils.otp_providers.sms_provider import Fast2SMSProvider
        
        # Initialize
        handler = get_otp_handler()
        sms_provider = Fast2SMSProvider()
        handler.register_provider('sms', sms_provider)
        
        print(f"\n✅ Fast2SMS provider initialized")
        print(f"   Number: {os.getenv('FAST2SMS_NUMBER')}")
        print("\n📱 Waiting for SMS OTP (timeout: 60s)...")
        print("   → Send a test SMS to your virtual number now!")
        print()
        
        # Wait for OTP
        otp = await handler.get_otp(otp_type='sms', timeout=60)
        
        if otp:
            print(f"\n✅ SUCCESS! Received OTP: {otp}")
            return True
        else:
            print(f"\n❌ FAILED: No OTP received within 60 seconds")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_otp_extraction():
    """Test OTP extraction from various text formats"""
    print("\n" + "="*80)
    print("Testing OTP Extraction Patterns")
    print("="*80)
    
    from utils.otp_handler import BaseOTPExtractor
    
    test_cases = [
        ("Your OTP is 123456", "123456"),
        ("OTP: 482913", "482913"),
        ("Verification code 789456", "789456"),
        ("PIN: 4829", "4829"),
        ("कोड: 654321", "654321"),
        ("Use 987654 to verify your account", "987654"),
        ("Dear user, 112233 is your OTP", "112233"),
        ("No OTP here!", None),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected in test_cases:
        extracted = BaseOTPExtractor.extract(text)
        
        if extracted == expected:
            print(f"✅ PASS: '{text[:40]}' → {extracted}")
            passed += 1
        else:
            print(f"❌ FAIL: '{text[:40]}' → Expected {expected}, got {extracted}")
            failed += 1
    
    print(f"\n📊 Results: {passed}/{len(test_cases)} passed")
    return failed == 0


async def main():
    """Run all tests"""
    print("\n🧪 OTP System Test Suite")
    print("="*80)
    
    results = {}
    
    # Test 1: OTP Extraction
    print("\n[Test 1/3] OTP Pattern Extraction")
    results['extraction'] = await test_otp_extraction()
    
    # Test 2: Gmail OTP
    print("\n[Test 2/3] Gmail OTP Provider")
    results['gmail'] = await test_gmail_otp()
    
    # Test 3: SMS OTP (optional)
    print("\n[Test 3/3] SMS OTP Provider (Optional)")
    results['sms'] = await test_sms_otp()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results.items():
        if result is True:
            print(f"✅ {test_name.upper()}: PASSED")
        elif result is False:
            print(f"❌ {test_name.upper()}: FAILED")
        else:
            print(f"⏭️  {test_name.upper()}: SKIPPED")
    
    print("="*80)
    print("\n💡 Tips:")
    print("   - For Gmail: Make sure IMAP is enabled and use App Password")
    print("   - For SMS: Requires paid Fast2SMS account")
    print("   - Check docs/OTP_SETUP.md for detailed setup instructions")
    print()


if __name__ == "__main__":
    asyncio.run(main())
