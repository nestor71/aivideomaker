from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List

from app.database.base import get_session
from app.database.models import User, SubscriptionTier, PaymentHistory
from app.schemas.subscription import (
    SubscriptionResponse, SubscriptionCreate, SubscriptionUpdate,
    BillingPortalRequest, UsageResponse, PaymentResponse, UsageSummary
)
from app.services.stripe_service import stripe_service
from app.services.rate_limiter import usage_tracker
from app.services.usage_monitor import usage_monitor
from app.auth.dependencies import get_current_active_user, rate_limit_moderate
from app.core.logger import logger
from datetime import datetime, timedelta
import calendar

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


@router.get("/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session)
):
    """Get current user subscription."""
    if not current_user.subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found"
        )
    
    return SubscriptionResponse.from_attributes(current_user.subscription)


@router.get("/usage", response_model=UsageSummary)
async def get_usage_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session)
):
    """Get monthly usage summary."""
    try:
        # Get current month usage from Redis
        redis_usage = await usage_tracker.get_monthly_usage(current_user.id)
        
        # Get recent usage records from database
        from app.database.models import UsageRecord
        recent_usage = db.query(UsageRecord).filter(
            UsageRecord.user_id == current_user.id,
            UsageRecord.created_at >= datetime.utcnow() - timedelta(days=7)
        ).order_by(UsageRecord.created_at.desc()).limit(10).all()
        
        # Calculate days remaining in current month
        now = datetime.utcnow()
        last_day = calendar.monthrange(now.year, now.month)[1]
        days_remaining = last_day - now.day
        
        # Get subscription limits
        subscription = current_user.subscription
        monthly_limit = subscription.monthly_video_minutes_limit if subscription else 10.0
        
        return UsageSummary(
            current_month_minutes=redis_usage.get("minutes", 0),
            monthly_limit=monthly_limit,
            percentage_used=(redis_usage.get("minutes", 0) / max(monthly_limit, 1)) * 100 if monthly_limit > 0 else 0,
            days_remaining_in_cycle=days_remaining,
            recent_usage=[UsageResponse.from_attributes(record) for record in recent_usage]
        )
        
    except Exception as e:
        logger.error(f"Error getting usage summary for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get usage summary"
        )


@router.get("/payment-history", response_model=List[PaymentResponse])
async def get_payment_history(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session)
):
    """Get user payment history."""
    payments = db.query(PaymentHistory).filter(
        PaymentHistory.user_id == current_user.id
    ).order_by(PaymentHistory.created_at.desc()).limit(50).all()
    
    return [PaymentResponse.from_attributes(payment) for payment in payments]


@router.post("/create", response_model=dict)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
    _: bool = Depends(rate_limit_moderate)
):
    """Create new subscription."""
    try:
        # Check if user already has premium subscription
        if (current_user.subscription and 
            current_user.subscription.tier == SubscriptionTier.PREMIUM and
            current_user.subscription.status.value == "active"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has active premium subscription"
            )
        
        # Create Stripe subscription
        result = await stripe_service.create_subscription(
            db=db,
            user=current_user,
            payment_method_id=subscription_data.payment_method_id,
            tier=subscription_data.tier
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Subscription creation error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/update", response_model=dict)
async def update_subscription(
    subscription_data: SubscriptionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
    _: bool = Depends(rate_limit_moderate)
):
    """Update existing subscription."""
    try:
        if not current_user.subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found"
            )
        
        result = {}
        
        # Update tier if requested
        if subscription_data.tier:
            stripe_result = await stripe_service.update_subscription(
                db=db,
                user=current_user,
                new_tier=subscription_data.tier
            )
            result.update(stripe_result)
        
        # Update cancellation if requested
        if subscription_data.cancel_at_period_end is not None:
            if subscription_data.cancel_at_period_end:
                cancel_result = await stripe_service.cancel_subscription(
                    db=db,
                    user=current_user,
                    at_period_end=True
                )
                result.update(cancel_result)
            else:
                # Reactivate subscription (remove cancellation)
                current_user.subscription.cancel_at_period_end = False
                db.commit()
                result["reactivated"] = True
        
        return result
        
    except Exception as e:
        logger.error(f"Subscription update error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/cancel", response_model=dict)
