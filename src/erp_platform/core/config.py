"""
Application configuration using Pydantic Settings
"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class Settings(BaseSettings):
    """
    Application settings with environment variable support
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    ENVIRONMENT: str = Field(default="development", description="Application environment")
    DEBUG: bool = Field(default=False, description="Debug mode")
    HOST: str = Field(default="0.0.0.0", description="Application host")
    PORT: int = Field(default=8000, description="Application port")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    ENABLE_DOCS: bool = Field(default=True, description="Enable API documentation")
    
    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins"
    )
    
    # SAP Configuration
    SAP_ENABLED: bool = Field(default=False, description="Enable SAP connector")
    SAP_HOST: Optional[str] = Field(default=None, description="SAP server host")
    SAP_SYSNR: Optional[str] = Field(default="00", description="SAP system number")
    SAP_CLIENT: Optional[str] = Field(default="100", description="SAP client")
    SAP_USER: Optional[str] = Field(default=None, description="SAP username")
    SAP_PASSWORD: Optional[str] = Field(default=None, description="SAP password")
    SAP_POOL_SIZE: int = Field(default=5, description="SAP connection pool size")
    
    # Oracle Configuration
    ORACLE_ENABLED: bool = Field(default=False, description="Enable Oracle connector")
    ORACLE_HOST: Optional[str] = Field(default=None, description="Oracle server host")
    ORACLE_PORT: int = Field(default=1521, description="Oracle server port")
    ORACLE_SERVICE: Optional[str] = Field(default=None, description="Oracle service name")
    ORACLE_USER: Optional[str] = Field(default=None, description="Oracle username")
    ORACLE_PASSWORD: Optional[str] = Field(default=None, description="Oracle password")
    ORACLE_POOL_SIZE: int = Field(default=5, description="Oracle connection pool size")
    
    # SQL Server Configuration
    SQLSERVER_ENABLED: bool = Field(default=False, description="Enable SQL Server connector")
    SQLSERVER_HOST: Optional[str] = Field(default=None, description="SQL Server host")
    SQLSERVER_DATABASE: Optional[str] = Field(default=None, description="SQL Server database")
    SQLSERVER_USER: Optional[str] = Field(default=None, description="SQL Server username")
    SQLSERVER_PASSWORD: Optional[str] = Field(default=None, description="SQL Server password")
    SQLSERVER_POOL_SIZE: int = Field(default=5, description="SQL Server connection pool size")
    
    # Redis Configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    REDIS_MAX_CONNECTIONS: int = Field(default=10, description="Redis max connections")
    
    # Celery Configuration
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0", description="Celery broker URL")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1", description="Celery result backend")
    CELERY_TASK_TIME_LIMIT: int = Field(default=300, description="Task time limit in seconds")
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(default=240, description="Task soft time limit")
    
    # Performance
    MAX_WORKERS: int = Field(default=10, description="Maximum worker threads")
    REQUEST_TIMEOUT: int = Field(default=30, description="Request timeout in seconds")
    CONNECTION_TIMEOUT: int = Field(default=30, description="Connection timeout in seconds")
    MAX_RETRIES: int = Field(default=3, description="Maximum retry attempts")
    RETRY_DELAY: int = Field(default=1000, description="Retry delay in milliseconds")
    
    # Monitoring
    ENABLE_METRICS: bool = Field(default=True, description="Enable Prometheus metrics")
    ENABLE_TRACING: bool = Field(default=False, description="Enable OpenTelemetry tracing")
    OTLP_ENDPOINT: Optional[str] = Field(default=None, description="OpenTelemetry collector endpoint")
    
    # Security
    SECRET_KEY: str = Field(default="change-me-in-production", description="Application secret key")
    API_KEY_HEADER: str = Field(default="X-API-Key", description="API key header name")
    ENABLE_API_KEY: bool = Field(default=False, description="Enable API key authentication")
    
    # Data Processing
    MAX_BATCH_SIZE: int = Field(default=1000, description="Maximum batch processing size")
    CHUNK_SIZE: int = Field(default=10000, description="Data chunk size for processing")
    USE_CPP_ACCELERATION: bool = Field(default=False, description="Use C++ accelerated modules")
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return v.upper()
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        allowed = ["development", "staging", "production", "test"]
        if v.lower() not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v.lower()
    
    # Config class removed - using model_config instead


# Create global settings instance
settings = Settings()