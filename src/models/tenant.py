"""
Tenant model for Turkish Business Integration Platform
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List

from sqlalchemy import Column, String, Boolean, JSON, Enum as SQLEnum, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.base import SystemModel


class TenantPlan(str, SQLEnum):
    """Tenant subscription plans"""
    TRIAL = "trial"
    STARTER = "starter"
    PROFESSIONAL = "professional" 
    ENTERPRISE = "enterprise"


class TenantStatus(str, SQLEnum):
    """Tenant account status"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    PENDING = "pending"


class Tenant(SystemModel):
    """
    Tenant model for multi-tenant SaaS
    
    Represents a customer organization using the platform
    """
    __tablename__ = "tenants"
    
    # Basic information
    name = Column(String(255), nullable=False)
    subdomain = Column(String(63), unique=True, nullable=False, index=True)
    domain = Column(String(255), nullable=True)  # Custom domain
    
    # Turkish business information
    tax_number = Column(String(11), nullable=True, index=True)  # Vergi numarası (10 or 11 digits)
    tax_office = Column(String(255), nullable=True)  # Vergi dairesi
    trade_registry_number = Column(String(20), nullable=True)  # Ticaret sicil numarası
    mersis_number = Column(String(20), nullable=True)  # MERSİS numarası
    
    # Contact information
    email = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(2), default="TR", nullable=False)  # ISO country code
    
    # KVKK Compliance
    kvkk_consent_date = Column(DateTime, nullable=True)
    verbis_registration = Column(String(255), nullable=True)  # KVKK VERBİS registration number
    kvkk_representative = Column(String(255), nullable=True)  # KVKK representative name
    kvkk_representative_email = Column(String(255), nullable=True)
    data_protection_officer = Column(String(255), nullable=True)
    
    # Subscription information
    plan = Column(SQLEnum(TenantPlan), default=TenantPlan.TRIAL, nullable=False)
    status = Column(SQLEnum(TenantStatus), default=TenantStatus.PENDING, nullable=False)
    
    # Plan limits (JSON structure)
    plan_limits = Column(JSON, default=lambda: {
        "api_calls_per_month": 10000,
        "workflows": 10,
        "integrations": 3,
        "users": 5,
        "storage_gb": 1,
        "webhook_endpoints": 5
    })
    
    # Current usage (updated by background tasks)
    current_usage = Column(JSON, default=lambda: {
        "api_calls_this_month": 0,
        "active_workflows": 0,
        "active_integrations": 0,
        "active_users": 0,
        "storage_used_gb": 0,
        "webhook_endpoints": 0
    })
    
    # Billing information
    billing_email = Column(String(255), nullable=True)
    billing_address = Column(Text, nullable=True)
    subscription_start = Column(DateTime, nullable=True)
    subscription_end = Column(DateTime, nullable=True)
    next_billing_date = Column(DateTime, nullable=True)
    
    # Feature flags
    features = Column(JSON, default=list)  # List of enabled features
    
    # Tenant settings
    settings = Column(JSON, default=dict)
    
    # Turkish localization settings
    language = Column(String(5), default="tr-TR", nullable=False)
    timezone = Column(String(50), default="Europe/Istanbul", nullable=False)
    currency = Column(String(3), default="TRY", nullable=False)
    date_format = Column(String(20), default="DD.MM.YYYY", nullable=False)
    time_format = Column(String(10), default="24h", nullable=False)
    
    # Status flags
    is_active = Column(Boolean, default=True, nullable=False)
    is_trial = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Trial information
    trial_ends_at = Column(DateTime, nullable=True)
    trial_extended_count = Column(Integer, default=0)
    
    # Onboarding status
    onboarding_completed = Column(Boolean, default=False)
    onboarding_step = Column(String(50), nullable=True)
    
    # Support information
    support_tier = Column(String(20), default="standard")  # standard, premium, enterprise
    support_contact = Column(String(255), nullable=True)
    
    # Technical settings
    api_rate_limit = Column(Integer, nullable=True)  # Custom rate limit
    webhook_secret = Column(String(64), nullable=True)  # For webhook verification
    
    # Relationships for DIA integration
    dia_cari_kartlar = relationship("DIACariKartDB", back_populates="tenant", cascade="all, delete-orphan")
    dia_stok_kartlar = relationship("DIAStokKartDB", back_populates="tenant", cascade="all, delete-orphan") 
    dia_fatura_fisler = relationship("DIAFaturaFisiDB", back_populates="tenant", cascade="all, delete-orphan")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.webhook_secret:
            self.webhook_secret = self._generate_webhook_secret()
    
    def _generate_webhook_secret(self) -> str:
        """Generate secure webhook secret"""
        import secrets
        return secrets.token_hex(32)
    
    def is_plan_feature_available(self, feature: str) -> bool:
        """
        Check if a feature is available in current plan
        
        Args:
            feature: Feature name to check
            
        Returns:
            bool: True if feature is available
        """
        plan_features = {
            TenantPlan.TRIAL: [
                "basic_integrations", "webhook_notifications", "basic_workflows"
            ],
            TenantPlan.STARTER: [
                "basic_integrations", "webhook_notifications", "basic_workflows",
                "api_access", "email_support"
            ],
            TenantPlan.PROFESSIONAL: [
                "basic_integrations", "webhook_notifications", "basic_workflows",
                "api_access", "email_support", "advanced_workflows", 
                "custom_integrations", "priority_support", "analytics"
            ],
            TenantPlan.ENTERPRISE: [
                "basic_integrations", "webhook_notifications", "basic_workflows",
                "api_access", "email_support", "advanced_workflows",
                "custom_integrations", "priority_support", "analytics",
                "white_label", "dedicated_support", "sla", "custom_development"
            ]
        }
        
        return feature in plan_features.get(self.plan, [])
    
    def has_usage_quota(self, resource: str) -> bool:
        """
        Check if tenant has remaining quota for a resource
        
        Args:
            resource: Resource type (api_calls_per_month, workflows, etc.)
            
        Returns:
            bool: True if quota is available
        """
        limit = self.plan_limits.get(resource, 0)
        current = self.current_usage.get(resource, 0)
        
        return current < limit
    
    def get_remaining_quota(self, resource: str) -> int:
        """
        Get remaining quota for a resource
        
        Args:
            resource: Resource type
            
        Returns:
            int: Remaining quota
        """
        limit = self.plan_limits.get(resource, 0)
        current = self.current_usage.get(resource, 0)
        
        return max(0, limit - current)
    
    def is_trial_expired(self) -> bool:
        """Check if trial period has expired"""
        if not self.is_trial or not self.trial_ends_at:
            return False
        return datetime.utcnow() > self.trial_ends_at
    
    def is_subscription_active(self) -> bool:
        """Check if subscription is currently active"""
        if self.status != TenantStatus.ACTIVE:
            return False
        if self.is_trial:
            return not self.is_trial_expired()
        if self.subscription_end:
            return datetime.utcnow() < self.subscription_end
        return True
    
    def extend_trial(self, days: int = 14) -> bool:
        """
        Extend trial period
        
        Args:
            days: Number of days to extend
            
        Returns:
            bool: True if extension was successful
        """
        if not self.is_trial or self.trial_extended_count >= 2:
            return False
        
        if not self.trial_ends_at:
            self.trial_ends_at = datetime.utcnow()
        
        from datetime import timedelta
        self.trial_ends_at += timedelta(days=days)
        self.trial_extended_count += 1
        
        return True
    
    def upgrade_plan(self, new_plan: TenantPlan) -> bool:
        """
        Upgrade tenant plan
        
        Args:
            new_plan: New plan to upgrade to
            
        Returns:
            bool: True if upgrade was successful
        """
        plan_hierarchy = {
            TenantPlan.TRIAL: 0,
            TenantPlan.STARTER: 1,
            TenantPlan.PROFESSIONAL: 2,
            TenantPlan.ENTERPRISE: 3
        }
        
        current_level = plan_hierarchy.get(self.plan, 0)
        new_level = plan_hierarchy.get(new_plan, 0)
        
        if new_level <= current_level:
            return False
        
        self.plan = new_plan
        self.is_trial = False
        
        # Update plan limits based on new plan
        self._update_plan_limits()
        
        return True
    
    def _update_plan_limits(self):
        """Update plan limits based on current plan"""
        limits = {
            TenantPlan.TRIAL: {
                "api_calls_per_month": 1000,
                "workflows": 3,
                "integrations": 2,
                "users": 2,
                "storage_gb": 0.5,
                "webhook_endpoints": 2
            },
            TenantPlan.STARTER: {
                "api_calls_per_month": 10000,
                "workflows": 10,
                "integrations": 5,
                "users": 10,
                "storage_gb": 5,
                "webhook_endpoints": 10
            },
            TenantPlan.PROFESSIONAL: {
                "api_calls_per_month": 100000,
                "workflows": 50,
                "integrations": 20,
                "users": 50,
                "storage_gb": 50,
                "webhook_endpoints": 50
            },
            TenantPlan.ENTERPRISE: {
                "api_calls_per_month": 1000000,
                "workflows": -1,  # Unlimited
                "integrations": -1,  # Unlimited
                "users": -1,  # Unlimited
                "storage_gb": 500,
                "webhook_endpoints": -1  # Unlimited
            }
        }
        
        self.plan_limits = limits.get(self.plan, limits[TenantPlan.TRIAL])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tenant to dictionary with sensitive data filtered"""
        data = super().to_dict()
        
        # Remove sensitive fields
        sensitive_fields = ["webhook_secret"]
        for field in sensitive_fields:
            data.pop(field, None)
        
        # Add computed fields
        data["is_trial_expired"] = self.is_trial_expired()
        data["is_subscription_active"] = self.is_subscription_active()
        data["plan_features"] = self._get_plan_features()
        
        return data
    
    def _get_plan_features(self) -> List[str]:
        """Get list of features available in current plan"""
        plan_features = {
            TenantPlan.TRIAL: [
                "basic_integrations", "webhook_notifications", "basic_workflows"
            ],
            TenantPlan.STARTER: [
                "basic_integrations", "webhook_notifications", "basic_workflows",
                "api_access", "email_support"
            ],
            TenantPlan.PROFESSIONAL: [
                "basic_integrations", "webhook_notifications", "basic_workflows",
                "api_access", "email_support", "advanced_workflows",
                "custom_integrations", "priority_support", "analytics"
            ],
            TenantPlan.ENTERPRISE: [
                "basic_integrations", "webhook_notifications", "basic_workflows", 
                "api_access", "email_support", "advanced_workflows",
                "custom_integrations", "priority_support", "analytics",
                "white_label", "dedicated_support", "sla", "custom_development"
            ]
        }
        
        return plan_features.get(self.plan, [])