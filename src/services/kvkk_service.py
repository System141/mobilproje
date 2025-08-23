"""
KVKK Compliance Service for Turkish Business Integration Platform

This service provides KVKK (Turkish Data Protection Law) compliance features:
- Consent management
- Data export (right to portability)
- Data anonymization (right to erasure)
- Audit logging
- Data retention management
"""

import json
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import uuid
import tempfile

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, text
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field, validator
import structlog

from src.database import get_session
from src.models.base import AuditLogModel, ConsentRecord, TenantAwareModel
from src.models.tenant import Tenant, User
from src.core.security import get_current_user

logger = structlog.get_logger(__name__)


class ConsentRequest(BaseModel):
    """Request to record user consent"""
    
    data_subject_id: uuid.UUID
    purpose: str = Field(..., max_length=200)
    legal_basis: str = Field(..., max_length=50)
    data_categories: List[str] = Field(..., min_items=1)
    consent_text: str = Field(..., min_length=10)
    consent_version: str = Field(default="1.0", max_length=20)
    retention_period: str = Field(..., max_length=50)
    expires_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    consent_method: str = Field(default="web_form", max_length=50)

    @validator('legal_basis')
    def validate_legal_basis(cls, v):
        valid_bases = [
            'explicit_consent', 'contract', 'legal_obligation', 
            'vital_interests', 'public_task', 'legitimate_interests'
        ]
        if v not in valid_bases:
            raise ValueError(f'Legal basis must be one of: {valid_bases}')
        return v

    @validator('purpose')
    def validate_purpose(cls, v):
        valid_purposes = [
            'marketing', 'analytics', 'customer_service', 'billing',
            'product_development', 'security', 'legal_compliance',
            'communication', 'personalization'
        ]
        if v not in valid_purposes:
            raise ValueError(f'Purpose must be one of: {valid_purposes}')
        return v


class DataExportRequest(BaseModel):
    """Request to export user data"""
    
    data_subject_id: uuid.UUID
    email: str = Field(..., max_length=255)
    export_format: str = Field(default="json", regex="^(json|csv|xml)$")
    include_audit_logs: bool = Field(default=True)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class AnonymizationRequest(BaseModel):
    """Request to anonymize user data"""
    
    data_subject_id: uuid.UUID
    reason: str = Field(..., max_length=500)
    tables_to_anonymize: Optional[List[str]] = None
    confirm_deletion: bool = Field(default=False)


