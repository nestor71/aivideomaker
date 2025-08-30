from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta

from app.database.base import get_session
from app.database.models import (
    User, Subscription, UsageRecord, PaymentHistory, AuditLog, 
    SystemMetrics, SubscriptionTier, SubscriptionStatus, UserRole
)
from app.auth.dependencies import require_admin
from app.schemas.auth import UserResponse
from app.core.logger import logger

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/setup-admin-roles")
async def setup_admin_roles(db: Session = Depends(get_session)):
    """
    TEMPORARY ROUTE: Set admin role for users with admin email addresses.
    This is a one-time setup route that should be removed after use.
    """
    from app.core.config import settings
    from app.database.models import UserRole
    
    try:
        admin_emails = settings.ADMIN_EMAIL_ADDRESSES
        if not admin_emails:
            raise HTTPException(
                status_code=400, 
                detail="No admin email addresses configured"
            )
        
        # Find users with admin emails
        admin_users = db.query(User).filter(User.email.in_(admin_emails)).all()
        
        if not admin_users:
            raise HTTPException(
                status_code=404,
                detail=f"No users found with admin emails: {admin_emails}"
            )
        
        updated_count = 0
        updated_users = []
        
        for user in admin_users:
            if user.role != UserRole.ADMIN:
                user.role = UserRole.ADMIN
                updated_count += 1
                updated_users.append(user.email)
                logger.info(f"Set admin role for user: {user.email}")
        
        if updated_count > 0:
            db.commit()
        
        return {
            "message": f"Successfully updated {updated_count} user(s) to admin role",
            "updated_users": updated_users,
            "admin_emails": admin_emails
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error setting admin roles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/stats")
async def get_dashboard_stats(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_session)
):
    """Get admin dashboard statistics."""
    try:
        # User statistics
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        verified_users = db.query(User).filter(User.is_verified == True).count()
        
        # Subscription statistics
        free_users = db.query(Subscription).filter(
            Subscription.tier == SubscriptionTier.FREE,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).count()
        
        premium_users = db.query(Subscription).filter(
            Subscription.tier == SubscriptionTier.PREMIUM,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).count()
        
        # Revenue statistics (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        monthly_revenue = db.query(func.sum(PaymentHistory.amount)).filter(
            PaymentHistory.created_at >= thirty_days_ago,
            PaymentHistory.status == "completed"
        ).scalar() or 0
        
        # Usage statistics
        total_videos_processed = db.query(func.count(UsageRecord.id)).filter(
            UsageRecord.action_type == "video_processing"
        ).scalar() or 0
        
        monthly_videos = db.query(func.count(UsageRecord.id)).filter(
            UsageRecord.action_type == "video_processing",
            UsageRecord.created_at >= thirty_days_ago
        ).scalar() or 0
        
        # Conversion rate (free to premium)
        conversion_rate = (premium_users / max(total_users, 1)) * 100
        
        # Growth statistics (last 7 days vs previous 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
        
        new_users_week = db.query(User).filter(
            User.created_at >= seven_days_ago
        ).count()
        
        new_users_prev_week = db.query(User).filter(
            User.created_at >= fourteen_days_ago,
            User.created_at < seven_days_ago
        ).count()
        
        user_growth = ((new_users_week - new_users_prev_week) / max(new_users_prev_week, 1)) * 100
        
        return {
            "users": {
                "total": total_users,
                "active": active_users,
                "verified": verified_users,
                "growth_rate": user_growth
            },
            "subscriptions": {
                "free": free_users,
                "premium": premium_users,
                "conversion_rate": conversion_rate
            },
            "revenue": {
                "monthly": monthly_revenue,
                "currency": "USD"
            },
            "usage": {
                "total_videos": total_videos_processed,
                "monthly_videos": monthly_videos
            },
            "growth": {
                "new_users_week": new_users_week,
                "user_growth_rate": user_growth
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting admin dashboard stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard statistics"
        )


@router.get("/users", response_model=List[dict])
async def get_users(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    tier: Optional[SubscriptionTier] = Query(None),
    status: Optional[str] = Query(None)
):
    """Get paginated list of users."""
    try:
        query = db.query(User).join(Subscription, User.id == Subscription.user_id, isouter=True)
        
        # Apply filters
        if search:
            query = query.filter(
                (User.email.ilike(f"%{search}%")) |
                (User.full_name.ilike(f"%{search}%"))
            )
        
        if tier:
            query = query.filter(Subscription.tier == tier)
        
        if status == "active":
            query = query.filter(User.is_active == True)
        elif status == "inactive":
            query = query.filter(User.is_active == False)
        elif status == "verified":
            query = query.filter(User.is_verified == True)
        elif status == "unverified":
            query = query.filter(User.is_verified == False)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * limit
        users = query.offset(offset).limit(limit).all()
        
        # Format user data
        user_data = []
        for user in users:
            user_dict = {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "subscription": {
                    "tier": user.subscription.tier.value if user.subscription else "free",
                    "status": user.subscription.status.value if user.subscription else "inactive",
                    "monthly_usage": user.subscription.monthly_video_minutes_used if user.subscription else 0
                },
                "oauth_providers": {
                    "google": user.google_id is not None,
                    "microsoft": user.microsoft_id is not None,
                    "apple": user.apple_id is not None
                }
            }
            user_data.append(user_dict)
        
        return {
            "users": user_data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users"
        )


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_session)
):
    """Get detailed user information."""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get usage statistics
        usage_stats = db.query(
            func.count(UsageRecord.id).label('total_videos'),
            func.sum(UsageRecord.video_duration_seconds).label('total_duration'),
            func.sum(UsageRecord.file_size_mb).label('total_size')
        ).filter(UsageRecord.user_id == user_id).first()
        
        # Get payment history
        payments = db.query(PaymentHistory).filter(
            PaymentHistory.user_id == user_id
        ).order_by(desc(PaymentHistory.created_at)).limit(10).all()
        
        # Get recent activity
        recent_activity = db.query(UsageRecord).filter(
            UsageRecord.user_id == user_id
        ).order_by(desc(UsageRecord.created_at)).limit(10).all()
        
        return {
            "user": UserResponse.from_db_user(user).dict(),
            "usage_stats": {
                "total_videos": usage_stats.total_videos or 0,
                "total_duration_minutes": (usage_stats.total_duration or 0) / 60,
                "total_size_gb": (usage_stats.total_size or 0) / 1024
            },
            "payments": [
                {
                    "id": payment.id,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "status": payment.status.value,
                    "created_at": payment.created_at.isoformat(),
                    "description": payment.description
                }
                for payment in payments
            ],
            "recent_activity": [
                {
                    "action": activity.action_type,
                    "duration_seconds": activity.video_duration_seconds,
                    "created_at": activity.created_at.isoformat()
                }
                for activity in recent_activity
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user details {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user details"
        )


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    active: bool,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_session)
):
    """Update user active status."""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user.is_active = active
        db.commit()
        
        # Log admin action
        audit_log = AuditLog(
            user_id=admin_user.id,
            action=f"user_status_{'activated' if active else 'deactivated'}",
            resource_type="user",
            resource_id=str(user_id),
            success=True,
            extra_data={"target_user_id": user_id, "new_status": active}
        )
        db.add(audit_log)
        db.commit()
        
        logger.info(f"Admin {admin_user.id} {'activated' if active else 'deactivated'} user {user_id}")
        
        return {"success": True, "message": f"User {'activated' if active else 'deactivated'} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user status {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status"
        )