async def cancel_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session),
    _: bool = Depends(rate_limit_moderate)
):
    """Cancel subscription at period end."""
    try:
        if not current_user.subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found"
            )
        
        result = await stripe_service.cancel_subscription(
            db=db,
            user=current_user,
            at_period_end=True
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Subscription cancellation error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/billing-portal", response_model=dict)
async def create_billing_portal(
    billing_data: BillingPortalRequest,
    current_user: User = Depends(get_current_active_user),
    _: bool = Depends(rate_limit_moderate)
):
    """Create Stripe billing portal session."""
    try:
        if not current_user.subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found"
            )
        
        portal_url = await stripe_service.create_billing_portal_session(
            user=current_user,
            return_url=billing_data.return_url
        )
        
        return {"url": portal_url}
        
    except Exception as e:
        logger.error(f"Billing portal error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/pricing", response_model=dict)
async def get_pricing():
    """Get pricing information."""
    return {
        "plans": {
            "free": {
                "name": "Free",
                "price": 0,
                "currency": "USD",
                "interval": "month",
                "features": {
                    "monthly_minutes": 10,
                    "max_video_duration": 60,
                    "max_quality": "720p",
                    "concurrent_uploads": 1,
                    "watermark": True,
                    "ai_services": ["whisper_local", "google_translate", "google_tts"]
                }
            },
            "premium": {
                "name": "Premium",
                "price": 999,  # In cents ($9.99)
                "currency": "USD",
                "interval": "month",
                "yearly_price": 9900,  # In cents ($99.00)
                "features": {
                    "monthly_minutes": -1,  # Unlimited
                    "max_video_duration": -1,  # Unlimited
                    "max_quality": "4K",
                    "concurrent_uploads": 5,
                    "watermark": False,
                    "priority_processing": True,
                    "ai_services": ["whisper_local", "whisper_api", "openai_gpt", "google_translate", "google_tts", "openai_tts"]
                }
            }
        }
    }


# Webhook endpoint for Stripe
@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_session)
):
    """Handle Stripe webhooks."""
    try:
        payload = await request.body()
        signature = request.headers.get('stripe-signature')
        
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Stripe signature"
            )
        
        result = await stripe_service.handle_webhook(
            payload=payload.decode('utf-8'),
            signature=signature,
            db=db
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook processing failed"
        )


@router.get("/limits", response_model=dict)
async def get_subscription_limits(
    current_user: User = Depends(get_current_active_user)
):
    """Get current subscription limits."""
    subscription = current_user.subscription
    
    if not subscription:
        # Default free tier limits
        return {
            "tier": "free",
            "monthly_video_minutes_limit": 10.0,
            "monthly_video_minutes_used": 0.0,
            "concurrent_uploads_limit": 1,
            "max_video_duration_seconds": 60,
            "max_export_quality": "720p",
            "watermark_enabled": True,
            "priority_processing": False,
            "advanced_ai_features": False
        }
    
    return {
        "tier": subscription.tier.value,
        "monthly_video_minutes_limit": subscription.monthly_video_minutes_limit,
        "monthly_video_minutes_used": subscription.monthly_video_minutes_used,
        "concurrent_uploads_limit": subscription.concurrent_uploads_limit,
        "max_video_duration_seconds": subscription.max_video_duration_seconds,
        "max_export_quality": subscription.max_export_quality,
        "watermark_enabled": subscription.watermark_enabled,
        "priority_processing": subscription.priority_processing,
        "advanced_ai_features": subscription.advanced_ai_features
    }