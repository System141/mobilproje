"""
Base database models for Turkish Business Integration Platform
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr

from src.database import Base


class TimestampMixin:
    """Mixin for adding timestamp fields"""
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow, 
        nullable=False
    )


class TenantAwareModel(Base, TimestampMixin):
    """
    Base model for tenant-aware entities with KVKK compliance
    
    All tenant data must inherit from this class to ensure:
    1. Multi-tenant isolation via tenant_id
    2. KVKK compliance tracking
    3. Audit trail capabilities
    """
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # KVKK Compliance fields
    data_subject_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    legal_basis = Column(String(50), nullable=True)  # consent, contract, legal_obligation, etc.
    data_category = Column(String(100), nullable=True)  # personal, sensitive, financial, etc.
    retention_until = Column(DateTime, nullable=True)  # Auto-deletion date per KVKK
    
    # Audit fields
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete
    deleted_by = Column(UUID(as_uuid=True), nullable=True)
    
    # Anonymization flag (for KVKK right to erasure)
    is_anonymized = Column(Boolean, default=False, nullable=False)
    anonymized_at = Column(DateTime, nullable=True)
    anonymized_by = Column(UUID(as_uuid=True), nullable=True)
    
    @declared_attr
    def __tablename__(cls):
        """Generate table name from class name"""
        return cls.__name__.lower()
    
    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def anonymize(self, anonymized_by: Optional[uuid.UUID] = None):
        """
        Anonymize record per KVKK requirements
        
        Args:
            anonymized_by: ID of user performing anonymization
        """
        self.is_anonymized = True
        self.anonymized_at = datetime.utcnow()
        self.anonymized_by = anonymized_by
        
        # Clear sensitive data (to be overridden by subclasses)
        self._anonymize_fields()
    
    def _anonymize_fields(self):
        """Override in subclasses to anonymize specific fields"""
        pass
    
    def soft_delete(self, deleted_by: Optional[uuid.UUID] = None):
        """
        Soft delete record
        
        Args:
            deleted_by: ID of user performing deletion
        """
        self.deleted_at = datetime.utcnow()
        self.deleted_by = deleted_by
    
    def is_deleted(self) -> bool:
        """Check if record is soft deleted"""
        return self.deleted_at is not None
    
    def is_expired(self) -> bool:
        """Check if data retention period has expired"""
        if not self.retention_until:
            return False
        return datetime.utcnow() > self.retention_until


class SystemModel(Base, TimestampMixin):
    """
    Base model for system-level entities (not tenant-specific)
    
    Used for tenant management, system configuration, etc.
    """
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Audit fields
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    
    @declared_attr
    def __tablename__(cls):
        """Generate table name from class name"""
        return f"sys_{cls.__name__.lower()}"
    
    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


class AuditLogModel(Base):
    """
    Audit log model for KVKK compliance
    
    This model tracks all data access and modifications
    """
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    # Event information
    event_type = Column(String(50), nullable=False)  # CREATE, READ, UPDATE, DELETE, EXPORT
    table_name = Column(String(100), nullable=False)
    record_id = Column(UUID(as_uuid=True), nullable=True)
    
    # User information
    user_id = Column(UUID(as_uuid=True), nullable=True)
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)
    
    # Request information
    ip_address = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=True)
    
    # Data information
    data_category = Column(String(100), nullable=True)
    legal_basis = Column(String(50), nullable=True)
    
    # Changes (for UPDATE events)
    old_values = Column(Text, nullable=True)  # JSON string
    new_values = Column(Text, nullable=True)  # JSON string
    
    # KVKK specific
    data_subject_id = Column(UUID(as_uuid=True), nullable=True)
    processing_purpose = Column(String(200), nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self) -> dict:
        """Convert audit log to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


class ConsentRecord(Base):
    """
    KVKK consent tracking model
    
    Tracks user consents for data processing
    """
    __tablename__ = "consent_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # Data subject information
    data_subject_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    data_subject_email = Column(String(255), nullable=True)
    
    # Consent information
    purpose = Column(String(200), nullable=False)  # marketing, analytics, etc.
    legal_basis = Column(String(50), nullable=False)  # explicit_consent, contract, etc.
    data_categories = Column(Text, nullable=False)  # JSON array of categories
    
    # Consent details
    consent_text = Column(Text, nullable=False)  # The exact consent text shown
    consent_version = Column(String(20), nullable=False, default="1.0")
    
    # Consent status
    is_given = Column(Boolean, nullable=False, default=True)
    given_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    withdrawn_at = Column(DateTime, nullable=True)
    
    # Retention
    retention_period = Column(String(50), nullable=False)  # "365 days", "until_withdrawal"
    expires_at = Column(DateTime, nullable=True)
    
    # Technical details
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    consent_method = Column(String(50), nullable=False)  # web_form, api, etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def is_active(self) -> bool:
        """Check if consent is currently active"""
        if not self.is_given:
            return False
        if self.withdrawn_at:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True
    
    def withdraw(self):
        """Withdraw consent"""
        self.is_given = False
        self.withdrawn_at = datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Convert consent record to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }