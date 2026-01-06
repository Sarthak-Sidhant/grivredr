# 📱 OTP Automation System

## Quick Start

### 1. Choose OTP Method

**Gmail (FREE)** - Recommended for testing:
```bash
# Add to .env
GMAIL_EMAIL=your.email@gmail.com
GMAIL_APP_PASSWORD=your_app_password
```

**SMS (₹0.15/SMS)** - For production:
```bash
# Add to .env
FAST2SMS_API_KEY=your_api_key
FAST2SMS_NUMBER=91XXXXXXXXXX
```

### 2. Test Setup

```bash
# Run test script
python tests/test_otp_system.py
```

### 3. Use in Training

The system automatically detects and handles OTP fields:

```bash
python cli/train_cli.py lucknow --district lucknow \
  --url "https://portal.example.com/form"
```

When an OTP field is detected:
1. ✅ System clicks "Send OTP" button
2. ✅ Waits for OTP (email/SMS)
3. ✅ Extracts OTP automatically
4. ✅ Fills field and verifies

## Files Created

```
utils/
├── otp_handler.py              # Core OTP handler
└── otp_providers/
    ├── __init__.py
    ├── gmail_provider.py        # Gmail OTP (FREE)
    └── sms_provider.py          # SMS OTP (Fast2SMS, MSG91)

agents/
└── test_agent.py                # OTP integration

docs/
└── OTP_SETUP.md                 # Detailed setup guide

tests/
└── test_otp_system.py           # Test script

.env.example                      # OTP config template
```

## Features

✅ **Email OTP** - Gmail IMAP (FREE)
✅ **SMS OTP** - Fast2SMS, MSG91, 2Factor.in
✅ **Auto-detection** - Recognizes OTP fields
✅ **Smart extraction** - Multiple regex patterns
✅ **Retry logic** - Handles failures gracefully
✅ **Statistics** - Track success rates

## Setup Guide

See [docs/OTP_SETUP.md](docs/OTP_SETUP.md) for detailed instructions.

## Cost

| Method | Cost | Setup Time |
|--------|------|------------|
| Gmail | FREE | 5 minutes |
| Fast2SMS | ₹0.15/SMS | 10 minutes |
| MSG91 | ₹0.20/SMS | 10 minutes |

## Examples

### Manual OTP Retrieval

```python
from utils.otp_handler import get_otp_handler
from utils.otp_providers.gmail_provider import GmailOTPProvider

handler = get_otp_handler()
gmail = GmailOTPProvider()
handler.register_provider('email', gmail)

otp = await handler.get_otp(otp_type='email', timeout=60)
print(f"OTP: {otp}")
```

### Automatic (Test Agent)

OTP fields are automatically detected and filled during form testing.

## Support

- 📚 Full Docs: `docs/OTP_SETUP.md`
- 🧪 Test: `python tests/test_otp_system.py`
- 🐛 Issues: GitHub Issues

---

**Built with ❤️ for Indian Gov Portals**
