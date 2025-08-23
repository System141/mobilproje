"""
Tenant management service for Turkish Business Integration Platform
"""

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_
from sqlalchemy.exc import IntegrityError
import structlog

from src.models.tenant import Tenant, TenantPlan, TenantStatus
from src.models.base import AuditLogModel
from src.database import get_admin_db
from src.core.security import TokenService
from src.utils.turkish import format_turkish_currency

logger = structlog.get_logger(__name__)


class TenantServiceError(Exception):
    """Base tenant service exception"""
    pass


class TenantNotFoundError(TenantServiceError):
    """Tenant not found"""
    pass


class TenantAlreadyExistsError(TenantServiceError):
    """Tenant already exists"""
    pass


class TenantQuotaExceededError(TenantServiceError):
    """Tenant quota exceeded"""
    pass


class TenantService:
    """
    Tenant management service for multi-tenant SaaS platform
    
    Handles:
    - Tenant registration and onboarding
    - Subscription management 
    - Usage tracking and quota enforcement
    - Turkish business compliance
    - Trial management
    """
    
    def __init__(self):
        self.logger = logger.bind(service="tenant_service")
    
    async def create_tenant(
        self,
        tenant_data: Dict[str, Any],
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create new tenant with Turkish business validation
        
        Args:
            tenant_data: Tenant information
            created_by: ID of user creating tenant
            
        Returns:
            Dict[str, Any]: Created tenant data
            
        Raises:
            TenantAlreadyExistsError: If tenant already exists
            TenantServiceError: If creation fails
        """
        async with get_admin_db() as db:
            try:
                # Validate subdomain
                subdomain = tenant_data.get("subdomain", "").lower()
                if not self._validate_subdomain(subdomain):
                    raise TenantServiceError(
                        "Geçersiz subdomain. Sadece harf, rakam ve tire kullanabilirsiniz"
                    )
                
                # Check if subdomain already exists
                existing = await db.execute(
                    select(Tenant).where(Tenant.subdomain == subdomain)
                )
                if existing.scalar_one_or_none():
                    raise TenantAlreadyExistsError(f"Subdomain '{subdomain}' zaten kullanılıyor")
                
                # Validate Turkish business data if provided
                if tenant_data.get("tax_number"):
                    if not self._validate_turkish_tax_number(tenant_data["tax_number"]):
                        raise TenantServiceError("Geçersiz vergi numarası formatı")
                
                # Create tenant
                tenant = Tenant(
                    name=tenant_data["name"],
                    subdomain=subdomain,
                    email=tenant_data["email"],
                    phone=tenant_data.get("phone"),
                    address=tenant_data.get("address"),
                    city=tenant_data.get("city"),
                    
                    # Turkish business info
                    tax_number=tenant_data.get("tax_number"),
                    tax_office=tenant_data.get("tax_office"),
                    trade_registry_number=tenant_data.get("trade_registry_number"),
                    mersis_number=tenant_data.get("mersis_number"),
                    
                    # Start with trial
                    plan=TenantPlan.TRIAL,
                    status=TenantStatus.ACTIVE,
                    is_trial=True,
                    trial_ends_at=datetime.utcnow() + timedelta(days=14),
                    
                    # Onboarding
                    onboarding_step="welcome",
                    
                    created_by=created_by
                )
                
                db.add(tenant)
                await db.commit()
                await db.refresh(tenant)
                
                # Log tenant creation
                await self._log_tenant_event(
                    db, tenant.id, "TENANT_CREATED", 
                    {"subdomain": subdomain}, created_by
                )
                
                self.logger.info(
                    "Tenant created",
                    tenant_id=str(tenant.id),
                    subdomain=subdomain,
                    plan=tenant.plan.value
                )
                
                return tenant.to_dict()
                
            except IntegrityError as e:
                await db.rollback()
                if "subdomain" in str(e):
                    raise TenantAlreadyExistsError(f"Subdomain '{subdomain}' zaten kullanılıyor")
                raise TenantServiceError(f"Tenant oluşturulamadı: {str(e)}")
            
            except Exception as e:
                await db.rollback()
                self.logger.error("Tenant creation failed", error=str(e))
                raise TenantServiceError(f"Tenant oluşturulamadı: {str(e)}")
    
    async def get_tenant(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get tenant by ID
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            Dict[str, Any]: Tenant data
            
        Raises:
            TenantNotFoundError: If tenant not found
        """
        async with get_admin_db() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                raise TenantNotFoundError(f"Tenant bulunamadı: {tenant_id}")
            
            return tenant.to_dict()
    
    async def get_tenant_by_subdomain(self, subdomain: str) -> Optional[Dict[str, Any]]:
        """
        Get tenant by subdomain
        
        Args:
            subdomain: Tenant subdomain
            
        Returns:
            Optional[Dict[str, Any]]: Tenant data or None
        """
        async with get_admin_db() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.subdomain == subdomain.lower())
            )
            tenant = result.scalar_one_or_none()
            
            return tenant.to_dict() if tenant else None
    
    async def get_tenant_id_by_subdomain(self, subdomain: str) -> Optional[str]:
        """
        Get tenant ID by subdomain (for middleware)
        
        Args:
            subdomain: Tenant subdomain
            
        Returns:
            Optional[str]: Tenant ID or None
        """
        tenant = await self.get_tenant_by_subdomain(subdomain)
        return str(tenant["id"]) if tenant else None
    
    async def get_tenant_info(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tenant info for middleware context
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            Optional[Dict[str, Any]]: Tenant info or None
        """
        try:
            return await self.get_tenant(tenant_id)
        except TenantNotFoundError:
            return None
    
    async def update_tenant(
        self,
        tenant_id: str,
        update_data: Dict[str, Any],
        updated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update tenant information
        
        Args:
            tenant_id: Tenant UUID
            update_data: Fields to update
            updated_by: ID of user making update
            
        Returns:
            Dict[str, Any]: Updated tenant data
        """
        async with get_admin_db() as db:
            # Get existing tenant
            result = await db.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                raise TenantNotFoundError(f"Tenant bulunamadı: {tenant_id}")
            
            # Validate updates
            if "subdomain" in update_data:
                new_subdomain = update_data["subdomain"].lower()
                if new_subdomain != tenant.subdomain:
                    if not self._validate_subdomain(new_subdomain):
                        raise TenantServiceError("Geçersiz subdomain formatı")
                    
                    # Check if new subdomain is available
                    existing = await db.execute(
                        select(Tenant).where(
                            and_(
                                Tenant.subdomain == new_subdomain,
                                Tenant.id != tenant_id
                            )
                        )
                    )
                    if existing.scalar_one_or_none():
                        raise TenantAlreadyExistsError(f"Subdomain '{new_subdomain}' zaten kullanılıyor")
            
            if "tax_number" in update_data and update_data["tax_number"]:
                if not self._validate_turkish_tax_number(update_data["tax_number"]):
                    raise TenantServiceError("Geçersiz vergi numarası formatı")
            
            # Apply updates
            for field, value in update_data.items():
                if hasattr(tenant, field):
                    setattr(tenant, field, value)
            
            tenant.updated_by = updated_by
            
            await db.commit()
            await db.refresh(tenant)
            
            # Log update
            await self._log_tenant_event(
                db, tenant_id, "TENANT_UPDATED", 
                {"fields": list(update_data.keys())}, updated_by
            )
            
            self.logger.info(
                "Tenant updated",
                tenant_id=tenant_id,
                fields=list(update_data.keys())
            )
            
            return tenant.to_dict()
    
    async def upgrade_tenant_plan(
        self,
        tenant_id: str,
        new_plan: TenantPlan,
        updated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upgrade tenant subscription plan
        
        Args:
            tenant_id: Tenant UUID
            new_plan: New subscription plan
            updated_by: ID of user making change
            
        Returns:
            Dict[str, Any]: Updated tenant data
        """
        async with get_admin_db() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                raise TenantNotFoundError(f"Tenant bulunamadı: {tenant_id}")
            
            old_plan = tenant.plan
            success = tenant.upgrade_plan(new_plan)
            
            if not success:
                raise TenantServiceError(f"Plan düşürülemez: {old_plan.value} -> {new_plan.value}")
            
            tenant.updated_by = updated_by
            
            # Set subscription dates
            if new_plan != TenantPlan.TRIAL:
                tenant.subscription_start = datetime.utcnow()
                tenant.subscription_end = datetime.utcnow() + timedelta(days=30)
                tenant.next_billing_date = tenant.subscription_end
            
            await db.commit()
            await db.refresh(tenant)
            
            # Log plan upgrade
            await self._log_tenant_event(
                db, tenant_id, "PLAN_UPGRADED",
                {"old_plan": old_plan.value, "new_plan": new_plan.value},
                updated_by
            )
            
            self.logger.info(
                "Tenant plan upgraded",
                tenant_id=tenant_id,
                old_plan=old_plan.value,
                new_plan=new_plan.value
            )
            
            return tenant.to_dict()
    
    async def extend_trial(
        self,
        tenant_id: str,
        days: int = 14,
        updated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extend tenant trial period
        
        Args:
            tenant_id: Tenant UUID
            days: Days to extend
            updated_by: ID of user making change
            
        Returns:
            Dict[str, Any]: Updated tenant data
        """
        async with get_admin_db() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                raise TenantNotFoundError(f"Tenant bulunamadı: {tenant_id}")
            
            success = tenant.extend_trial(days)
            if not success:
                raise TenantServiceError("Trial uzatılamadı (limit aşıldı veya trial değil)")
            
            tenant.updated_by = updated_by
            
            await db.commit()
            await db.refresh(tenant)
            
            # Log trial extension
            await self._log_tenant_event(
                db, tenant_id, "TRIAL_EXTENDED",
                {"days": days, "new_end_date": tenant.trial_ends_at.isoformat()},
                updated_by
            )
            
            self.logger.info(
                "Trial extended",
                tenant_id=tenant_id,
                days=days,
                new_end_date=tenant.trial_ends_at
            )
            
            return tenant.to_dict()
    
    async def suspend_tenant(
        self,
        tenant_id: str,
        reason: str,
        updated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Suspend tenant account
        
        Args:
            tenant_id: Tenant UUID
            reason: Suspension reason
            updated_by: ID of user making change
            
        Returns:
            Dict[str, Any]: Updated tenant data
        """
        async with get_admin_db() as db:
            await db.execute(
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(
                    status=TenantStatus.SUSPENDED,
                    is_active=False,
                    updated_by=updated_by
                )
            )
            
            # Log suspension
            await self._log_tenant_event(
                db, tenant_id, "TENANT_SUSPENDED",
                {"reason": reason}, updated_by
            )
            
            await db.commit()
            
            self.logger.warning(
                "Tenant suspended",
                tenant_id=tenant_id,
                reason=reason
            )
            
            return await self.get_tenant(tenant_id)
    
    async def update_usage(
        self,
        tenant_id: str,
        resource: str,
        increment: int = 1
    ) -> Dict[str, int]:
        """
        Update tenant resource usage
        
        Args:
            tenant_id: Tenant UUID
            resource: Resource name (api_calls_this_month, etc.)
            increment: Amount to increment
            
        Returns:
            Dict[str, int]: Updated usage stats
        """
        async with get_admin_db() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one_or_none()
            
            if not tenant:
                raise TenantNotFoundError(f"Tenant bulunamadı: {tenant_id}")
            
            # Update usage
            current_usage = tenant.current_usage.copy() if tenant.current_usage else {}
            current_usage[resource] = current_usage.get(resource, 0) + increment
            
            tenant.current_usage = current_usage
            
            await db.commit()
            
            return current_usage
    
    async def check_quota(self, tenant_id: str, resource: str) -> Dict[str, Any]:
        """
        Check if tenant has remaining quota for resource
        
        Args:
            tenant_id: Tenant UUID
            resource: Resource name
            
        Returns:
            Dict[str, Any]: Quota information
        """
        tenant = await self.get_tenant(tenant_id)
        
        limit = tenant["plan_limits"].get(resource, 0)
        used = tenant["current_usage"].get(resource, 0)
        remaining = max(0, limit - used)
        
        return {
            "resource": resource,
            "limit": limit,
            "used": used,
            "remaining": remaining,
            "percentage_used": (used / max(limit, 1)) * 100,
            "quota_exceeded": used >= limit,
            "plan": tenant["plan"]
        }
    
    async def get_tenant_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get comprehensive tenant statistics
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            Dict[str, Any]: Tenant statistics
        """
        tenant = await self.get_tenant(tenant_id)
        
        # Calculate quota status for all resources
        quotas = {}
        for resource in tenant["plan_limits"]:
            quotas[resource] = await self.check_quota(tenant_id, resource)
        
        # Calculate subscription info
        subscription_info = {
            "is_trial": tenant["is_trial"],
            "trial_expired": tenant.get("is_trial_expired", False),
            "subscription_active": tenant.get("is_subscription_active", True),
            "days_remaining": None,
            "billing_info": None
        }
        
        if tenant["is_trial"] and tenant.get("trial_ends_at"):
            trial_end = datetime.fromisoformat(tenant["trial_ends_at"])
            days_left = (trial_end - datetime.utcnow()).days
            subscription_info["days_remaining"] = max(0, days_left)
        elif tenant.get("subscription_end"):
            sub_end = datetime.fromisoformat(tenant["subscription_end"])
            days_left = (sub_end - datetime.utcnow()).days
            subscription_info["days_remaining"] = max(0, days_left)
            
            if tenant.get("next_billing_date"):
                subscription_info["billing_info"] = {
                    "next_billing_date": tenant["next_billing_date"],
                    "plan": tenant["plan"],
                    "estimated_cost": self._calculate_plan_cost(tenant["plan"])
                }
        
        return {
            "tenant_id": tenant_id,
            "name": tenant["name"],
            "subdomain": tenant["subdomain"],
            "plan": tenant["plan"],
            "status": tenant["status"],
            "quotas": quotas,
            "subscription": subscription_info,
            "created_at": tenant["created_at"],
            "onboarding_completed": tenant.get("onboarding_completed", False)
        }
    
    def _validate_subdomain(self, subdomain: str) -> bool:
        """Validate subdomain format"""
        if not subdomain or len(subdomain) < 3 or len(subdomain) > 63:
            return False
        
        # Allow Turkish characters in subdomain
        pattern = r"^[a-z0-9çğıöşü][a-z0-9çğıöşü-]*[a-z0-9çğıöşü]$"
        return bool(re.match(pattern, subdomain))
    
    def _validate_turkish_tax_number(self, tax_number: str) -> bool:
        """Validate Turkish tax number format"""
        if not tax_number:
            return False
        
        # Remove spaces and dashes
        clean_tax_number = re.sub(r"[\s-]", "", tax_number)
        
        # Must be 10 or 11 digits
        if not re.match(r"^\d{10,11}$", clean_tax_number):
            return False
        
        # TODO: Add checksum validation for Turkish tax numbers
        return True
    
    def _calculate_plan_cost(self, plan: str) -> Dict[str, Any]:
        """Calculate estimated plan cost in Turkish Lira"""
        costs = {
            TenantPlan.TRIAL: 0,
            TenantPlan.STARTER: 99,
            TenantPlan.PROFESSIONAL: 299,
            TenantPlan.ENTERPRISE: 999
        }
        
        cost = costs.get(plan, 0)
        return {
            "monthly_cost": cost,
            "currency": "TRY",
            "formatted": format_turkish_currency(cost)
        }
    
    async def _log_tenant_event(
        self,
        db: AsyncSession,
        tenant_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        """Log tenant-related events for audit"""
        audit_log = AuditLogModel(
            tenant_id=tenant_id,
            event_type=event_type,
            table_name="tenants",
            record_id=tenant_id,
            user_id=user_id,
            new_values=str(event_data),
            processing_purpose="tenant_management"
        )
        
        db.add(audit_log)
        # Note: commit happens in calling function