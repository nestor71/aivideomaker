from pydantic_settings import BaseSettings
from pydantic import Field, validator
import os
import secrets
from typing import List, Optional, Union

class Settings(BaseSettings):
    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = True
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # CORS settings
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000,http://localhost:8000"
    
    @validator('CORS_ORIGINS', pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    CORS_ALLOW_CREDENTIALS: bool = True
    
    # File validation settings
    STRICT_FILE_VALIDATION: bool = os.getenv("STRICT_FILE_VALIDATION", "false").lower() == "true"
    UPLOAD_DIR: str = "app/static/uploads"
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./aivideomaker.db")
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    
    # AI Services
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # ElevenLabs (Premium Voice Cloning + Lip Sync)
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "")  # Default voice
    ELEVENLABS_MODEL_ID: str = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    
    # OAuth Providers
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    MICROSOFT_CLIENT_ID: str = os.getenv("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET: str = os.getenv("MICROSOFT_CLIENT_SECRET", "")
    MICROSOFT_TENANT_ID: str = os.getenv("MICROSOFT_TENANT_ID", "common")
    
    APPLE_CLIENT_ID: str = os.getenv("APPLE_CLIENT_ID", "")
    APPLE_CLIENT_SECRET: str = os.getenv("APPLE_CLIENT_SECRET", "")
    APPLE_KEY_ID: str = os.getenv("APPLE_KEY_ID", "")
    APPLE_TEAM_ID: str = os.getenv("APPLE_TEAM_ID", "")
    
    # Email Configuration
    EMAIL_HOST: str = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USERNAME: str = os.getenv("EMAIL_USERNAME", "")
    EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@aivideomaker.com")
    EMAIL_USE_TLS: bool = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
    
    # Admin Configuration
    ADMIN_EMAIL_ADDRESSES: List[str] = Field(default_factory=list)
    
    @validator('ADMIN_EMAIL_ADDRESSES', pre=True, always=True)
    def parse_admin_emails(cls, v):
        if isinstance(v, str):
            if not v:
                return []
            # Split by comma and strip whitespace
            return [email.strip() for email in v.split(',') if email.strip()]
        elif isinstance(v, list):
            return v
        return []
    
    # YouTube (legacy)
    YOUTUBE_CLIENT_ID: str = os.getenv("YOUTUBE_CLIENT_ID", "")
    YOUTUBE_CLIENT_SECRET: str = os.getenv("YOUTUBE_CLIENT_SECRET", "")
    
    # Stripe
    STRIPE_PUBLIC_KEY: str = os.getenv("STRIPE_PUBLIC_KEY", "")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    # Subscription pricing (in cents) - STRATEGIA ELEVENLABS
    PREMIUM_MONTHLY_PRICE: int = 1999  # €19.99
    PREMIUM_YEARLY_PRICE: int = 19900  # €199.00 (2 mesi gratis)
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    # Free tier limits (STRATEGIA SICURA)
    FREE_TIER_MONTHLY_VIDEOS: int = int(os.getenv("FREE_TIER_MONTHLY_VIDEOS", "2"))
    FREE_TIER_MONTHLY_MINUTES: float = 1.0
    FREE_TIER_MAX_DURATION_SECONDS: int = 30
    FREE_TIER_MAX_QUALITY: str = "720p"
    FREE_TIER_CONCURRENT_UPLOADS: int = 1
    FREE_TIER_WATERMARK: bool = True
    
    # Premium tier limits (STRATEGIA ELEVENLABS)
    PREMIUM_TIER_MONTHLY_VIDEOS: int = 15  # 15 video al mese
    PREMIUM_TIER_MONTHLY_MINUTES: float = 75.0  # 15 × 5 min
    PREMIUM_TIER_MAX_DURATION_SECONDS: int = 300  # 5 minuti max
    PREMIUM_TIER_MAX_QUALITY: str = "1080p"
    PREMIUM_TIER_CONCURRENT_UPLOADS: int = 3
    PREMIUM_TIER_WATERMARK: bool = False
    PREMIUM_TIER_ELEVENLABS: bool = True  # ElevenLabs + Lip Sync
    PREMIUM_TIER_VOICE_CLONING: bool = True
    
    # Email settings (for notifications)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@aivideomaker.com")
    
    # Celery (for background tasks)
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    
    # GDPR & Privacy
    DATA_RETENTION_DAYS: int = int(os.getenv("DATA_RETENTION_DAYS", "365"))
    COOKIE_CONSENT_REQUIRED: bool = os.getenv("COOKIE_CONSENT_REQUIRED", "true").lower() == "true"
    
    # Monitoring
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()