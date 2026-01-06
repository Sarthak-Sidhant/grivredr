"""
Comprehensive Pytest Test Suite for OTP System

Run with:
    pytest tests/test_otp_system.py -v
    pytest tests/test_otp_system.py -v -m manual  # For manual tests with real credentials
"""
import pytest
import asyncio
import os
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

from utils.otp_handler import (
    OTPHandler, 
    BaseOTPExtractor, 
    get_otp_handler,
    get_otp_stats,
    OTPStats
)
from utils.otp_providers.gmail_provider import GmailOTPProvider
from utils.otp_providers.sms_provider import Fast2SMSProvider, MSG91Provider


class TestOTPPatternExtraction:
    """Test OTP extraction from various text formats"""
    
    def test_extract_explicit_otp(self):
        """Test explicit OTP mentions"""
        text = "Your OTP is 123456. Please enter it within 5 minutes."
        otp = BaseOTPExtractor.extract(text)
        assert otp == "123456"
    
    def test_extract_verification_code(self):
        """Test verification code patterns"""
        text = "Verification code: 482913"
        otp = BaseOTPExtractor.extract(text)
        assert otp == "482913"
    
    def test_extract_hindi_pattern(self):
        """Test Hindi OTP patterns"""
        text = "आपका कोड: 789456 है"
        otp = BaseOTPExtractor.extract(text)
        assert otp == "789456"
    
    def test_extract_pin_pattern(self):
        """Test PIN patterns"""
        text = "Your PIN is 4829 for verification"
        otp = BaseOTPExtractor.extract(text)
        assert otp == "4829"
    
    def test_extract_from_sentence(self):
        """Test extraction from complex sentence"""
        text = "123456 is your one-time password. Do not share with anyone."
        otp = BaseOTPExtractor.extract(text)
        assert otp == "123456"
    
    def test_extract_6_digit_number(self):
        """Test fallback to 6-digit pattern"""
        text = "Please use 859472 to verify your account."
        otp = BaseOTPExtractor.extract(text)
        assert otp == "859472"
    
    def test_extract_4_digit_code(self):
        """Test 4-digit OTP"""
        text = "Your code is 5839"
        otp = BaseOTPExtractor.extract(text)
        assert otp == "5839"
    
    def test_extract_8_digit_code(self):
        """Test 8-digit OTP"""
        text = "OTP: 12345678"
        otp = BaseOTPExtractor.extract(text)
        assert otp == "12345678"
    
    def test_no_otp_in_text(self):
        """Test when no OTP present"""
        text = "Welcome to our service! Please register to continue."
        otp = BaseOTPExtractor.extract(text)
        assert otp is None
    
    def test_ignore_phone_numbers(self):
        """Test that phone numbers are not mistaken for OTP"""
        # Should prefer explicit OTP mention over phone number
        text = "Call us at 9876543210. Your OTP is 482913."
        otp = BaseOTPExtractor.extract(text)
        assert otp == "482913"
    
    def test_html_email_extraction(self):
        """Test OTP extraction from HTML email"""
        html_text = """
        <html><body>
        <p>Dear User,</p>
        <p>Your verification code is: <b>938472</b></p>
        </body></html>
        """
        otp = BaseOTPExtractor.extract(html_text)
        assert otp == "938472"
    
    def test_multiline_text(self):
        """Test OTP extraction from multiline text"""
        text = """
        Subject: Account Verification
        
        Dear Customer,
        
        Your OTP for login is: 564829
        
        Valid for 10 minutes.
        """
        otp = BaseOTPExtractor.extract(text)
        assert otp == "564829"


class TestOTPHandler:
    """Test OTPHandler core functionality"""
    
    def test_handler_initialization(self):
        """Test handler can be initialized"""
        handler = OTPHandler()
        assert handler is not None
        assert len(handler.providers) == 0
    
    def test_register_provider(self):
        """Test provider registration"""
        handler = OTPHandler()
        
        # Create mock provider
        mock_provider = Mock()
        handler.register_provider('test', mock_provider)
        
        assert 'test' in handler.providers
        assert handler.providers['test'] == mock_provider
    
    @pytest.mark.asyncio
    async def test_get_otp_no_provider(self):
        """Test error when provider not registered"""
        handler = OTPHandler()
        otp = await handler.get_otp(otp_type='email', timeout=1)
        assert otp is None
    
    @pytest.mark.asyncio
    async def test_get_otp_with_mock_provider(self):
        """Test OTP retrieval with mock provider"""
        handler = OTPHandler()
        
        # Create mock provider that returns OTP
        mock_provider = AsyncMock()
        mock_provider.get_otp = AsyncMock(return_value="123456")
        
        handler.register_provider('email', mock_provider)
        
        otp = await handler.get_otp(otp_type='email', timeout=10)
        assert otp == "123456"
        mock_provider.get_otp.assert_called_once()
    
    def test_extract_otp_from_text(self):
        """Test direct text extraction"""
        handler = OTPHandler()
        
        # Register provider with extract_otp method
        mock_provider = Mock()
        mock_provider.extract_otp = Mock(return_value="789456")
        handler.register_provider('email', mock_provider)
        
        otp = handler.extract_otp_from_text("Your OTP is 789456", otp_type='email')
        assert otp == "789456"
    
    def test_global_handler_instance(self):
        """Test global handler singleton"""
        handler1 = get_otp_handler()
        handler2 = get_otp_handler()
        assert handler1 is handler2