@router.get("/analytics/usage")
async def get_usage_analytics(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_session),
    days: int = Query(30, ge=1, le=365)
):
    """Get usage analytics for the specified period."""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Daily usage statistics
        daily_usage = db.query(
            func.date(UsageRecord.created_at).label('date'),
            func.count(UsageRecord.id).label('videos'),
            func.sum(UsageRecord.video_duration_seconds).label('duration'),
            func.count(func.distinct(UsageRecord.user_id)).label('unique_users')
        ).filter(
            UsageRecord.created_at >= start_date,
            UsageRecord.action_type == "video_processing"
        ).group_by(
            func.date(UsageRecord.created_at)
        ).order_by(func.date(UsageRecord.created_at)).all()
        
        # User tier distribution
        tier_usage = db.query(
            Subscription.tier,
            func.count(UsageRecord.id).label('videos'),
            func.sum(UsageRecord.video_duration_seconds).label('duration')
        ).join(
            User, User.id == UsageRecord.user_id
        ).join(
            Subscription, Subscription.user_id == User.id
        ).filter(
            UsageRecord.created_at >= start_date,
            UsageRecord.action_type == "video_processing"
        ).group_by(Subscription.tier).all()
        
        # AI service usage
        ai_usage = db.query(
            UsageRecord.ai_service_used,
            func.count(UsageRecord.id).label('count')
        ).filter(
            UsageRecord.created_at >= start_date,
            UsageRecord.ai_service_used.isnot(None)
        ).group_by(UsageRecord.ai_service_used).all()
        
        return {
            "daily_usage": [
                {
                    "date": usage.date.isoformat(),
                    "videos": usage.videos,
                    "duration_minutes": (usage.duration or 0) / 60,
                    "unique_users": usage.unique_users
                }
                for usage in daily_usage
            ],
            "tier_usage": [
                {
                    "tier": usage.tier.value,
                    "videos": usage.videos,
                    "duration_minutes": (usage.duration or 0) / 60
                }
                for usage in tier_usage
            ],
            "ai_service_usage": [
                {
                    "service": usage.ai_service_used,
                    "count": usage.count
                }
                for usage in ai_usage
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting usage analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get usage analytics"
        )


@router.get("/analytics/revenue")
async def get_revenue_analytics(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_session),
    days: int = Query(30, ge=1, le=365)
):
    """Get revenue analytics."""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Daily revenue
        daily_revenue = db.query(
            func.date(PaymentHistory.created_at).label('date'),
            func.sum(PaymentHistory.amount).label('revenue'),
            func.count(PaymentHistory.id).label('transactions')
        ).filter(
            PaymentHistory.created_at >= start_date,
            PaymentHistory.status == "completed"
        ).group_by(
            func.date(PaymentHistory.created_at)
        ).order_by(func.date(PaymentHistory.created_at)).all()
        
        # Monthly recurring revenue (MRR)
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        mrr = db.query(
            func.sum(PaymentHistory.amount).label('mrr')
        ).filter(
            PaymentHistory.created_at >= current_month_start,
            PaymentHistory.status == "completed",
            PaymentHistory.description.like('%subscription%')
        ).scalar() or 0
        
        # Customer lifetime value approximation
        avg_subscription_length_months = 12  # Assumed average
        monthly_churn_rate = 0.05  # Assumed 5% monthly churn
        avg_monthly_revenue_per_user = mrr / max(db.query(Subscription).filter(
            Subscription.tier == SubscriptionTier.PREMIUM,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).count(), 1)
        
        clv = avg_monthly_revenue_per_user / monthly_churn_rate if monthly_churn_rate > 0 else 0
        
        return {
            "daily_revenue": [
                {
                    "date": revenue.date.isoformat(),
                    "revenue": revenue.revenue,
                    "transactions": revenue.transactions
                }
                for revenue in daily_revenue
            ],
            "metrics": {
                "mrr": mrr,
                "estimated_clv": clv,
                "avg_revenue_per_user": avg_monthly_revenue_per_user
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting revenue analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get revenue analytics"
        )


@router.get("/system/health")
async def get_system_health(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_session)
):
    """Get system health metrics."""
    try:
        # Database health
        db_health = True
        try:
            db.execute("SELECT 1")
        except:
            db_health = False
        
        # Redis health
        redis_health = True
        try:
            from app.database.base import get_redis
            redis_client = get_redis()
            if redis_client:
                redis_client.ping()
        except:
            redis_health = False
        
        # Recent error logs
        recent_errors = db.query(AuditLog).filter(
            AuditLog.success == False,
            AuditLog.created_at >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        # System metrics
        active_sessions = db.query(User).filter(
            User.last_login >= datetime.utcnow() - timedelta(minutes=30)
        ).count()
        
        return {
            "status": "healthy" if (db_health and redis_health) else "degraded",
            "services": {
                "database": "up" if db_health else "down",
                "redis": "up" if redis_health else "down"
            },
            "metrics": {
                "active_sessions": active_sessions,
                "recent_errors_24h": recent_errors
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system health"
        )