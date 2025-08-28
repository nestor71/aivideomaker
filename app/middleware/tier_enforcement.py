from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.database.models import User, SubscriptionTier
from app.database.base import get_session
from app.services.rate_limiter import usage_tracker
from app.auth.dependencies import get_current_user_or_anonymous
from app.core.logger import logger
from datetime import datetime
import asyncio


class TierEnforcement:
    """Enforce tier-based restrictions."""
    
    @staticmethod
    async def check_video_upload_limits(
        user: Optional[User], 
        video_duration_seconds: float,
        file_size_mb: float,
        db: Session
    ) -> Dict[str, Any]:
        """Check if user can upload video based on tier limits."""
        
        # Anonymous users - require registration for processing
        if not user:
            return {
                "allowed": True,  # Allow upload, but require login for processing
                "require_auth": True,
                "message": "You can preview your video, but need to sign up to process it."
            }
        
        subscription = user.subscription
        if not subscription:
            return {
                "allowed": False,
                "error": "No subscription found"
            }
        
        # Check video duration limits
        max_duration = subscription.max_video_duration_seconds
        if max_duration > 0 and video_duration_seconds > max_duration:
            return {
                "allowed": False,
                "error": f"Video duration ({video_duration_seconds}s) exceeds limit ({max_duration}s) for {subscription.tier.value} tier",
                "limit_exceeded": "duration",
                "upgrade_required": subscription.tier == SubscriptionTier.FREE
            }
        
        # Check monthly usage limits
        if subscription.monthly_video_minutes_limit > 0:
            current_usage = await usage_tracker.get_monthly_usage(user.id)
            current_minutes = current_usage.get("minutes", 0)
            video_minutes = video_duration_seconds / 60.0
            
            if current_minutes + video_minutes > subscription.monthly_video_minutes_limit:
                return {
                    "allowed": False,
                    "error": f"Video would exceed monthly limit ({subscription.monthly_video_minutes_limit} minutes). Current usage: {current_minutes:.1f} minutes",
                    "limit_exceeded": "monthly_minutes",
                    "upgrade_required": subscription.tier == SubscriptionTier.FREE
                }
        
        return {
            "allowed": True,
            "tier": subscription.tier.value,
            "limits": {
                "max_duration_seconds": max_duration,
                "monthly_minutes_limit": subscription.monthly_video_minutes_limit,
                "monthly_minutes_used": (await usage_tracker.get_monthly_usage(user.id)).get("minutes", 0)
            }
        }
    
    @staticmethod
    async def check_processing_permission(
        user: Optional[User],
        db: Session
    ) -> Dict[str, Any]:
        """Check if user can start video processing."""
        
        # Require authentication for processing
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "Authentication required",
                    "message": "Please sign up or log in to process videos",
                    "action_required": "auth"
                }
            )
        
        subscription = user.subscription
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "No subscription found",
                    "message": "Please set up your account",
                    "action_required": "subscription"
                }
            )
        
        # Check if subscription is active
        if subscription.status.value != "active":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "Subscription not active",
                    "message": f"Your subscription is {subscription.status.value}. Please update your billing information.",
                    "action_required": "payment"
                }
            )
        
        return {
            "allowed": True,
            "tier": subscription.tier.value,
            "features": {
                "watermark_enabled": subscription.watermark_enabled,
                "priority_processing": subscription.priority_processing,
                "advanced_ai_features": subscription.advanced_ai_features,
                "max_export_quality": subscription.max_export_quality
            }
        }
    
    @staticmethod
    async def track_video_processing(
        user: User,
        video_duration_seconds: float,
        file_size_mb: float,
        action_type: str = "video_processing",
        ai_service_used: Optional[str] = None
    ):
        """Track video processing usage."""
        try:
            # Track in Redis for real-time limits
            await usage_tracker.track_usage(
                user_id=user.id,
                action_type=action_type,
                video_duration_seconds=video_duration_seconds,
                file_size_mb=file_size_mb
            )
            
            # Track in database for billing and analytics
            from app.database.models import UsageRecord
            from app.database.base import SessionLocal
            
            db = SessionLocal()
            try:
                usage_record = UsageRecord(
                    user_id=user.id,
                    action_type=action_type,
                    video_duration_seconds=video_duration_seconds,
                    file_size_mb=file_size_mb,
                    ai_service_used=ai_service_used,
                    cost_credits=TierEnforcement._calculate_cost(
                        user.subscription.tier if user.subscription else SubscriptionTier.FREE,
                        video_duration_seconds
                    ),
                    is_billable=user.subscription.tier == SubscriptionTier.PREMIUM if user.subscription else False
                )
                
                db.add(usage_record)
                db.commit()
                
                # Update monthly usage in subscription
                if user.subscription:
                    video_minutes = video_duration_seconds / 60.0
                    user.subscription.monthly_video_minutes_used += video_minutes
                    db.commit()
                
                logger.info(f"Usage tracked for user {user.id}: {video_duration_seconds}s video processing")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error tracking usage for user {user.id}: {e}")
    
    @staticmethod
    def _calculate_cost(tier: SubscriptionTier, video_duration_seconds: float) -> float:
        """Calculate cost in internal credits."""
        # Free tier: 0 credits (already paid via subscription)
        # Premium tier: 0 credits (unlimited usage)
        
        if tier == SubscriptionTier.FREE:
            return 0.0  # Free tier usage
        elif tier == SubscriptionTier.PREMIUM:
            return 0.0  # Premium unlimited
        
        return 0.0
    
    @staticmethod
    async def get_ai_service_for_tier(tier: SubscriptionTier, service_type: str) -> str:
        """Get appropriate AI service based on tier."""
        if tier == SubscriptionTier.FREE:
            # Free tier uses local/free services
            ai_services = {
                "transcription": "whisper_local",
                "translation": "google_translate", 
                "text_to_speech": "google_tts"
            }
        else:  # Premium tier
            # Premium tier can use OpenAI APIs
            ai_services = {
                "transcription": "whisper_api",  # Could fallback to local
                "translation": "openai_gpt",    # Could fallback to google
                "text_to_speech": "openai_tts"  # Could fallback to google
            }
        
        return ai_services.get(service_type, "unknown")


