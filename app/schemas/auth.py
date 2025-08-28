from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
from app.database.models import UserRole, SubscriptionTier


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=100)
    agreed_to_terms: bool = True
    gdpr_consent: bool = True
    marketing_consent: Optional[bool] = False
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Schema for user profile updates."""
    full_name: Optional[str] = None
    marketing_consent: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user response."""
    id: int
    role: UserRole
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    
    # OAuth provider info (for display purposes)
    has_google: bool = False
    has_microsoft: bool = False
    has_apple: bool = False
    
    # Subscription info
    subscription_tier: Optional[SubscriptionTier] = None
    subscription_active: bool = False
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_db_user(cls, user):
        """Create UserResponse from database User model."""
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
            last_login=user.last_login,
            has_google=user.google_id is not None,
            has_microsoft=user.microsoft_id is not None,
            has_apple=user.apple_id is not None,
            subscription_tier=user.subscription.tier if user.subscription else SubscriptionTier.FREE,
            subscription_active=user.subscription.status.value == "active" if user.subscription else False
        )


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    user: UserResponse


class TokenData(BaseModel):
    """Token payload data."""
    email: Optional[str] = None
    user_id: Optional[int] = None


class PasswordReset(BaseModel):
    """Password reset request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('new_password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class EmailVerification(BaseModel):
    """Email verification."""
    token: str


class OAuthCallback(BaseModel):
    """OAuth callback data."""
    code: str
    state: Optional[str] = None