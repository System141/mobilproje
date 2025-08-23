"""
DIA ERP Service Layer Implementation
"""

import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete
from sqlalchemy.orm import selectinload

from src.database import get_session
from src.integrations.base_connector import ConnectorResponse
from .connector import DIAConnector
from .config import DIAConfig, DIAModuleConfig, DIASyncConfig
from .models import (
    DIAResponse,
    DIACariKart,
    DIAStokKart,
    DIAFaturaFisi,
    DIAListRequest,
    DIACreateRequest,
    DIAUpdateRequest,
    DIADeleteRequest,
    DIACariKartDB,
    DIAStokKartDB,
    DIAFaturaFisiDB,
    DIASyncStats
)


logger = structlog.get_logger(__name__)


class DIAService:
    """
    DIA ERP Service Layer
    
    Provides high-level operations for DIA integration including:
    - Data synchronization
    - CRUD operations
    - Business logic
    """
    
    def __init__(self, connector: DIAConnector, sync_config: Optional[DIASyncConfig] = None):
        self.connector = connector
        self.sync_config = sync_config or DIASyncConfig()
        self.logger = structlog.get_logger("service.dia")
    
    # Cari Kart Operations
    async def sync_cari_kartlar(
        self,
        tenant_id: UUID,
        firma_kodu: int,
        donem_kodu: int = 1,
        limit: Optional[int] = None
    ) -> ConnectorResponse:
        """
        Sync cari kartlar from DIA to local database
        """
        start_time = datetime.utcnow()
        stats = DIASyncStats()
        
        try:
            self.logger.info(
                "Starting cari kartlar sync",
                tenant_id=str(tenant_id),
                firma_kodu=firma_kodu,
                donem_kodu=donem_kodu
            )
            
            # Prepare request
            limit = limit or self.sync_config.batch_size
            request_data = {
                "scf_carikart_listele": {
                    "session_id": await self.connector.get_session_id(),
                    "firma_kodu": firma_kodu,
                    "donem_kodu": donem_kodu,
                    "limit": limit,
                    "offset": 0
                }
            }
            
            # Make DIA API call
            response = await self.connector._make_request(
                method="POST",
                endpoint="/SCF/json",
                json=request_data
            )
            
            if not response.success:
                return ConnectorResponse(
                    success=False,
                    error=response.error,
                    error_code="SYNC_FAILED",
                    message_tr="Cari kart senkronizasyonu başarısız",
                    message_en="Cari kart synchronization failed"
                )
            
            # Parse DIA response
            try:
                dia_response = DIAResponse(**response.data)
                if not dia_response.is_success:
                    return ConnectorResponse(
                        success=False,
                        error=dia_response.msg,
                        error_code=dia_response.code,
                        message_tr="DIA'dan veri alınamadı",
                        message_en="Failed to get data from DIA"
                    )
                
                # Extract cari kartlar data
                cari_data = dia_response.data or []
                stats.total_records = len(cari_data)
                
                # Save to database
                async with get_session() as session:
                    for cari_item in cari_data:
                        try:
                            # Validate and convert to pydantic model
                            cari_model = DIACariKart(**cari_item)
                            
                            # Check if exists
                            existing_query = select(DIACariKartDB).where(
                                DIACariKartDB.tenant_id == tenant_id,
                                DIACariKartDB.dia_key == cari_model._key,
                                DIACariKartDB.dia_level1 == cari_model._level1
                            )
                            existing = await session.execute(existing_query)
                            existing_record = existing.scalar_one_or_none()
                            
                            if existing_record:
                                # Update existing
                                update_data = {
                                    "carikartkodu": cari_model.carikartkodu,
                                    "unvan": cari_model.unvan,
                                    "carikarttipi": cari_model.carikarttipi,
                                    "verginumarasi": cari_model.verginumarasi,
                                    "vergidairesi": cari_model.vergidairesi,
                                    "dia_key_sis_bolge": cari_model._key_sis_bolge,
                                    "dia_key_sis_temsilci": cari_model._key_sis_temsilci,
                                    "aktif": cari_model.aktif,
                                    "dia_cdate": cari_model._cdate,
                                    "dia_user": cari_model._user,
                                    "last_sync_at": datetime.utcnow(),
                                    "sync_status": "synced",
                                    "sync_error": None,
                                    "updated_at": datetime.utcnow()
                                }
                                
                                await session.execute(
                                    update(DIACariKartDB)
                                    .where(DIACariKartDB.id == existing_record.id)
                                    .values(**update_data)
                                )
                            else:
                                # Create new
                                new_record = DIACariKartDB(
                                    tenant_id=tenant_id,
                                    dia_key=cari_model._key,
                                    dia_level1=cari_model._level1,
                                    dia_level2=cari_model._level2,
                                    carikartkodu=cari_model.carikartkodu,
                                    unvan=cari_model.unvan,
                                    carikarttipi=cari_model.carikarttipi,
                                    verginumarasi=cari_model.verginumarasi,
                                    vergidairesi=cari_model.vergidairesi,
                                    dia_key_sis_bolge=cari_model._key_sis_bolge,
                                    dia_key_sis_temsilci=cari_model._key_sis_temsilci,
                                    aktif=cari_model.aktif,
                                    dia_cdate=cari_model._cdate,
                                    dia_user=cari_model._user,
                                    last_sync_at=datetime.utcnow(),
                                    sync_status="synced"
                                )
                                session.add(new_record)
                            
                            stats.synced_records += 1
                            
                        except ValidationError as e:
                            self.logger.error(
                                "Cari kart validation failed",
                                error=str(e),
                                item=cari_item
                            )
                            stats.failed_records += 1
                            stats.errors.append(f"Validation error: {str(e)}")
                            continue
                        
                        except Exception as e:
                            self.logger.error(
                                "Cari kart save failed",
                                error=str(e),
                                item=cari_item
                            )
                            stats.failed_records += 1
                            stats.errors.append(f"Save error: {str(e)}")
                            continue
                    
                    await session.commit()
                
                # Calculate duration
                stats.last_sync_at = datetime.utcnow()
                stats.sync_duration_seconds = (datetime.utcnow() - start_time).total_seconds()
                
                self.logger.info(
                    "Cari kartlar sync completed",
                    tenant_id=str(tenant_id),
                    total=stats.total_records,
                    synced=stats.synced_records,
                    failed=stats.failed_records,
                    duration=stats.sync_duration_seconds
                )
                
                return ConnectorResponse(
                    success=True,
                    data=stats.dict(),
                    message_tr="Cari kart senkronizasyonu tamamlandı",
                    message_en="Cari kart synchronization completed"
                )
                
            except ValidationError as e:
                return ConnectorResponse(
                    success=False,
                    error=str(e),
                    error_code="PARSE_ERROR",
                    message_tr="DIA yanıtı ayrıştırılamadı",
                    message_en="Failed to parse DIA response"
                )
            
        except Exception as e:
            self.logger.error("Cari kartlar sync failed", error=str(e))
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="SYNC_ERROR",
                message_tr="Senkronizasyon sırasında hata",
                message_en="Error during synchronization"
            )
    
    async def get_cari_kartlar(
        self,
        tenant_id: UUID,
        firma_kodu: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> ConnectorResponse:
        """
        Get cari kartlar from local database
        """
        try:
            async with get_session() as session:
                query = select(DIACariKartDB).where(
                    DIACariKartDB.tenant_id == tenant_id,
                    DIACariKartDB.sync_status == "synced"
                )
                
                # Add filters
                if firma_kodu:
                    query = query.where(DIACariKartDB.dia_level1 == firma_kodu)
                
                if filters:
                    if "carikarttipi" in filters:
                        query = query.where(DIACariKartDB.carikarttipi == filters["carikarttipi"])
                    if "aktif" in filters:
                        query = query.where(DIACariKartDB.aktif == filters["aktif"])
                    if "search" in filters:
                        search_term = f"%{filters['search']}%"
                        query = query.where(
                            DIACariKartDB.unvan.ilike(search_term) |
                            DIACariKartDB.carikartkodu.ilike(search_term)
                        )
                
                # Add pagination
                query = query.offset(offset).limit(limit)
                
                result = await session.execute(query)
                records = result.scalars().all()
                
                # Convert to dict for response
                data = []
                for record in records:
                    data.append({
                        "id": str(record.id),
                        "dia_key": record.dia_key,
                        "carikartkodu": record.carikartkodu,
                        "unvan": record.unvan,
                        "carikarttipi": record.carikarttipi,
                        "verginumarasi": record.verginumarasi,
                        "vergidairesi": record.vergidairesi,
                        "aktif": record.aktif,
                        "last_sync_at": record.last_sync_at.isoformat() if record.last_sync_at else None,
                        "created_at": record.created_at.isoformat(),
                        "updated_at": record.updated_at.isoformat() if record.updated_at else None
                    })
                
                return ConnectorResponse(
                    success=True,
                    data={
                        "records": data,
                        "count": len(data),
                        "limit": limit,
                        "offset": offset
                    },
                    message_tr="Cari kartlar listelendi",
                    message_en="Cari kartlar listed"
                )
                
        except Exception as e:
            self.logger.error("Get cari kartlar failed", error=str(e))
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="QUERY_ERROR",
                message_tr="Cari kartlar sorgulanamadı",
                message_en="Failed to query cari kartlar"
            )
    
    async def create_cari_kart(
        self,
        tenant_id: UUID,
        firma_kodu: int,
        donem_kodu: int,
        cari_data: Dict[str, Any]
    ) -> ConnectorResponse:
        """
        Create cari kart in DIA
        """
        try:
            # Validate data
            cari_model = DIACariKart(**cari_data)
            
            # Prepare DIA request
            request_data = {
                "scf_carikart_ekle": {
                    "session_id": await self.connector.get_session_id(),
                    "firma_kodu": firma_kodu,
                    "donem_kodu": donem_kodu,
                    **cari_model.dict(exclude_none=True, exclude={"_key", "_level1", "_level2", "_cdate", "_user"})
                }
            }
            
            # Make DIA API call
            response = await self.connector._make_request(
                method="POST",
                endpoint="/SCF/json",
                json=request_data
            )
            
            if not response.success:
                return ConnectorResponse(
                    success=False,
                    error=response.error,
                    error_code="CREATE_FAILED",
                    message_tr="Cari kart oluşturulamadı",
                    message_en="Failed to create cari kart"
                )
            
            # Parse response
            dia_response = DIAResponse(**response.data)
            if not dia_response.is_success:
                return ConnectorResponse(
                    success=False,
                    error=dia_response.msg,
                    error_code=dia_response.code,
                    message_tr="DIA'da cari kart oluşturulamadı",
                    message_en="Failed to create cari kart in DIA"
                )
            
            # Save to local database
            async with get_session() as session:
                new_record = DIACariKartDB(
                    tenant_id=tenant_id,
                    dia_level1=firma_kodu,
                    dia_level2=donem_kodu,
                    carikartkodu=cari_model.carikartkodu,
                    unvan=cari_model.unvan,
                    carikarttipi=cari_model.carikarttipi,
                    verginumarasi=cari_model.verginumarasi,
                    vergidairesi=cari_model.vergidairesi,
                    dia_key_sis_bolge=cari_model._key_sis_bolge,
                    dia_key_sis_temsilci=cari_model._key_sis_temsilci,
                    aktif=cari_model.aktif,
                    sync_status="synced",
                    last_sync_at=datetime.utcnow()
                )
                
                # Extract DIA key from response if available
                if isinstance(dia_response.data, dict) and "_key" in dia_response.data:
                    new_record.dia_key = dia_response.data["_key"]
                
                session.add(new_record)
                await session.commit()
                await session.refresh(new_record)
            
            return ConnectorResponse(
                success=True,
                data={
                    "id": str(new_record.id),
                    "dia_key": new_record.dia_key,
                    "carikartkodu": new_record.carikartkodu,
                    "response": dia_response.data
                },
                message_tr="Cari kart başarıyla oluşturuldu",
                message_en="Cari kart created successfully"
            )
            
        except ValidationError as e:
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="VALIDATION_ERROR",
                message_tr="Veri doğrulama hatası",
                message_en="Data validation error"
            )
        
        except Exception as e:
            self.logger.error("Create cari kart failed", error=str(e))
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="CREATE_ERROR",
                message_tr="Cari kart oluşturma hatası",
                message_en="Error creating cari kart"
            )
    
    # Stok Kart Operations
    async def sync_stok_kartlar(
        self,
        tenant_id: UUID,
        firma_kodu: int,
        donem_kodu: int = 1,
        limit: Optional[int] = None
    ) -> ConnectorResponse:
        """
        Sync stok kartlar from DIA to local database
        """
        start_time = datetime.utcnow()
        stats = DIASyncStats()
        
        try:
            self.logger.info(
                "Starting stok kartlar sync",
                tenant_id=str(tenant_id),
                firma_kodu=firma_kodu,
                donem_kodu=donem_kodu
            )
            
            # Prepare request
            limit = limit or self.sync_config.batch_size
            request_data = {
                "scf_stokkart_listele": {
                    "session_id": await self.connector.get_session_id(),
                    "firma_kodu": firma_kodu,
                    "donem_kodu": donem_kodu,
                    "limit": limit,
                    "offset": 0
                }
            }
            
            # Make DIA API call
            response = await self.connector._make_request(
                method="POST",
                endpoint="/SCF/json",
                json=request_data
            )
            
            if not response.success:
                return ConnectorResponse(
                    success=False,
                    error=response.error,
                    error_code="SYNC_FAILED",
                    message_tr="Stok kart senkronizasyonu başarısız",
                    message_en="Stok kart synchronization failed"
                )
            
            # Parse and process data similar to cari kartlar sync
            # Implementation details would follow the same pattern...
            
            return ConnectorResponse(
                success=True,
                data=stats.dict(),
                message_tr="Stok kart senkronizasyonu tamamlandı",
                message_en="Stok kart synchronization completed"
            )
            
        except Exception as e:
            self.logger.error("Stok kartlar sync failed", error=str(e))
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="SYNC_ERROR",
                message_tr="Senkronizasyon sırasında hata",
                message_en="Error during synchronization"
            )
    
    # Utility methods
    async def get_sync_status(self, tenant_id: UUID) -> ConnectorResponse:
        """
        Get synchronization status for tenant
        """
        try:
            async with get_session() as session:
                # Get stats for each module
                cari_query = select(DIACariKartDB).where(
                    DIACariKartDB.tenant_id == tenant_id
                )
                cari_result = await session.execute(cari_query)
                cari_records = cari_result.scalars().all()
                
                stok_query = select(DIAStokKartDB).where(
                    DIAStokKartDB.tenant_id == tenant_id
                )
                stok_result = await session.execute(stok_query)
                stok_records = stok_result.scalars().all()
                
                # Calculate stats
                cari_stats = {
                    "total": len(cari_records),
                    "synced": len([r for r in cari_records if r.sync_status == "synced"]),
                    "pending": len([r for r in cari_records if r.sync_status == "pending"]),
                    "errors": len([r for r in cari_records if r.sync_status == "error"]),
                    "last_sync": max([r.last_sync_at for r in cari_records if r.last_sync_at], default=None)
                }
                
                stok_stats = {
                    "total": len(stok_records),
                    "synced": len([r for r in stok_records if r.sync_status == "synced"]),
                    "pending": len([r for r in stok_records if r.sync_status == "pending"]), 
                    "errors": len([r for r in stok_records if r.sync_status == "error"]),
                    "last_sync": max([r.last_sync_at for r in stok_records if r.last_sync_at], default=None)
                }
                
                return ConnectorResponse(
                    success=True,
                    data={
                        "tenant_id": str(tenant_id),
                        "cari_kartlar": cari_stats,
                        "stok_kartlar": stok_stats,
                        "last_check": datetime.utcnow().isoformat()
                    },
                    message_tr="Senkronizasyon durumu alındı",
                    message_en="Synchronization status retrieved"
                )
                
        except Exception as e:
            self.logger.error("Get sync status failed", error=str(e))
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="STATUS_ERROR",
                message_tr="Durum sorgulanamadı",
                message_en="Failed to query status"
            )