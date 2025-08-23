"""
Turkish localization utilities for Turkish Business Integration Platform
"""

import structlog

logger = structlog.get_logger(__name__)

def setup_turkish_localization():
    """Setup Turkish localization"""
    logger.info("Turkish localization setup completed")

def format_turkish_currency(amount: float) -> str:
    """Format amount as Turkish Lira"""
    return f"{amount:,.2f} ₺"

def format_turkish_phone(phone: str) -> str:
    """Format Turkish phone number"""
    if phone.startswith("+90"):
        return phone
    if phone.startswith("0"):
        return f"+90{phone[1:]}"
    return f"+90{phone}"