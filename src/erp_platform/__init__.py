"""
ERP Integration Platform - Hybrid Python-to-C++ Integration System
"""

__version__ = "1.0.0"
__author__ = "ERP Integration Team"

from erp_platform.core.config import settings
from erp_platform.core.logging import get_logger

logger = get_logger(__name__)

__all__ = ["settings", "logger", "__version__"]