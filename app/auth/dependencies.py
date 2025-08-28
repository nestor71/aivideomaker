from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.base import get_session
from app.database.models import User, SubscriptionTier
from app.auth.jwt_handler import decode_access_token
from app.core.logger import logger

# Security scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_session)
) -> Optional[User]:
    """Get current user from JWT token or return None for anonymous users."""
    
    # Check for token in Authorization header
    token = None
    if credentials:
        token = credentials.credentials
    
    # Check for token in cookies as fallback
    if not token:
        token = request.cookies.get("access_token")
    
    if not token:
        return None
    
    # Decode token
    payload = decode_access_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user and user.is_active:
            # Update last login
            from sqlalchemy.sql import func
            user.last_login = func.now()
            db.commit()
            return user
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
    
    return None


async def get_current_active_user(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Get current active user or raise 401 if not authenticated."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return current_user


async def get_current_user_or_anonymous(
    current_user: Optional[User] = Depends(get_current_user)
) -> Optional[User]:
    """Get current user or allow anonymous access."""
    return current_user


async def require_subscription(
    tier: SubscriptionTier,
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Require user to have specific subscription tier."""
    if not current_user.subscription:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subscription required"
        )
    
    if current_user.subscription.tier != tier and tier == SubscriptionTier.PREMIUM:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Premium subscription required"
        )
    
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Require admin privileges."""
    if current_user.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return current_user


class RateLimitDependency:
    """Rate limiting dependency factory."""
    
    def __init__(self, max_requests: int, window_minutes: int):
        self.max_requests = max_requests
        self.window_minutes = window_minutes
    
    async def __call__(self, request: Request, current_user: Optional[User] = Depends(get_current_user)):
        """Check rate limits for user or IP."""
        from app.services.rate_limiter import rate_limiter
        
        # Use user ID if authenticated, otherwise use IP
        identifier = str(current_user.id) if current_user else request.client.host
        
        if not await rate_limiter.check_rate_limit(
            identifier, 
            self.max_requests, 
            self.window_minutes
        ):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        
        return True


# Common rate limit dependencies
rate_limit_strict = RateLimitDependency(max_requests=10, window_minutes=1)
rate_limit_moderate = RateLimitDependency(max_requests=60, window_minutes=1)
rate_limit_relaxed = RateLimitDependency(max_requests=300, window_minutes=1)