class TestOTPStats:
    """Test OTP statistics tracking"""
    
    def test_stats_initialization(self):
        """Test stats object initialization"""
        stats = OTPStats()
        assert stats.total_requests == 0
        assert stats.successful == 0
        assert stats.failed == 0
    
    def test_record_success(self):
        """Test recording successful OTP retrieval"""
        stats = OTPStats()
        stats.record_success(wait_time=5.2)
        
        assert stats.total_requests == 1
        assert stats.successful == 1
        assert stats.average_wait_time == 5.2
    
    def test_record_failure(self):
        """Test recording failed OTP retrieval"""
        stats = OTPStats()
        stats.record_failure()
        
        assert stats.total_requests == 1
        assert stats.failed == 1
    
    def test_average_wait_time(self):
        """Test average wait time calculation"""
        stats = OTPStats()
        stats.record_success(5.0)
        stats.record_success(10.0)
        stats.record_success(3.0)
        
        assert stats.average_wait_time == 6.0  # (5+10+3)/3
    
    def test_get_stats(self):
        """Test stats reporting"""
        stats = OTPStats()
        stats.record_success(5.0)
        stats.record_success(3.0)
        stats.record_failure()
        
        report = stats.get_stats()
        assert report['total_requests'] == 3
        assert report['successful'] == 2
        assert report['failed'] == 1
        assert '66.7%' in report['success_rate']


@pytest.mark.asyncio
class TestGmailProvider:
    """Test Gmail OTP provider (mocked for CI/CD)"""
    
    def test_initialization_from_env(self):
        """Test Gmail provider initialization from env vars"""
        with patch.dict(os.environ, {
            'GMAIL_EMAIL': 'test@gmail.com',
            'GMAIL_APP_PASSWORD': 'testpassword123'
        }):
            provider = GmailOTPProvider()
            assert provider.email_address == 'test@gmail.com'
            assert provider.app_password == 'testpassword123'
    
    def test_initialization_from_params(self):
        """Test Gmail provider initialization from parameters"""
        provider = GmailOTPProvider(
            email_address='custom@gmail.com',
            app_password='custompass'
        )
        assert provider.email_address == 'custom@gmail.com'
        assert provider.app_password == 'custompass'
    
    def test_initialization_missing_credentials(self):
        """Test error when credentials missing"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Gmail credentials"):
                GmailOTPProvider()
    
    async def test_get_otp_mock_success(self):
        """Test OTP retrieval with mocked IMAP"""
        provider = GmailOTPProvider(
            email_address='test@gmail.com',
            app_password='testpass'
        )
        
        # Mock the _check_inbox method to return OTP
        with patch.object(provider, '_check_inbox', return_value="123456"):
            otp = await provider.get_otp(timeout=5)
            assert otp == "123456"
    
    async def test_get_otp_mock_timeout(self):
        """Test OTP timeout with mocked IMAP"""
        provider = GmailOTPProvider(
            email_address='test@gmail.com',
            app_password='testpass'
        )
        
        # Mock to always return None (no OTP)
        with patch.object(provider, '_check_inbox', return_value=None):
            otp = await provider.get_otp(timeout=2)
            assert otp is None
    
    def test_extract_otp_from_email(self):
        """Test OTP extraction from email text"""
        provider = GmailOTPProvider(
            email_address='test@gmail.com',
            app_password='testpass'
        )
        
        email_text = """
        Subject: Your Verification Code
        
        Your OTP is 482913. Valid for 10 minutes.
        """
        
        otp = provider.extract_otp(email_text)
        assert otp == "482913"


@pytest.mark.asyncio
class TestSMSProviders:
    """Test SMS OTP providers (mocked)"""
    
    def test_fast2sms_initialization(self):
        """Test Fast2SMS provider initialization"""
        with patch.dict(os.environ, {
            'FAST2SMS_API_KEY': 'test_api_key',
            'FAST2SMS_NUMBER': '919876543210'
        }):
            provider = Fast2SMSProvider()
            assert provider.api_key == 'test_api_key'
            assert provider.virtual_number == '919876543210'
    
    def test_fast2sms_missing_credentials(self):
        """Test error when Fast2SMS credentials missing"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API key"):
                Fast2SMSProvider()
    
    async def test_fast2sms_get_otp_mock(self):
        """Test Fast2SMS OTP retrieval (mocked)"""
        provider = Fast2SMSProvider(
            api_key='test_key',
            virtual_number='919876543210'
        )
        
        # Mock the _check_messages method
        with patch.object(provider, '_check_messages', return_value="789456"):
            otp = await provider.get_otp(timeout=5)
            assert otp == "789456"
    
    def test_msg91_initialization(self):
        """Test MSG91 provider initialization"""
        with patch.dict(os.environ, {
            'MSG91_AUTH_KEY': 'test_auth_key',
            'MSG91_NUMBER': '919876543210'
        }):
            provider = MSG91Provider()
            assert provider.auth_key == 'test_auth_key'
            assert provider.virtual_number == '919876543210'
    
    async def test_msg91_get_otp_mock(self):
        """Test MSG91 OTP retrieval (mocked)"""
        provider = MSG91Provider(
            auth_key='test_key',
            virtual_number='919876543210'
        )
        
        with patch.object(provider, '_check_messages', return_value="456789"):
            otp = await provider.get_otp(timeout=5)
            assert otp == "456789"


