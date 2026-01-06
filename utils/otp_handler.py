"""
OTP Handler - Universal OTP Automation for Indian Government Portals

Supports:
- Email OTP (Gmail via IMAP)
- SMS OTP (Fast2SMS, MSG91, 2Factor.in)

Usage:
    handler = OTPHandler()
    otp = await handler.get_otp(otp_type='email', timeout=60)
"""
import re
import asyncio
import logging
from typing import Optional, Literal, Dict, Any
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class OTPProvider(ABC):
    """Base class for OTP providers"""
    
    @abstractmethod
    async def get_otp(self, timeout: int = 60, retry_count: int = 1) -> Optional[str]:
        """
        Retrieve OTP from provider
        
        Args:
            timeout: Maximum seconds to wait for OTP
            retry_count: Number of retry attempts
            
        Returns:
            OTP string or None if not received
        """
        pass
    
    @abstractmethod
    def extract_otp(self, text: str) -> Optional[str]:
        """
        Extract OTP from message text using regex patterns
        
        Args:
            text: Message text (email body or SMS content)
            
        Returns:
            Extracted OTP or None
        """
        pass


class OTPHandler:
    """
    Universal OTP handler that manages multiple providers
    """
    
    def __init__(self):
        self.providers: Dict[str, OTPProvider] = {}
        self._last_check_time = None
        
    def register_provider(self, name: str, provider: OTPProvider):
        """Register an OTP provider"""
        self.providers[name] = provider
        logger.info(f"✓ Registered OTP provider: {name}")
    
    async def get_otp(
        self,
        otp_type: Literal['email', 'sms'],
        timeout: int = 60,
        retry_on_failure: bool = True
    ) -> Optional[str]:
        """
        Get OTP from specified provider
        
        Args:
            otp_type: 'email' or 'sms'
            timeout: Maximum seconds to wait
            retry_on_failure: Retry once if first attempt fails
            
        Returns:
            OTP string or None
        """
        provider = self.providers.get(otp_type)
        
        if not provider:
            logger.error(f"❌ No provider registered for OTP type: {otp_type}")
            return None
        
        logger.info(f"📱 Waiting for {otp_type.upper()} OTP (timeout: {timeout}s)...")
        
        # First attempt
        retry_count = 1 if retry_on_failure else 0
        otp = await provider.get_otp(timeout=timeout, retry_count=retry_count)
        
        if otp:
            logger.info(f"✅ OTP received: {otp}")
            return otp
        else:
            logger.error(f"❌ Failed to receive OTP after {timeout}s")
            return None
    
    def extract_otp_from_text(self, text: str, otp_type: str = 'email') -> Optional[str]:
        """
        Extract OTP from arbitrary text (for debugging/testing)
        
        Args:
            text: Message text
            otp_type: Provider type to use for extraction
            
        Returns:
            Extracted OTP or None
        """
        provider = self.providers.get(otp_type)
        if provider:
            return provider.extract_otp(text)
        return None


class BaseOTPExtractor:
    """
    Common OTP extraction patterns for Indian government portals
    """
    
    # Common OTP regex patterns (ordered by specificity)
    PATTERNS = [
        # Explicit OTP mentions
        r'(?:OTP|otp|One.time.password)[:\s]+([0-9]{4,8})',
        r'([0-9]{4,8})\s+(?:is your|is the)\s+(?:OTP|otp|verification code)',
        
        # Verification code patterns
        r'(?:verification|verify|confirmation)\s+code[:\s]+([0-9]{4,8})',
        r'([0-9]{4,8})\s+(?:is your|is the)\s+verification code',
        
        # PIN patterns
        r'(?:PIN|pin)[:\s]+([0-9]{4,8})',
        
        # Common Indian gov patterns
        r'(?:कोड|code)[:\s]*([0-9]{4,8})',  # Hindi
        r'Your\s+code\s+is[:\s]+([0-9]{4,8})',
        
        # Generic number patterns (6 digits most common)
        r'\b([0-9]{6})\b',  # 6 digits
        r'\b([0-9]{4})\b',  # 4 digits
        r'\b([0-9]{8})\b',  # 8 digits
    ]
    
    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        """
        Extract OTP using multiple patterns
        
        Args:
            text: Message text
            
        Returns:
            First matched OTP or None
        """
        # Try each pattern in order
        for pattern in cls.PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                otp = match.group(1).strip()
                # Validate: must be 4-8 digits
                if re.match(r'^[0-9]{4,8}$', otp):
                    logger.debug(f"Extracted OTP using pattern: {pattern[:50]}...")
                    return otp
        
        return None


# Statistics tracking
class OTPStats:
    """Track OTP retrieval statistics"""
    
    def __init__(self):
        self.total_requests = 0
        self.successful = 0
        self.failed = 0
        self.average_wait_time = 0.0
        self.wait_times = []
    
    def record_success(self, wait_time: float):
        """Record successful OTP retrieval"""
        self.total_requests += 1
        self.successful += 1
        self.wait_times.append(wait_time)
        self.average_wait_time = sum(self.wait_times) / len(self.wait_times)
    
    def record_failure(self):
        """Record failed OTP retrieval"""
        self.total_requests += 1
        self.failed += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        return {
            "total_requests": self.total_requests,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": f"{(self.successful / self.total_requests * 100):.1f}%" if self.total_requests > 0 else "0%",
            "average_wait_time": f"{self.average_wait_time:.1f}s"
        }


# Global instance
_otp_handler: Optional[OTPHandler] = None
_otp_stats = OTPStats()


def get_otp_handler() -> OTPHandler:
    """Get or create global OTP handler instance"""
    global _otp_handler
    if _otp_handler is None:
        _otp_handler = OTPHandler()
    return _otp_handler


def get_otp_stats() -> Dict[str, Any]:
    """Get OTP statistics"""
    return _otp_stats.get_stats()