class KVKKService:
    """KVKK Compliance Service"""
    
    def __init__(self):
        self.logger = structlog.get_logger("kvkk_service")
    
    async def record_consent(
        self, 
        tenant_id: uuid.UUID,
        consent_request: ConsentRequest
    ) -> Dict[str, Any]:
        """
        Record user consent for data processing
        
        Args:
            tenant_id: Tenant ID
            consent_request: Consent details
            
        Returns:
            Dict with consent record details
        """
        async with get_session() as session:
            try:
                # Check if consent already exists
                existing_consent = await session.execute(
                    select(ConsentRecord)
                    .where(
                        ConsentRecord.tenant_id == tenant_id,
                        ConsentRecord.data_subject_id == consent_request.data_subject_id,
                        ConsentRecord.purpose == consent_request.purpose,
                        ConsentRecord.is_given == True
                    )
                )
                
                existing = existing_consent.scalar_one_or_none()
                
                if existing and existing.is_active():
                    return {
                        "success": False,
                        "message": "Bu amaç için aktif bir onay zaten mevcut",
                        "message_en": "Active consent already exists for this purpose",
                        "consent_id": str(existing.id)
                    }
                
                # Create new consent record
                consent = ConsentRecord(
                    tenant_id=tenant_id,
                    data_subject_id=consent_request.data_subject_id,
                    data_subject_email=consent_request.data_subject_email,
                    purpose=consent_request.purpose,
                    legal_basis=consent_request.legal_basis,
                    data_categories=json.dumps(consent_request.data_categories),
                    consent_text=consent_request.consent_text,
                    consent_version=consent_request.consent_version,
                    retention_period=consent_request.retention_period,
                    expires_at=consent_request.expires_at,
                    ip_address=consent_request.ip_address,
                    user_agent=consent_request.user_agent,
                    consent_method=consent_request.consent_method
                )
                
                session.add(consent)
                await session.commit()
                await session.refresh(consent)
                
                # Log consent recording
                await self._log_audit_event(
                    session=session,
                    tenant_id=tenant_id,
                    event_type="CONSENT_GIVEN",
                    table_name="consent_records",
                    record_id=consent.id,
                    data_subject_id=consent_request.data_subject_id,
                    processing_purpose=consent_request.purpose,
                    legal_basis=consent_request.legal_basis,
                    ip_address=consent_request.ip_address,
                    user_agent=consent_request.user_agent
                )
                
                self.logger.info(
                    "Consent recorded",
                    tenant_id=str(tenant_id),
                    data_subject_id=str(consent_request.data_subject_id),
                    purpose=consent_request.purpose,
                    consent_id=str(consent.id)
                )
                
                return {
                    "success": True,
                    "message": "Onay başarıyla kaydedildi",
                    "message_en": "Consent recorded successfully",
                    "consent_id": str(consent.id),
                    "expires_at": consent.expires_at.isoformat() if consent.expires_at else None
                }
                
            except Exception as e:
                await session.rollback()
                self.logger.error("Failed to record consent", error=str(e))
                return {
                    "success": False,
                    "message": "Onay kaydedilemedi",
                    "message_en": f"Failed to record consent: {str(e)}"
                }
    
    async def withdraw_consent(
        self,
        tenant_id: uuid.UUID,
        data_subject_id: uuid.UUID,
        purpose: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Withdraw user consent
        
        Args:
            tenant_id: Tenant ID
            data_subject_id: Data subject ID
            purpose: Consent purpose
            reason: Withdrawal reason
            ip_address: User IP address
            user_agent: User agent
            
        Returns:
            Dict with withdrawal result
        """
        async with get_session() as session:
            try:
                # Find active consent
                result = await session.execute(
                    select(ConsentRecord)
                    .where(
                        ConsentRecord.tenant_id == tenant_id,
                        ConsentRecord.data_subject_id == data_subject_id,
                        ConsentRecord.purpose == purpose,
                        ConsentRecord.is_given == True,
                        ConsentRecord.withdrawn_at.is_(None)
                    )
                )
                
                consent = result.scalar_one_or_none()
                if not consent:
                    return {
                        "success": False,
                        "message": "Geri çekilecek aktif onay bulunamadı",
                        "message_en": "No active consent found to withdraw"
                    }
                
                # Withdraw consent
                consent.withdraw()
                await session.commit()
                
                # Log withdrawal
                await self._log_audit_event(
                    session=session,
                    tenant_id=tenant_id,
                    event_type="CONSENT_WITHDRAWN",
                    table_name="consent_records",
                    record_id=consent.id,
                    data_subject_id=data_subject_id,
                    processing_purpose=purpose,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    old_values=json.dumps({"is_given": True}),
                    new_values=json.dumps({"is_given": False, "withdrawn_at": datetime.utcnow().isoformat()})
                )
                
                self.logger.info(
                    "Consent withdrawn",
                    tenant_id=str(tenant_id),
                    data_subject_id=str(data_subject_id),
                    purpose=purpose,
                    consent_id=str(consent.id)
                )
                
                return {
                    "success": True,
                    "message": "Onay başarıyla geri çekildi",
                    "message_en": "Consent withdrawn successfully",
                    "consent_id": str(consent.id)
                }
                
            except Exception as e:
                await session.rollback()
                self.logger.error("Failed to withdraw consent", error=str(e))
                return {
                    "success": False,
                    "message": "Onay geri çekilemedi",
                    "message_en": f"Failed to withdraw consent: {str(e)}"
                }
    
    async def export_user_data(
        self,
        tenant_id: uuid.UUID,
        export_request: DataExportRequest
    ) -> Dict[str, Any]:
        """
        Export all user data (KVKK right to portability)
        
        Args:
            tenant_id: Tenant ID
            export_request: Export parameters
            
        Returns:
            Dict with export file path and metadata
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                export_dir = Path(temp_dir) / "kvkk_export"
                export_dir.mkdir()
                
                async with get_session() as session:
                    # Export user data from all tenant-aware tables
                    export_data = {}
                    
                    # Get all models that inherit from TenantAwareModel
                    tenant_aware_models = self._get_tenant_aware_models()
                    
                    for model_class in tenant_aware_models:
                        table_name = model_class.__tablename__
                        
                        # Query data for this user
                        query = select(model_class).where(
                            model_class.tenant_id == tenant_id,
                            model_class.data_subject_id == export_request.data_subject_id
                        )
                        
                        # Apply date filters if provided
                        if export_request.date_from:
                            query = query.where(model_class.created_at >= export_request.date_from)
                        if export_request.date_to:
                            query = query.where(model_class.created_at <= export_request.date_to)
                        
                        result = await session.execute(query)
                        records = result.scalars().all()
                        
                        if records:
                            export_data[table_name] = [
                                self._sanitize_export_data(record.to_dict()) 
                                for record in records
                            ]
                    
                    # Export consent records
                    consents_result = await session.execute(
                        select(ConsentRecord)
                        .where(
                            ConsentRecord.tenant_id == tenant_id,
                            ConsentRecord.data_subject_id == export_request.data_subject_id
                        )
                    )
                    consent_records = consents_result.scalars().all()
                    
                    if consent_records:
                        export_data["consent_records"] = [
                            self._sanitize_export_data(record.to_dict())
                            for record in consent_records
                        ]
                    
                    # Export audit logs if requested
                    if export_request.include_audit_logs:
                        audit_result = await session.execute(
                            select(AuditLogModel)
                            .where(
                                AuditLogModel.tenant_id == tenant_id,
                                AuditLogModel.data_subject_id == export_request.data_subject_id
                            )
                        )
                        audit_logs = audit_result.scalars().all()
                        
                        if audit_logs:
                            export_data["audit_logs"] = [
                                self._sanitize_export_data(log.to_dict())
                                for log in audit_logs
                            ]
                    
                    # Create export file
                    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    
                    if export_request.export_format == "json":
                        export_file = export_dir / f"data_export_{timestamp}.json"
                        with open(export_file, 'w', encoding='utf-8') as f:
                            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
                    
                    elif export_request.export_format == "csv":
                        # Create separate CSV files for each table
                        import csv
                        csv_files = []
                        
                        for table_name, records in export_data.items():
                            if records:
                                csv_file = export_dir / f"{table_name}_{timestamp}.csv"
                                csv_files.append(csv_file)
                                
                                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                                    if records:
                                        writer = csv.DictWriter(f, fieldnames=records[0].keys())
                                        writer.writeheader()
                                        writer.writerows(records)
                        
                        export_file = export_dir / f"data_export_{timestamp}.csv"
                    
                    # Create ZIP archive
                    zip_file = Path(temp_dir) / f"kvkk_export_{timestamp}.zip"
                    
                    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for file in export_dir.rglob("*"):
                            if file.is_file():
                                zf.write(file, file.relative_to(export_dir))
                    
                    # Log export
                    await self._log_audit_event(
                        session=session,
                        tenant_id=tenant_id,
                        event_type="DATA_EXPORT",
                        table_name="multiple",
                        data_subject_id=export_request.data_subject_id,
                        processing_purpose="data_portability"
                    )
                    
                    # Move to permanent location (implement based on your storage strategy)
                    permanent_path = f"/tmp/{zip_file.name}"  # This should be configurable
                    
                    self.logger.info(
                        "Data exported",
                        tenant_id=str(tenant_id),
                        data_subject_id=str(export_request.data_subject_id),
                        export_format=export_request.export_format,
                        file_path=permanent_path
                    )
                    
                    return {
                        "success": True,
                        "message": "Veri dışa aktarımı tamamlandı",
                        "message_en": "Data export completed",
                        "export_file": permanent_path,
                        "export_format": export_request.export_format,
                        "record_count": sum(len(records) for records in export_data.values()),
                        "tables_exported": list(export_data.keys()),
                        "export_date": datetime.utcnow().isoformat()
                    }
                    
        except Exception as e:
            self.logger.error("Data export failed", error=str(e))
            return {
                "success": False,
                "message": "Veri dışa aktarımı başarısız",
                "message_en": f"Data export failed: {str(e)}"
            }
    
    async def anonymize_user_data(
        self,
        tenant_id: uuid.UUID,
        anonymization_request: AnonymizationRequest,
        performed_by: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """
        Anonymize user data (KVKK right to erasure)
        
        Args:
            tenant_id: Tenant ID
            anonymization_request: Anonymization parameters
            performed_by: ID of user performing anonymization
            
        Returns:
            Dict with anonymization result
        """
        if not anonymization_request.confirm_deletion:
            return {
                "success": False,
                "message": "Silme onayı gerekli",
                "message_en": "Deletion confirmation required"
            }
        
        async with get_session() as session:
            try:
                anonymized_tables = []
                anonymized_records = 0
                
                # Get models to anonymize
                if anonymization_request.tables_to_anonymize:
                    # Specific tables requested
                    models_to_anonymize = [
                        model for model in self._get_tenant_aware_models()
                        if model.__tablename__ in anonymization_request.tables_to_anonymize
                    ]
                else:
                    # All tenant-aware models
                    models_to_anonymize = self._get_tenant_aware_models()
                
                for model_class in models_to_anonymize:
                    # Find records to anonymize
                    result = await session.execute(
                        select(model_class)
                        .where(
                            model_class.tenant_id == tenant_id,
                            model_class.data_subject_id == anonymization_request.data_subject_id,
                            model_class.is_anonymized == False
                        )
                    )
                    
                    records = result.scalars().all()
                    
                    for record in records:
                        # Anonymize the record
                        record.anonymize(performed_by)
                        anonymized_records += 1
                    
                    if records:
                        anonymized_tables.append(model_class.__tablename__)
                
                # Anonymize consent records
                consent_result = await session.execute(
                    select(ConsentRecord)
                    .where(
                        ConsentRecord.tenant_id == tenant_id,
                        ConsentRecord.data_subject_id == anonymization_request.data_subject_id
                    )
                )
                
                consent_records = consent_result.scalars().all()
                for consent in consent_records:
                    consent.data_subject_email = "anonymized@example.com"
                    consent.ip_address = "0.0.0.0"
                    consent.user_agent = "anonymized"
                    anonymized_records += 1
                
                if consent_records:
                    anonymized_tables.append("consent_records")
                
                await session.commit()
                
                # Log anonymization
                await self._log_audit_event(
                    session=session,
                    tenant_id=tenant_id,
                    event_type="DATA_ANONYMIZED",
                    table_name="multiple",
                    data_subject_id=anonymization_request.data_subject_id,
                    processing_purpose="data_erasure",
                    user_id=performed_by,
                    new_values=json.dumps({
                        "reason": anonymization_request.reason,
                        "anonymized_tables": anonymized_tables,
                        "anonymized_records": anonymized_records
                    })
                )
                
                self.logger.info(
                    "Data anonymized",
                    tenant_id=str(tenant_id),
                    data_subject_id=str(anonymization_request.data_subject_id),
                    tables=anonymized_tables,
                    record_count=anonymized_records
                )
                
                return {
                    "success": True,
                    "message": f"{anonymized_records} kayıt anonimleştirildi",
                    "message_en": f"{anonymized_records} records anonymized",
                    "anonymized_tables": anonymized_tables,
                    "anonymized_records": anonymized_records,
                    "anonymization_date": datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                await session.rollback()
                self.logger.error("Data anonymization failed", error=str(e))
                return {
                    "success": False,
                    "message": "Veri anonimleştirme başarısız",
                    "message_en": f"Data anonymization failed: {str(e)}"
                }
    
    async def get_user_consents(
        self,
        tenant_id: uuid.UUID,
        data_subject_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get all consents for a data subject
        
        Args:
            tenant_id: Tenant ID
            data_subject_id: Data subject ID
            
        Returns:
            Dict with consent list
        """
        async with get_session() as session:
            try:
                result = await session.execute(
                    select(ConsentRecord)
                    .where(
                        ConsentRecord.tenant_id == tenant_id,
                        ConsentRecord.data_subject_id == data_subject_id
                    )
                    .order_by(ConsentRecord.created_at.desc())
                )
                
                consents = result.scalars().all()
                
                consent_list = []
                for consent in consents:
                    consent_dict = consent.to_dict()
                    consent_dict['is_active'] = consent.is_active()
                    consent_dict['data_categories'] = json.loads(consent_dict.get('data_categories', '[]'))
                    consent_list.append(consent_dict)
                
                return {
                    "success": True,
                    "consents": consent_list,
                    "total_consents": len(consent_list),
                    "active_consents": len([c for c in consent_list if c['is_active']])
                }
                
            except Exception as e:
                self.logger.error("Failed to get user consents", error=str(e))
                return {
                    "success": False,
                    "message": "Onaylar alınamadı",
                    "message_en": f"Failed to get consents: {str(e)}"
                }
    
    async def clean_expired_data(self, tenant_id: uuid.UUID) -> Dict[str, Any]:
        """
        Clean expired data per KVKK retention requirements
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Dict with cleanup results
        """
        async with get_session() as session:
            try:
                cleaned_records = 0
                cleaned_tables = []
                
                # Clean expired records from all tenant-aware models
                for model_class in self._get_tenant_aware_models():
                    result = await session.execute(
                        select(model_class)
                        .where(
                            model_class.tenant_id == tenant_id,
                            model_class.retention_until.isnot(None),
                            model_class.retention_until <= datetime.utcnow(),
                            model_class.is_anonymized == False
                        )
                    )
                    
                    expired_records = result.scalars().all()
                    
                    for record in expired_records:
                        record.anonymize()
                        cleaned_records += 1
                    
                    if expired_records:
                        cleaned_tables.append(model_class.__tablename__)
                
                await session.commit()
                
                if cleaned_records > 0:
                    # Log cleanup
                    await self._log_audit_event(
                        session=session,
                        tenant_id=tenant_id,
                        event_type="DATA_CLEANUP",
                        table_name="multiple",
                        processing_purpose="retention_compliance",
                        new_values=json.dumps({
                            "cleaned_tables": cleaned_tables,
                            "cleaned_records": cleaned_records
                        })
                    )
                
                self.logger.info(
                    "Expired data cleaned",
                    tenant_id=str(tenant_id),
                    cleaned_records=cleaned_records,
                    cleaned_tables=cleaned_tables
                )
                
                return {
                    "success": True,
                    "message": f"{cleaned_records} süresi dolmuş kayıt temizlendi",
                    "message_en": f"{cleaned_records} expired records cleaned",
                    "cleaned_records": cleaned_records,
                    "cleaned_tables": cleaned_tables
                }
                
            except Exception as e:
                await session.rollback()
                self.logger.error("Data cleanup failed", error=str(e))
                return {
                    "success": False,
                    "message": "Veri temizleme başarısız",
                    "message_en": f"Data cleanup failed: {str(e)}"
                }
    
    async def _log_audit_event(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        event_type: str,
        table_name: str,
        record_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        user_email: Optional[str] = None,
        user_role: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        data_category: Optional[str] = None,
        legal_basis: Optional[str] = None,
        data_subject_id: Optional[uuid.UUID] = None,
        processing_purpose: Optional[str] = None,
        old_values: Optional[str] = None,
        new_values: Optional[str] = None
    ):
        """Log audit event for KVKK compliance"""
        
        audit_log = AuditLogModel(
            tenant_id=tenant_id,
            event_type=event_type,
            table_name=table_name,
            record_id=record_id,
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            data_category=data_category,
            legal_basis=legal_basis,
            data_subject_id=data_subject_id,
            processing_purpose=processing_purpose,
            old_values=old_values,
            new_values=new_values,
            request_id=str(uuid.uuid4())
        )
        
        session.add(audit_log)
    
    def _get_tenant_aware_models(self):
        """Get all models that inherit from TenantAwareModel"""
        # This would return all registered models that inherit from TenantAwareModel
        # Implementation depends on your model registry
        from src.models.tenant import User, Tenant  # Import your models here
        
        return [User]  # Add all your tenant-aware models here
    
    def _sanitize_export_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize data for export by removing internal fields
        and converting timestamps to ISO format
        """
        # Remove internal fields
        fields_to_remove = [
            'deleted_at', 'deleted_by', 'anonymized_at', 'anonymized_by'
        ]
        
        sanitized = {
            k: v for k, v in data.items() 
            if k not in fields_to_remove
        }
        
        # Convert datetime objects to ISO strings
        for key, value in sanitized.items():
            if isinstance(value, datetime):
                sanitized[key] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                sanitized[key] = str(value)
        
        return sanitized


# Service instance
kvkk_service = KVKKService()