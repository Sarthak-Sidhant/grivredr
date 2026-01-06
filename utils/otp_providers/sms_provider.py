"""
SMS OTP Provider - Retrieve OTP from SMS via API services

Supported services:
- Fast2SMS (India) - Cheapest: ₹0.15-0.20/SMS
- MSG91 (India) - ₹0.20/SMS
- 2Factor.in (India) - ₹0.18/SMS

Setup Fast2SMS:
1. Sign up at https://www.fast2sms.com/
2. Get API key and virtual number
3. Set environment variables:
   - FAST2SMS_API_KEY=your_api_key
   - FAST2SMS_NUMBER=your_virtual_number
"""
import aiohttp
import asyncio
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from utils.otp_handler import OTPProvider, BaseOTPExtractor

logger = logging.getLogger(__name__)


class Fast2SMSProvider(OTPProvider):
    """
    Fast2SMS OTP provider - Cheapest Indian SMS service
    
    API Docs: https://docs.fast2sms.com/
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        virtual_number: Optional[str] = None,
        poll_interval: float = 2.0
    ):
        """
        Initialize Fast2SMS provider
        
        Args:
            api_key: Fast2SMS API key (or set FAST2SMS_API_KEY env var)
            virtual_number: Virtual number to receive SMS (or set FAST2SMS_NUMBER)
            poll_interval: Seconds between SMS checks
        """
        self.api_key = api_key or os.getenv('FAST2SMS_API_KEY')
        self.virtual_number = virtual_number or os.getenv('FAST2SMS_NUMBER')
        self.poll_interval = poll_interval
        self.base_url = "https://www.fast2sms.com/dev/v3"
        
        if not self.api_key:
            raise ValueError(
                "Fast2SMS API key not provided. Set FAST2SMS_API_KEY environment variable."
            )
        
        if not self.virtual_number:
            raise ValueError(
                "Virtual number not provided. Set FAST2SMS_NUMBER environment variable."
            )
        
        logger.info(f"✓ Fast2SMS provider initialized (number: {self.virtual_number})")
    
    async def get_otp(self, timeout: int = 60, retry_count: int = 1) -> Optional[str]:
        """
        Poll Fast2SMS for received SMS messages
        
        Args:
            timeout: Maximum seconds to wait
            retry_count: Unused for SMS
            
        Returns:
            Extracted OTP or None
        """
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=timeout)
        
        logger.info(f"📱 Polling Fast2SMS for OTP (timeout: {timeout}s)...")
        
        # Track seen message IDs
        seen_message_ids = set()
        
        while datetime.now() < end_time:
            try:
                otp = await self._check_messages(start_time, seen_message_ids)
                if otp:
                    wait_time = (datetime.now() - start_time).total_seconds()
                    logger.info(f"✅ OTP found in {wait_time:.1f}s")
                    return otp
                
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Error checking SMS: {e}")
                await asyncio.sleep(self.poll_interval)
        
        logger.warning(f"⏱️ Timeout waiting for SMS OTP ({timeout}s)")
        return None
    
    async def _check_messages(
        self,
        since_time: datetime,
        seen_message_ids: set
    ) -> Optional[str]:
        """
        Check for new SMS messages via Fast2SMS API
        
        Args:
            since_time: Only check messages received after this time
            seen_message_ids: Set of already-processed message IDs
            
        Returns:
            Extracted OTP or None
        """
        headers = {
            'authorization': self.api_key,
            'Content-Type': 'application/json'
        }
        
        # Get received messages for the virtual number
        params = {
            'number': self.virtual_number,
            'limit': 10  # Check last 10 messages
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/receive",
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        logger.debug(f"Fast2SMS API error: {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    if not data.get('return'):
                        logger.debug("No messages found")
                        return None
                    
                    # Process messages (newest first)
                    messages = data.get('data', [])
                    for msg in reversed(messages):
                        msg_id = msg.get('id')
                        msg_text = msg.get('message', '')
                        msg_time_str = msg.get('received_at')
                        
                        # Skip if already seen
                        if msg_id in seen_message_ids:
                            continue
                        
                        seen_message_ids.add(msg_id)
                        
                        # Parse timestamp
                        try:
                            # Fast2SMS timestamp format: "2024-01-06 12:30:45"
                            msg_time = datetime.strptime(msg_time_str, "%Y-%m-%d %H:%M:%S")
                            
                            # Only process messages received after start time
                            if msg_time < since_time:
                                continue
                        except:
                            pass  # If parsing fails, still try to extract OTP
                        
                        logger.debug(f"Checking SMS: {msg_text[:50]}...")
                        
                        # Extract OTP
                        otp = self.extract_otp(msg_text)
                        if otp:
                            logger.info(f"📱 OTP found in SMS")
                            return otp
                    
                    return None
                    
        except asyncio.TimeoutError:
            logger.debug("Fast2SMS API timeout")
            return None
        except Exception as e:
            logger.debug(f"Fast2SMS check error: {e}")
            return None
    
    def extract_otp(self, text: str) -> Optional[str]:
        """
        Extract OTP from SMS text
        
        Args:
            text: SMS message text
            
        Returns:
            Extracted OTP or None
        """
        return BaseOTPExtractor.extract(text)


class MSG91Provider(OTPProvider):
    """
    MSG91 OTP provider - Popular Indian SMS service
    
    API Docs: https://docs.msg91.com/
    """
    
    def __init__(
        self,
        auth_key: Optional[str] = None,
        virtual_number: Optional[str] = None,
        poll_interval: float = 2.0
    ):
        """
        Initialize MSG91 provider
        
        Args:
            auth_key: MSG91 auth key (or set MSG91_AUTH_KEY env var)
            virtual_number: Virtual number (or set MSG91_NUMBER)
            poll_interval: Seconds between checks
        """
        self.auth_key = auth_key or os.getenv('MSG91_AUTH_KEY')
        self.virtual_number = virtual_number or os.getenv('MSG91_NUMBER')
        self.poll_interval = poll_interval
        self.base_url = "https://api.msg91.com/api/v5"
        
        if not self.auth_key:
            raise ValueError("MSG91 auth key not provided. Set MSG91_AUTH_KEY environment variable.")
        
        if not self.virtual_number:
            raise ValueError("Virtual number not provided. Set MSG91_NUMBER environment variable.")
        
        logger.info(f"✓ MSG91 provider initialized (number: {self.virtual_number})")
    
    async def get_otp(self, timeout: int = 60, retry_count: int = 1) -> Optional[str]:
        """Poll MSG91 for OTP"""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=timeout)
        
        logger.info(f"📱 Polling MSG91 for OTP (timeout: {timeout}s)...")
        
        seen_ids = set()
        
        while datetime.now() < end_time:
            try:
                otp = await self._check_messages(start_time, seen_ids)
                if otp:
                    return otp
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"MSG91 error: {e}")
                await asyncio.sleep(self.poll_interval)
        
        logger.warning(f"⏱️ Timeout waiting for MSG91 OTP ({timeout}s)")
        return None
    
    async def _check_messages(self, since_time: datetime, seen_ids: set) -> Optional[str]:
        """Check MSG91 inbox"""
        headers = {
            'authkey': self.auth_key,
            'Content-Type': 'application/json'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/inbox/fetch",
                    headers=headers,
                    params={'number': self.virtual_number},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    messages = data.get('messages', [])
                    
                    for msg in reversed(messages):
                        msg_id = msg.get('id')
                        if msg_id in seen_ids:
                            continue
                        
                        seen_ids.add(msg_id)
                        msg_text = msg.get('text', '')
                        
                        otp = self.extract_otp(msg_text)
                        if otp:
                            return otp
                    
                    return None
        except Exception as e:
            logger.debug(f"MSG91 check error: {e}")
            return None
    
    def extract_otp(self, text: str) -> Optional[str]:
        """Extract OTP from SMS"""
        return BaseOTPExtractor.extract(text)
