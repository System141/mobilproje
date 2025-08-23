"""
Global configuration for Turkish Business Integration Platform
"""

import os
from typing import List, Optional
from functools import lru_cache

from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Basic app configuration
    environment: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    
    # Database configuration
    database_url: str = "postgresql+asyncpg://turkuser:turkpass@localhost/turkplatform"
    database_pool_size: int = 20
    database_max_overflow: int = 10
    
    # Redis configuration
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 10
    
    # Kafka configuration
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "turkplatform"
    kafka_auto_offset_reset: str = "latest"
    
    # Security configuration
    secret_key: str = "change-me-in-production-with-strong-key"
    algorithm: str = "RS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    
    # CORS configuration
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://yourdomain.com"
    ]
    cors_allow_credentials: bool = True
    
    # Multi-tenant configuration
    default_tenant_plan: str = "trial"
    max_tenants_per_instance: int = 1000
    
    # Turkish Business Integrations
    
    # Netgsm (SMS & WhatsApp)
    netgsm_enabled: bool = False
    netgsm_user_code: Optional[str] = None
    netgsm_password: Optional[str] = None
    netgsm_sender_name: str = "FIRMA"
    
    # Bulutfon (Phone System)
    bulutfon_enabled: bool = False
    bulutfon_api_key: Optional[str] = None
    bulutfon_master_token: Optional[str] = None
    
    # Arvento (Vehicle Tracking)
    arvento_enabled: bool = False
    arvento_api_key: Optional[str] = None
    arvento_username: Optional[str] = None
    arvento_password: Optional[str] = None
    
    # Findeks (Credit Scoring)
    findeks_enabled: bool = False
    findeks_user_code: Optional[str] = None
    findeks_password: Optional[str] = None
    
    # Iyzico (Payment Gateway)
    iyzico_enabled: bool = False
    iyzico_api_key: Optional[str] = None
    iyzico_secret_key: Optional[str] = None
    iyzico_base_url: str = "https://sandbox-api.iyzipay.com"
    
    # E-Fatura (Turkish E-Invoice)
    efatura_enabled: bool = False
    efatura_username: Optional[str] = None
    efatura_password: Optional[str] = None
    efatura_test_mode: bool = True
    
    # KVKK Compliance
    kvkk_enabled: bool = True
    kvkk_default_retention_days: int = 365
    kvkk_breach_notification_email: str = "kvkk@yourcompany.com"
    data_residency_region: str = "turkey"
    
    # Monitoring & Observability
    prometheus_enabled: bool = True
    prometheus_port: int = 9090
    sentry_dsn: Optional[str] = None
    sentry_environment: str = "development"
    
    # Performance Settings
    max_concurrent_requests: int = 1000
    request_timeout_seconds: int = 30
    max_upload_size_mb: int = 100
    
    # Turkish Localization
    default_language: str = "tr-TR"
    default_timezone: str = "Europe/Istanbul"
    default_currency: str = "TRY"
    
    # Production Settings
    use_ssl: bool = False
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from environment variable"""
        if isinstance(v, str):
            try:
                # Handle JSON string format
                import json
                return json.loads(v)
            except json.JSONDecodeError:
                # Handle comma-separated format
                return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("database_url")
    def validate_database_url(cls, v):
        """Ensure database URL is properly formatted"""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("Database URL must use postgresql or postgresql+asyncpg scheme")
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment.lower() == "development"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment"""
        return self.environment.lower() == "testing"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings
    
    Returns:
        Settings: Application configuration instance
    """
    return Settings()


# Global settings instance
settings = get_settings()