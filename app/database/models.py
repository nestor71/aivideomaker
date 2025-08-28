from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base
import enum
from datetime import datetime
from typing import Optional


class UserRole(str, enum.Enum):
    """User role enum."""
    USER = "user"
    ADMIN = "admin"


class SubscriptionTier(str, enum.Enum):
    """Subscription tier enum."""
    FREE = "free"
    PREMIUM = "premium"


class SubscriptionStatus(str, enum.Enum):
    """Subscription status enum."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"


class PaymentStatus(str, enum.Enum):
    """Payment status enum."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class User(Base):
    """User model for authentication and billing."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)  # Nullable for OAuth users
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # OAuth fields
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    microsoft_id = Column(String(255), unique=True, nullable=True, index=True)
    apple_id = Column(String(255), unique=True, nullable=True, index=True)
    
    # User management
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True)
    
    # GDPR & Privacy
    agreed_to_terms = Column(Boolean, default=False)
    gdpr_consent = Column(Boolean, default=False)
    marketing_consent = Column(Boolean, default=False)
    data_retention_expiry = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    usage_records = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")
    payment_history = relationship("PaymentHistory", back_populates="user", cascade="all, delete-orphan")
    
    # GDPR Relationships
    consents = relationship("UserConsent", back_populates="user", cascade="all, delete-orphan")
    processing_records = relationship("DataProcessingRecord", back_populates="user", cascade="all, delete-orphan")
    export_requests = relationship("DataExportRequest", back_populates="user", cascade="all, delete-orphan")
    deletion_requests = relationship("DataDeletionRequest", back_populates="user", cascade="all, delete-orphan")
    cookie_consents = relationship("CookieConsent", back_populates="user", cascade="all, delete-orphan")
    data_inventory = relationship("UserDataInventory", back_populates="user", cascade="all, delete-orphan")


class Subscription(Base):
    """User subscription model."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Subscription details
    tier = Column(Enum(SubscriptionTier), default=SubscriptionTier.FREE)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    
    # Stripe integration
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    stripe_subscription_id = Column(String(255), nullable=True, index=True)
    
    # Billing
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    
    # Usage limits (monthly reset)
    monthly_video_minutes_used = Column(Float, default=0.0)
    monthly_video_minutes_limit = Column(Float, default=10.0)  # 10 minutes for free tier
    concurrent_uploads_limit = Column(Integer, default=1)
    max_video_duration_seconds = Column(Integer, default=60)  # 1 minute for free tier
    max_export_quality = Column(String(10), default="720p")
    
    # Features
    watermark_enabled = Column(Boolean, default=True)  # True for free tier
    priority_processing = Column(Boolean, default=False)
    advanced_ai_features = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="subscription")


class UsageRecord(Base):
    """Track user usage for billing and rate limiting."""
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Usage details
    action_type = Column(String(50), nullable=False, index=True)  # video_processing, transcription, etc.
    video_duration_seconds = Column(Float, nullable=True)
    file_size_mb = Column(Float, nullable=True)
    ai_service_used = Column(String(100), nullable=True)  # whisper, openai, google_translate, etc.
    
    # Billing
    cost_credits = Column(Float, default=0.0)  # Internal credit system
    is_billable = Column(Boolean, default=True)
    
    # Metadata
    extra_data = Column(JSON, nullable=True)  # Store additional data as JSON
    processing_time_seconds = Column(Float, nullable=True)
    export_quality = Column(String(10), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="usage_records")


class PaymentHistory(Base):
    """Track payment history."""
    __tablename__ = "payment_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Stripe integration
    stripe_payment_intent_id = Column(String(255), nullable=True, index=True)
    stripe_invoice_id = Column(String(255), nullable=True, index=True)
    
    # Payment details
    amount = Column(Float, nullable=False)  # In USD
    currency = Column(String(3), default="USD")
    status = Column(Enum(PaymentStatus), nullable=False)
    
    # Billing period
    billing_period_start = Column(DateTime, nullable=True)
    billing_period_end = Column(DateTime, nullable=True)
    
    # Metadata
    description = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="payment_history")


# Admin tables for analytics and monitoring
class SystemMetrics(Base):
    """Store system-wide metrics."""
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_type = Column(String(50), nullable=False)  # counter, gauge, histogram
    tags = Column(JSON, nullable=True)  # Store tags as JSON
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Audit log for security and compliance."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Action details
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(255), nullable=True)
    
    # Request details
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    
    # Results
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Metadata
    extra_data = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())