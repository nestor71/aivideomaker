from typing import Optional
from sqlalchemy.orm import Session
from app.database.models import User, Subscription, UsageRecord, SubscriptionTier
from app.services.email_service import email_service
from app.core.logger import logger
from datetime import datetime, timedelta
from sqlalchemy import func


class UsageMonitor:
    """Monitor user usage and send notifications."""
    
    @staticmethod
    async def check_usage_limits(db: Session, user: User, minutes_used: float) -> bool:
        """Check if user has exceeded usage limits and send notifications."""
        try:
            if not user.subscription:
                return False
            
            subscription = user.subscription
            
            # Skip unlimited users
            if subscription.monthly_video_minutes_limit == -1:
                return True
            
            # Calculate current month usage
            current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            total_usage = db.query(func.sum(UsageRecord.video_duration_seconds)).filter(
                UsageRecord.user_id == user.id,
                UsageRecord.created_at >= current_month_start,
                UsageRecord.action_type == "video_processing"
            ).scalar() or 0
            
            total_minutes = (total_usage / 60) + minutes_used
            limit = subscription.monthly_video_minutes_limit
            usage_percent = int((total_minutes / limit) * 100) if limit > 0 else 0
            
            # Send warning at 80% usage
            if usage_percent >= 80 and usage_percent < 100:
                # Check if we already sent a warning this month
                warning_sent = db.query(UsageRecord).filter(
                    UsageRecord.user_id == user.id,
                    UsageRecord.created_at >= current_month_start,
                    UsageRecord.action_type == "usage_warning_80"
                ).first()
                
                if not warning_sent:
                    # Send warning email
                    try:
                        email_service.send_usage_limit_warning(
                            user_email=user.email,
                            user_name=user.full_name or user.email.split('@')[0],
                            usage_percent=usage_percent,
                            tier=subscription.tier.value
                        )
                        
                        # Record that we sent the warning
                        warning_record = UsageRecord(
                            user_id=user.id,
                            action_type="usage_warning_80",
                            video_duration_seconds=0,
                            file_size_mb=0
                        )
                        db.add(warning_record)
                        db.commit()
                        
                        logger.info(f"Usage warning sent to user {user.id} at {usage_percent}%")
                        
                    except Exception as e:
                        logger.error(f"Failed to send usage warning to user {user.id}: {e}")
            
            # Send exceeded notification at 100% usage
            elif usage_percent >= 100:
                # Check if we already sent an exceeded notification this month
                exceeded_sent = db.query(UsageRecord).filter(
                    UsageRecord.user_id == user.id,
                    UsageRecord.created_at >= current_month_start,
                    UsageRecord.action_type == "usage_exceeded"
                ).first()
                
                if not exceeded_sent:
                    # Send exceeded email
                    try:
                        email_service.send_usage_limit_exceeded(
                            user_email=user.email,
                            user_name=user.full_name or user.email.split('@')[0],
                            tier=subscription.tier.value
                        )
                        
                        # Record that we sent the exceeded notification
                        exceeded_record = UsageRecord(
                            user_id=user.id,
                            action_type="usage_exceeded",
                            video_duration_seconds=0,
                            file_size_mb=0
                        )
                        db.add(exceeded_record)
                        db.commit()
                        
                        logger.info(f"Usage exceeded notification sent to user {user.id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to send usage exceeded notification to user {user.id}: {e}")
                
                return False  # Block processing
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking usage limits for user {user.id}: {e}")
            return True  # Allow processing on error to avoid blocking users
    
    @staticmethod
    async def send_monthly_reset_notifications(db: Session):
        """Send notifications when monthly limits reset."""
        try:
            # Find all users who had usage warnings/exceeded notifications last month
            last_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
            last_month_end = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            users_with_warnings = db.query(User).join(UsageRecord).filter(
                UsageRecord.created_at >= last_month_start,
                UsageRecord.created_at < last_month_end,
                UsageRecord.action_type.in_(["usage_warning_80", "usage_exceeded"])
            ).distinct().all()
            
            for user in users_with_warnings:
                try:
                    # Send reset notification
                    email_service.send_template_email(
                        to_email=user.email,
                        template_name="usage_reset",
                        subject="Your monthly video processing minutes have been reset!",
                        context={
                            "user_name": user.full_name or user.email.split('@')[0],
                            "tier": user.subscription.tier.value if user.subscription else "free",
                            "limit": user.subscription.monthly_video_minutes_limit if user.subscription else 10,
                            "app_name": "AIVideoMaker",
                            "year": datetime.now().year
                        }
                    )
                    
                    logger.info(f"Monthly reset notification sent to user {user.id}")
                    
                except Exception as e:
                    logger.error(f"Failed to send monthly reset notification to user {user.id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error sending monthly reset notifications: {e}")
    
    @staticmethod
    async def get_usage_statistics(db: Session, user: User) -> dict:
        """Get detailed usage statistics for a user."""
        try:
            if not user.subscription:
                return {
                    "current_month_minutes": 0,
                    "monthly_limit": 10,
                    "percentage_used": 0,
                    "days_remaining_in_cycle": 0,
                    "recent_usage": []
                }
            
            subscription = user.subscription
            current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Calculate current month usage
            total_usage = db.query(func.sum(UsageRecord.video_duration_seconds)).filter(
                UsageRecord.user_id == user.id,
                UsageRecord.created_at >= current_month_start,
                UsageRecord.action_type == "video_processing"
            ).scalar() or 0
            
            current_minutes = total_usage / 60
            limit = subscription.monthly_video_minutes_limit
            percentage = (current_minutes / limit * 100) if limit > 0 else 0
            
            # Days remaining in current month
            next_month = (datetime.utcnow().replace(day=1) + timedelta(days=32)).replace(day=1)
            days_remaining = (next_month - datetime.utcnow()).days
            
            # Recent usage (last 10 records)
            recent_usage = db.query(UsageRecord).filter(
                UsageRecord.user_id == user.id,
                UsageRecord.action_type == "video_processing"
            ).order_by(UsageRecord.created_at.desc()).limit(10).all()
            
            recent_usage_data = [
                {
                    "date": record.created_at.isoformat(),
                    "duration_seconds": record.video_duration_seconds,
                    "file_size_mb": record.file_size_mb,
                    "ai_service": record.ai_service_used
                }
                for record in recent_usage
            ]
            
            return {
                "current_month_minutes": round(current_minutes, 2),
                "monthly_limit": limit,
                "percentage_used": round(percentage, 1),
                "days_remaining_in_cycle": days_remaining,
                "recent_usage": recent_usage_data
            }
            
        except Exception as e:
            logger.error(f"Error getting usage statistics for user {user.id}: {e}")
            return {
                "current_month_minutes": 0,
                "monthly_limit": 10,
                "percentage_used": 0,
                "days_remaining_in_cycle": 0,
                "recent_usage": []
            }


# Global instance
usage_monitor = UsageMonitor()