class TierMiddleware:
    """Middleware factory for tier enforcement."""
    
    def __init__(self, check_type: str):
        self.check_type = check_type
    
    async def __call__(
        self, 
        user: Optional[User] = Depends(get_current_user_or_anonymous),
        db: Session = Depends(get_session)
    ):
        """Apply tier checks based on type."""
        
        if self.check_type == "processing":
            return await TierEnforcement.check_processing_permission(user, db)
        elif self.check_type == "upload":
            # This would need additional parameters in real implementation
            return {"allowed": True, "user": user}
        
        return {"allowed": True, "user": user}


# Pre-configured middleware instances
require_auth_for_processing = TierMiddleware("processing")
check_upload_limits = TierMiddleware("upload")


# Dependency functions for common checks
async def require_premium_tier(
    user: User = Depends(get_current_user_or_anonymous)
) -> User:
    """Require premium subscription."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for premium features"
        )
    
    if not user.subscription or user.subscription.tier != SubscriptionTier.PREMIUM:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "Premium subscription required",
                "message": "This feature requires a premium subscription",
                "action_required": "upgrade"
            }
        )
    
    return user


async def check_feature_access(feature: str):
    """Check if user has access to specific feature."""
    async def _check_feature(
        user: User = Depends(get_current_user_or_anonymous)
    ) -> User:
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        if not user.subscription:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Subscription required"
            )
        
        # Feature-specific checks
        feature_requirements = {
            "advanced_ai": lambda s: s.advanced_ai_features,
            "priority_processing": lambda s: s.priority_processing,
            "4k_export": lambda s: s.max_export_quality in ["4K", "2K", "1080p"],
            "no_watermark": lambda s: not s.watermark_enabled
        }
        
        requirement_check = feature_requirements.get(feature)
        if requirement_check and not requirement_check(user.subscription):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": f"Feature '{feature}' not available in {user.subscription.tier.value} tier",
                    "message": "Upgrade to premium for advanced features",
                    "action_required": "upgrade"
                }
            )
        
        return user
    
    return _check_feature


# Specific feature dependencies
require_advanced_ai = check_feature_access("advanced_ai")
require_priority_processing = check_feature_access("priority_processing")
require_4k_export = check_feature_access("4k_export")
require_no_watermark = check_feature_access("no_watermark")