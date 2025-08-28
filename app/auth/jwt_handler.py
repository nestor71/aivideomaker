from datetime import datetime, timedelta
from typing import Dict, Optional
from jose import JWTError, jwt
from app.core.config import settings
from app.core.logger import logger


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    
    to_encode.update({"exp": expire})
    
    try:
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"Error creating access token: {e}")
        raise


def decode_access_token(token: str) -> Optional[Dict]:
    """Decode JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {e}")
        return None


def create_refresh_token(user_id: int) -> str:
    """Create refresh token for user."""
    data = {
        "sub": str(user_id),
        "type": "refresh"
    }
    # Refresh tokens last 30 days
    expires_delta = timedelta(days=30)
    return create_access_token(data, expires_delta)


def create_verification_token(user_id: int, email: str) -> str:
    """Create email verification token."""
    data = {
        "sub": str(user_id),
        "email": email,
        "type": "verification"
    }
    # Verification tokens last 24 hours
    expires_delta = timedelta(hours=24)
    return create_access_token(data, expires_delta)