"""
DIA ERP Configuration
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator

from src.integrations.base_connector import ConnectorConfig


class DIAConfig(ConnectorConfig):
    """DIA ERP connector configuration"""
    
    # DIA specific settings
    server_code: str = Field(..., description="DIA server code (SUNUCUKODU)")
    api_key: str = Field(..., description="DIA API key")
    username: str = Field(..., description="DIA username")
    password: str = Field(..., description="DIA password")
    
    # Connection settings
    disconnect_same_user: bool = Field(default=True, description="Disconnect same user on login")
    session_timeout: int = Field(default=3600, description="Session timeout in seconds")
    
    # Features
    enable_kontor_tracking: bool = Field(default=True, description="Track kontör usage")
    enable_foreign_key_resolution: bool = Field(default=True, description="Enable smart foreign key resolution")
    
    # Performance settings
    default_limit: int = Field(default=100, ge=1, le=1000, description="Default query limit")
    max_retry_for_session: int = Field(default=3, description="Max retries for session errors")
    
    @validator('server_code')
    def validate_server_code(cls, v):
        if not v or len(v) < 2:
            raise ValueError('Server code must be at least 2 characters')
        return v
    
    @validator('api_key')
    def validate_api_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError('API key must be at least 10 characters')
        return v
    
    @property
    def api_base_url(self) -> str:
        """Generate DIA API base URL"""
        return f"https://{self.server_code}.ws.dia.com.tr/api/v3"
    
    class Config:
        extra = "forbid"
        
    def __init__(self, **data):
        # Set base_url automatically from server_code
        if 'server_code' in data and 'base_url' not in data:
            data['base_url'] = f"https://{data['server_code']}.ws.dia.com.tr/api/v3"
        
        super().__init__(**data)


class DIAModuleConfig(BaseModel):
    """Configuration for DIA modules"""
    
    # Core modules
    scf_enabled: bool = Field(default=True, description="Enable SCF (Stok-Cari-Fatura) module")
    sis_enabled: bool = Field(default=True, description="Enable SIS (System) module")  
    muh_enabled: bool = Field(default=False, description="Enable MUH (Muhasebe) module")
    per_enabled: bool = Field(default=False, description="Enable PER (Personel) module")
    bcs_enabled: bool = Field(default=False, description="Enable BCS (Banka-Çek-Senet) module")
    gts_enabled: bool = Field(default=False, description="Enable GTS (Görev Takip) module")
    
    # Module specific settings
    scf_default_firma_kodu: Optional[int] = Field(default=None, description="Default firma kodu for SCF")
    scf_default_donem_kodu: Optional[int] = Field(default=1, description="Default dönem kodu for SCF")
    
    class Config:
        extra = "forbid"


class DIASyncConfig(BaseModel):
    """Configuration for DIA data synchronization"""
    
    # Sync settings
    auto_sync_enabled: bool = Field(default=False, description="Enable automatic sync")
    sync_interval_minutes: int = Field(default=60, ge=5, le=1440, description="Sync interval in minutes")
    
    # Sync scope
    sync_cari_kartlar: bool = Field(default=True, description="Sync cari kartlar")
    sync_stok_kartlar: bool = Field(default=True, description="Sync stok kartlar")
    sync_fatura_fisler: bool = Field(default=False, description="Sync fatura fişleri")
    
    # Performance settings
    batch_size: int = Field(default=100, ge=10, le=1000, description="Batch size for sync")
    max_records_per_sync: int = Field(default=5000, ge=100, description="Max records per sync")
    
    # Conflict resolution
    conflict_strategy: str = Field(
        default="last_write_wins", 
        regex="^(last_write_wins|manual_review|skip)$",
        description="Strategy for handling conflicts"
    )
    
    class Config:
        extra = "forbid"