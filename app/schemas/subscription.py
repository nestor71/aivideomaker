from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.database.models import SubscriptionTier, SubscriptionStatus, PaymentStatus


class SubscriptionResponse(BaseModel):
    """Subscription details response."""
    id: int
    tier: SubscriptionTier
    status: SubscriptionStatus
    
    # Usage limits
    monthly_video_minutes_used: float
    monthly_video_minutes_limit: float
    concurrent_uploads_limit: int
    max_video_duration_seconds: int
    max_export_quality: str
    
    # Features
    watermark_enabled: bool
    priority_processing: bool
    advanced_ai_features: bool
    
    # Billing
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UsageResponse(BaseModel):
    """Usage record response."""
    id: int
    action_type: str
    video_duration_seconds: Optional[float] = None
    file_size_mb: Optional[float] = None
    ai_service_used: Optional[str] = None
    cost_credits: float
    processing_time_seconds: Optional[float] = None
    export_quality: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class UsageSummary(BaseModel):
    """Monthly usage summary."""
    current_month_minutes: float
    monthly_limit: float
    percentage_used: float
    days_remaining_in_cycle: int
    recent_usage: List[UsageResponse]


class PaymentResponse(BaseModel):
    """Payment history response."""
    id: int
    amount: float
    currency: str
    status: PaymentStatus
    description: Optional[str] = None
    billing_period_start: Optional[datetime] = None
    billing_period_end: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class SubscriptionCreate(BaseModel):
    """Create subscription request."""
    tier: SubscriptionTier
    payment_method_id: str  # Stripe payment method ID


class SubscriptionUpdate(BaseModel):
    """Update subscription request."""
    tier: Optional[SubscriptionTier] = None
    cancel_at_period_end: Optional[bool] = None


class BillingPortalRequest(BaseModel):
    """Stripe billing portal request."""
    return_url: str