@pytest.mark.integration
@pytest.mark.asyncio
class TestOTPIntegration:
    """Integration tests for OTP system"""
    
    async def test_full_email_workflow_mock(self):
        """Test complete email OTP workflow (mocked)"""
        # Initialize handler
        handler = get_otp_handler()
        
        # Create mock Gmail provider
        mock_gmail = AsyncMock()
        mock_gmail.get_otp = AsyncMock(return_value="123456")
        
        handler.register_provider('email', mock_gmail)
        
        # Get OTP
        otp = await handler.get_otp(otp_type='email', timeout=10)
        
        assert otp == "123456"
        mock_gmail.get_otp.assert_called_once()
    
    async def test_multiple_providers(self):
        """Test using multiple OTP providers"""
        handler = OTPHandler()
        
        # Register both email and SMS providers
        mock_email = AsyncMock()
        mock_email.get_otp = AsyncMock(return_value="111111")
        
        mock_sms = AsyncMock()
        mock_sms.get_otp = AsyncMock(return_value="222222")
        
        handler.register_provider('email', mock_email)
        handler.register_provider('sms', mock_sms)
        
        # Get from both
        email_otp = await handler.get_otp(otp_type='email', timeout=5)
        sms_otp = await handler.get_otp(otp_type='sms', timeout=5)
        
        assert email_otp == "111111"
        assert sms_otp == "222222"


# Manual tests (require real credentials)
@pytest.mark.manual
@pytest.mark.skipif(
    not os.getenv('GMAIL_EMAIL') or not os.getenv('GMAIL_APP_PASSWORD'),
    reason="Gmail credentials not configured"
)
@pytest.mark.asyncio
class TestRealGmailOTP:
    """
    Manual test with real Gmail account
    
    To run:
    1. Setup Gmail credentials in .env
    2. Send yourself an email with OTP
    3. Run: pytest tests/test_otp_system.py::TestRealGmailOTP -v -m manual
    """
    
    async def test_real_gmail_connection(self):
        """Test real Gmail IMAP connection"""
        provider = GmailOTPProvider()
        
        print("\n📧 Testing Gmail IMAP connection...")
        print(f"   Email: {provider.email_address}")
        print("   Send yourself an email with 'OTP: 123456' in the body")
        print("   Waiting 30 seconds for email...")
        
        otp = await provider.get_otp(timeout=30)
        
        if otp:
            print(f"✅ OTP received: {otp}")
            assert len(otp) >= 4 and len(otp) <= 8
        else:
            print("❌ No OTP received (this is expected if no email sent)")


def run_manual_tests():
    """
    Helper function to run manual tests
    
    Usage:
        python tests/test_otp_system.py
    """
    print("="*80)
    print("🧪 Grivredr OTP System - Manual Test")
    print("="*80)
    print()
    
    # Test pattern extraction
    print("1. Testing OTP Pattern Extraction...")
    test_texts = [
        ("Your OTP is 123456", "123456"),
        ("Verification code: 482913", "482913"),
        ("कोड: 789456", "789456"),
        ("PIN is 4829", "4829"),
    ]
    
    for text, expected in test_texts:
        result = BaseOTPExtractor.extract(text)
        status = "✅" if result == expected else "❌"
        print(f"   {status} '{text[:30]}...' → {result}")
    
    print()
    
    # Test Gmail provider (if configured)
    if os.getenv('GMAIL_EMAIL') and os.getenv('GMAIL_APP_PASSWORD'):
        print("2. Testing Gmail OTP Provider...")
        print(f"   Email: {os.getenv('GMAIL_EMAIL')}")
        print("   ⚠️  Send yourself a test email with 'OTP: 123456'")
        print("   Waiting 20 seconds...")
        
        async def test_gmail():
            provider = GmailOTPProvider()
            otp = await provider.get_otp(timeout=20)
            if otp:
                print(f"   ✅ OTP received: {otp}")
            else:
                print("   ⏱️  No OTP received (timeout)")
        
        asyncio.run(test_gmail())
    else:
        print("2. Gmail OTP Provider - SKIPPED (credentials not configured)")
    
    print()
    print("="*80)
    print("✅ Manual tests complete!")
    print()
    print("To run automated tests:")
    print("  pytest tests/test_otp_system.py -v")
    print()


if __name__ == '__main__':
    run_manual_tests()
