from typing import Optional
import time
import json
from app.database.base import get_redis
from app.core.logger import logger


class RateLimiter:
    """Redis-based rate limiter."""
    
    def __init__(self):
        self.redis = get_redis()
    
    async def check_rate_limit(
        self, 
        identifier: str, 
        max_requests: int, 
        window_minutes: int
    ) -> bool:
        """
        Check if identifier is within rate limits.
        Returns True if within limits, False if exceeded.
        """
        if not self.redis:
            # No Redis available, allow all requests
            logger.warning("Redis not available, rate limiting disabled")
            return True
        
        try:
            window_seconds = window_minutes * 60
            current_time = int(time.time())
            window_start = current_time - window_seconds
            
            key = f"rate_limit:{identifier}"
            
            # Use sliding window log algorithm
            pipe = self.redis.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, window_seconds + 60)  # Extra buffer
            
            results = pipe.execute()
            current_count = results[1]
            
            if current_count >= max_requests:
                logger.warning(f"Rate limit exceeded for {identifier}: {current_count}/{max_requests}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit for {identifier}: {e}")
            # On error, allow the request (fail open)
            return True
    
    async def get_rate_limit_info(
        self, 
        identifier: str, 
        window_minutes: int
    ) -> dict:
        """Get rate limit information for identifier."""
        if not self.redis:
            return {"requests": 0, "window_minutes": window_minutes, "available": True}
        
        try:
            window_seconds = window_minutes * 60
            current_time = int(time.time())
            window_start = current_time - window_seconds
            
            key = f"rate_limit:{identifier}"
            
            # Clean up old entries and count current
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            results = pipe.execute()
            
            current_count = results[1]
            
            return {
                "requests": current_count,
                "window_minutes": window_minutes,
                "window_start": window_start,
                "current_time": current_time
            }
            
        except Exception as e:
            logger.error(f"Error getting rate limit info for {identifier}: {e}")
            return {"requests": 0, "window_minutes": window_minutes, "error": str(e)}
    
    async def reset_rate_limit(self, identifier: str) -> bool:
        """Reset rate limit for identifier (admin function)."""
        if not self.redis:
            return False
        
        try:
            key = f"rate_limit:{identifier}"
            self.redis.delete(key)
            logger.info(f"Rate limit reset for {identifier}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting rate limit for {identifier}: {e}")
            return False


class UsageTracker:
    """Track usage for billing and quota enforcement."""
    
    def __init__(self):
        self.redis = get_redis()
    
    async def track_usage(
        self,
        user_id: int,
        action_type: str,
        video_duration_seconds: float = 0,
        file_size_mb: float = 0
    ) -> bool:
        """Track user usage."""
        if not self.redis:
            return True
        
        try:
            current_time = int(time.time())
            month_key = f"usage:{user_id}:{time.strftime('%Y-%m')}"
            
            # Track monthly video minutes
            if video_duration_seconds > 0:
                video_minutes = video_duration_seconds / 60.0
                self.redis.incrbyfloat(f"{month_key}:minutes", video_minutes)
                self.redis.expire(f"{month_key}:minutes", 32 * 24 * 3600)  # 32 days
            
            # Track file size
            if file_size_mb > 0:
                self.redis.incrbyfloat(f"{month_key}:size_mb", file_size_mb)
                self.redis.expire(f"{month_key}:size_mb", 32 * 24 * 3600)
            
            # Track action count
            action_key = f"{month_key}:actions:{action_type}"
            self.redis.incr(action_key)
            self.redis.expire(action_key, 32 * 24 * 3600)
            
            return True
            
        except Exception as e:
            logger.error(f"Error tracking usage for user {user_id}: {e}")
            return False
    
    async def get_monthly_usage(self, user_id: int) -> dict:
        """Get monthly usage for user."""
        if not self.redis:
            return {"minutes": 0, "size_mb": 0, "actions": {}}
        
        try:
            month_key = f"usage:{user_id}:{time.strftime('%Y-%m')}"
            
            minutes = float(self.redis.get(f"{month_key}:minutes") or 0)
            size_mb = float(self.redis.get(f"{month_key}:size_mb") or 0)
            
            # Get all action counts
            action_keys = self.redis.keys(f"{month_key}:actions:*")
            actions = {}
            for key in action_keys:
                action_type = key.split(':')[-1]
                actions[action_type] = int(self.redis.get(key) or 0)
            
            return {
                "minutes": minutes,
                "size_mb": size_mb,
                "actions": actions,
                "month": time.strftime('%Y-%m')
            }
            
        except Exception as e:
            logger.error(f"Error getting usage for user {user_id}: {e}")
            return {"minutes": 0, "size_mb": 0, "actions": {}, "error": str(e)}


# Global instances
rate_limiter = RateLimiter()
usage_tracker = UsageTracker()