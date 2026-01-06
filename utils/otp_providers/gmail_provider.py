"""
Gmail OTP Provider - Retrieve OTP from Gmail inbox via IMAP

Setup:
1. Enable IMAP in Gmail settings
2. Create App Password: https://myaccount.google.com/apppasswords
3. Set environment variables:
   - GMAIL_EMAIL=your.email@gmail.com
   - GMAIL_APP_PASSWORD=your_app_password
"""
import imaplib
import email
import asyncio
import logging
import os
from typing import Optional
from datetime import datetime, timedelta
from email.header import decode_header

from utils.otp_handler import OTPProvider, BaseOTPExtractor

logger = logging.getLogger(__name__)


class GmailOTPProvider(OTPProvider):
    """
    Gmail-based OTP provider using IMAP
    """
    
    def __init__(
        self,
        email_address: Optional[str] = None,
        app_password: Optional[str] = None,
        imap_server: str = "imap.gmail.com",
        poll_interval: float = 2.0
    ):
        """
        Initialize Gmail OTP provider
        
        Args:
            email_address: Gmail address (or set GMAIL_EMAIL env var)
            app_password: Gmail app password (or set GMAIL_APP_PASSWORD env var)
            imap_server: IMAP server address
            poll_interval: Seconds between inbox checks
        """
        self.email_address = email_address or os.getenv('GMAIL_EMAIL')
        self.app_password = app_password or os.getenv('GMAIL_APP_PASSWORD')
        self.imap_server = imap_server
        self.poll_interval = poll_interval
        
        if not self.email_address or not self.app_password:
            raise ValueError(
                "Gmail credentials not provided. Set GMAIL_EMAIL and GMAIL_APP_PASSWORD "
                "environment variables or pass them to constructor."
            )
        
        logger.info(f"✓ Gmail OTP provider initialized for: {self.email_address}")
    
    async def get_otp(self, timeout: int = 60, retry_count: int = 1) -> Optional[str]:
        """
        Poll Gmail inbox for OTP email
        
        Args:
            timeout: Maximum seconds to wait
            retry_count: Number of retry attempts (unused for email)
            
        Returns:
            Extracted OTP or None
        """
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=timeout)
        
        logger.info(f"📧 Polling Gmail inbox for OTP (timeout: {timeout}s)...")
        
        # Track emails we've already seen to avoid duplicates
        seen_message_ids = set()
        
        while datetime.now() < end_time:
            try:
                otp = await self._check_inbox(start_time, seen_message_ids)
                if otp:
                    wait_time = (datetime.now() - start_time).total_seconds()
                    logger.info(f"✅ OTP found in {wait_time:.1f}s")
                    return otp
                
                # Wait before next check
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                logger.error(f"Error checking inbox: {e}")
                await asyncio.sleep(self.poll_interval)
        
        logger.warning(f"⏱️ Timeout waiting for email OTP ({timeout}s)")
        return None
    
    async def _check_inbox(
        self,
        since_time: datetime,
        seen_message_ids: set
    ) -> Optional[str]:
        """
        Check inbox for new OTP emails
        
        Args:
            since_time: Only check emails received after this time
            seen_message_ids: Set of already-processed message IDs
            
        Returns:
            Extracted OTP or None
        """
        # Run IMAP operations in thread pool (blocking I/O)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._check_inbox_sync,
            since_time,
            seen_message_ids
        )
    
    def _check_inbox_sync(
        self,
        since_time: datetime,
        seen_message_ids: set
    ) -> Optional[str]:
        """
        Synchronous inbox check (runs in thread)
        """
        mail = None
        try:
            # Connect to Gmail
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email_address, self.app_password)
            mail.select('inbox')
            
            # Search for recent emails (last 5 minutes to be safe)
            search_date = (since_time - timedelta(minutes=5)).strftime("%d-%b-%Y")
            status, messages = mail.search(None, f'(SINCE {search_date})')
            
            if status != 'OK':
                return None
            
            message_ids = messages[0].split()
            
            # Check newest messages first (reverse order)
            for msg_id in reversed(message_ids):
                msg_id_str = msg_id.decode()
                
                # Skip if we've already seen this message
                if msg_id_str in seen_message_ids:
                    continue
                
                seen_message_ids.add(msg_id_str)
                
                # Fetch message
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                if status != 'OK':
                    continue
                
                # Parse email
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Get received time
                date_tuple = email.utils.parsedate_tz(email_message['Date'])
                if date_tuple:
                    msg_time = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                    
                    # Only process emails received after start time
                    if msg_time < since_time:
                        continue
                
                # Extract subject for logging
                subject = email_message.get('Subject', '')
                if subject:
                    subject = self._decode_header(subject)
                
                logger.debug(f"Checking email: {subject[:50]}...")
                
                # Extract text from email
                email_text = self._extract_email_text(email_message)
                
                # Try to extract OTP
                otp = self.extract_otp(email_text)
                if otp:
                    logger.info(f"📧 OTP found in email: {subject[:50]}...")
                    return otp
            
            return None
            
        except Exception as e:
            logger.debug(f"IMAP check error: {e}")
            return None
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass
    
    def _extract_email_text(self, email_message) -> str:
        """Extract text content from email"""
        text_parts = []
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        text_parts.append(part.get_payload(decode=True).decode())
                    except:
                        pass
                elif content_type == "text/html":
                    try:
                        # Fallback to HTML if no plain text
                        text_parts.append(part.get_payload(decode=True).decode())
                    except:
                        pass
        else:
            try:
                text_parts.append(email_message.get_payload(decode=True).decode())
            except:
                pass
        
        return '\n'.join(text_parts)
    
    def _decode_header(self, header: str) -> str:
        """Decode email header"""
        decoded = decode_header(header)
        result = []
        for text, encoding in decoded:
            if isinstance(text, bytes):
                result.append(text.decode(encoding or 'utf-8', errors='ignore'))
            else:
                result.append(text)
        return ''.join(result)
    
    def extract_otp(self, text: str) -> Optional[str]:
        """
        Extract OTP from email text
        
        Args:
            text: Email body text
            
        Returns:
            Extracted OTP or None
        """
        return BaseOTPExtractor.extract(text)
