"""
DIA ERP Data Models
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from src.models.base import BaseModel as SQLBaseModel


# Pydantic Models for API
class DIAResponse(BaseModel):
    """DIA API response model"""
    code: str
    msg: Optional[str] = None
    data: Optional[Any] = None
    
    @property
    def is_success(self) -> bool:
        return self.code == "200"
    
    @property 
    def is_error(self) -> bool:
        return self.code != "200"


class DIALoginResponse(DIAResponse):
    """DIA login response"""
    session_id: Optional[str] = Field(None, alias="msg")


class DIAFirmaDonem(BaseModel):
    """DIA firma ve dönem bilgisi"""
    firmakodu: int
    firmaadi: str
    donemkodu: int
    donemadi: str
    ontanimli: bool = False


class DIAYetkiler(BaseModel):
    """DIA yetki bilgileri"""
    firmalar: List[DIAFirmaDonem]
    subeler: List[Dict[str, Any]]
    depolar: List[Dict[str, Any]]


# SCF Modülü Models
class DIACariKart(BaseModel):
    """DIA Cari Kart modeli"""
    _key: Optional[int] = None
    _level1: Optional[int] = None  # Firma kodu
    _level2: Optional[int] = None  # Dönem kodu
    carikartkodu: str
    unvan: str
    carikarttipi: str  # AL/SAT/ALSAT
    verginumarasi: Optional[str] = None
    vergidairesi: Optional[str] = None
    _key_sis_bolge: Optional[int] = None
    _key_sis_temsilci: Optional[int] = None
    aktif: bool = True
    _cdate: Optional[datetime] = None
    _user: Optional[str] = None
    
    @validator('carikarttipi')
    def validate_carikart_tipi(cls, v):
        allowed = ["AL", "SAT", "ALSAT"]
        if v not in allowed:
            raise ValueError(f'Cari kart tipi {allowed} değerlerinden biri olmalı')
        return v


class DIAStokKart(BaseModel):
    """DIA Stok Kart modeli"""
    _key: Optional[int] = None
    _level1: Optional[int] = None
    _level2: Optional[int] = None
    stokkartkodu: str
    stokkartadi: str
    stokkarttipi: str  # MALZEME/HIZMET/SABIT_KIYMET
    _key_sis_stokgrubu: Optional[int] = None
    _key_sis_birim: Optional[int] = None
    kdvorani: Optional[Decimal] = Field(default=Decimal('0'))
    satisfiyati: Optional[Decimal] = Field(default=Decimal('0'))
    aktif: bool = True
    _cdate: Optional[datetime] = None
    _user: Optional[str] = None
    
    @validator('stokkarttipi')
    def validate_stok_tipi(cls, v):
        allowed = ["MALZEME", "HIZMET", "SABIT_KIYMET"]
        if v not in allowed:
            raise ValueError(f'Stok kart tipi {allowed} değerlerinden biri olmalı')
        return v


class DIAFaturaFisi(BaseModel):
    """DIA Fatura Fiş modeli"""
    _key: Optional[int] = None
    _level1: Optional[int] = None
    _level2: Optional[int] = None
    faturafisnumarasi: str
    faturafistarihi: date
    _key_scf_carikart: int
    toplamtutar: Decimal
    kdvtoplami: Decimal
    faturatipi: str  # ALIS/SATIS
    _cdate: Optional[datetime] = None
    _user: Optional[str] = None
    
    @validator('faturatipi')
    def validate_fatura_tipi(cls, v):
        allowed = ["ALIS", "SATIS"]
        if v not in allowed:
            raise ValueError(f'Fatura tipi {allowed} değerlerinden biri olmalı')
        return v


# SIS Modülü Models
class DIAKullanici(BaseModel):
    """DIA Kullanıcı modeli"""
    _key: Optional[int] = None
    kullaniciadi: str
    adsoyad: str
    eposta: Optional[str] = None
    telefon: Optional[str] = None
    aktif: bool = True
    _cdate: Optional[datetime] = None


class DIAFirma(BaseModel):
    """DIA Firma modeli"""
    _key: Optional[int] = None
    firmakodu: int
    firmaadi: str
    verginumarasi: Optional[str] = None
    adres: Optional[str] = None
    aktif: bool = True


class DIABolge(BaseModel):
    """DIA Bölge modeli"""
    _key: Optional[int] = None
    _level1: Optional[int] = None
    kod: str
    ad: str
    aktif: bool = True


# SQLAlchemy Models for Database Storage
class DIACariKartDB(SQLBaseModel):
    """DIA Cari Kart database model"""
    __tablename__ = "dia_cari_kartlar"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=UUID)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    
    # DIA fields
    dia_key = Column(Integer, nullable=True, index=True)
    dia_level1 = Column(Integer, nullable=True)  # Firma kodu
    dia_level2 = Column(Integer, nullable=True)  # Dönem kodu
    carikartkodu = Column(String(50), nullable=False, index=True)
    unvan = Column(String(250), nullable=False)
    carikarttipi = Column(String(10), nullable=False)  # AL/SAT/ALSAT
    verginumarasi = Column(String(50), nullable=True)
    vergidairesi = Column(String(100), nullable=True)
    dia_key_sis_bolge = Column(Integer, nullable=True)
    dia_key_sis_temsilci = Column(Integer, nullable=True)
    aktif = Column(Boolean, default=True)
    dia_cdate = Column(DateTime, nullable=True)
    dia_user = Column(String(50), nullable=True)
    
    # Sync metadata
    last_sync_at = Column(DateTime, nullable=True)
    sync_status = Column(String(20), default="pending")  # pending/synced/error
    sync_error = Column(Text, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="dia_cari_kartlar")


class DIAStokKartDB(SQLBaseModel):
    """DIA Stok Kart database model"""
    __tablename__ = "dia_stok_kartlar"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=UUID)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    
    # DIA fields
    dia_key = Column(Integer, nullable=True, index=True)
    dia_level1 = Column(Integer, nullable=True)
    dia_level2 = Column(Integer, nullable=True)
    stokkartkodu = Column(String(50), nullable=False, index=True)
    stokkartadi = Column(String(250), nullable=False)
    stokkarttipi = Column(String(20), nullable=False)  # MALZEME/HIZMET/SABIT_KIYMET
    dia_key_sis_stokgrubu = Column(Integer, nullable=True)
    dia_key_sis_birim = Column(Integer, nullable=True)
    kdvorani = Column(Numeric(18, 4), default=0)
    satisfiyati = Column(Numeric(18, 4), default=0)
    aktif = Column(Boolean, default=True)
    dia_cdate = Column(DateTime, nullable=True)
    dia_user = Column(String(50), nullable=True)
    
    # Sync metadata
    last_sync_at = Column(DateTime, nullable=True)
    sync_status = Column(String(20), default="pending")
    sync_error = Column(Text, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="dia_stok_kartlar")


class DIAFaturaFisiDB(SQLBaseModel):
    """DIA Fatura Fiş database model"""
    __tablename__ = "dia_fatura_fisler"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=UUID)
    tenant_id = Column(PGUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    
    # DIA fields
    dia_key = Column(Integer, nullable=True, index=True)
    dia_level1 = Column(Integer, nullable=True)
    dia_level2 = Column(Integer, nullable=True)
    faturafisnumarasi = Column(String(50), nullable=False, index=True)
    faturafistarihi = Column(Date, nullable=False, index=True)
    dia_key_scf_carikart = Column(Integer, nullable=False)
    toplamtutar = Column(Numeric(18, 4), nullable=False)
    kdvtoplami = Column(Numeric(18, 4), nullable=False)
    faturatipi = Column(String(10), nullable=False)  # ALIS/SATIS
    dia_cdate = Column(DateTime, nullable=True)
    dia_user = Column(String(50), nullable=True)
    
    # Sync metadata
    last_sync_at = Column(DateTime, nullable=True)
    sync_status = Column(String(20), default="pending")
    sync_error = Column(Text, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="dia_fatura_fisler")


# Request/Response Models for API Operations
class DIAListRequest(BaseModel):
    """DIA listeleme request modeli"""
    firma_kodu: int
    donem_kodu: int = 1
    filters: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    sorts: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    limit: Optional[int] = Field(default=100, ge=1, le=1000)
    offset: Optional[int] = Field(default=0, ge=0)
    selectedcolumns: Optional[List[str]] = None


class DIACreateRequest(BaseModel):
    """DIA ekleme request modeli"""
    firma_kodu: int
    donem_kodu: int = 1
    data: Dict[str, Any]


class DIAUpdateRequest(BaseModel):
    """DIA güncelleme request modeli"""
    firma_kodu: int
    donem_kodu: int = 1
    key: int
    data: Dict[str, Any]


class DIADeleteRequest(BaseModel):
    """DIA silme request modeli"""
    firma_kodu: int
    donem_kodu: int = 1
    key: int


class DIABatchRequest(BaseModel):
    """DIA batch işlem request modeli"""
    firma_kodu: int
    donem_kodu: int = 1
    operation: str  # create/update/delete
    records: List[Dict[str, Any]]
    
    @validator('operation')
    def validate_operation(cls, v):
        allowed = ["create", "update", "delete"]
        if v not in allowed:
            raise ValueError(f'Operation {allowed} değerlerinden biri olmalı')
        return v


class DIASyncStats(BaseModel):
    """DIA sync istatistikleri"""
    total_records: int = 0
    synced_records: int = 0
    failed_records: int = 0
    last_sync_at: Optional[datetime] = None
    sync_duration_seconds: Optional[float] = None
    errors: List[str] = Field(default_factory=list)