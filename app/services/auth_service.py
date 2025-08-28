from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from jose import JWTError, jwt

from app.database.models import User, Subscription, SubscriptionTier, SubscriptionStatus, UserRole
from app.database.base import get_session
from app.schemas.auth import UserCreate, UserLogin, UserResponse
from app.auth.password import get_password_hash, verify_password
from app.auth.jwt_handler import create_access_token, create_verification_token
from app.core.logger import logger
from app.core.config import settings
from app.services.email_service import email_service
from datetime import timedelta
import uuid

# OAuth2 scheme for token extraction
oauth2_scheme = HTTPBearer()


class AuthService:
    """Authentication service."""
    
    @staticmethod
    async def create_user(db: Session, user_data: UserCreate) -> User:
        """Create a new user."""
        try:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == user_data.email).first()
            if existing_user:
                raise ValueError("User with this email already exists")
            
            # Hash password
            hashed_password = get_password_hash(user_data.password)
            
            # Create user
            db_user = User(
                email=user_data.email,
                hashed_password=hashed_password,
                full_name=user_data.full_name,
                agreed_to_terms=user_data.agreed_to_terms,
                gdpr_consent=user_data.gdpr_consent,
                marketing_consent=user_data.marketing_consent,
                verification_token=str(uuid.uuid4()),
                is_verified=False  # Email verification required
            )
            
            db.add(db_user)
            db.flush()  # Get the user ID
            
            # Create free subscription
            subscription = Subscription(
                user_id=db_user.id,
                tier=SubscriptionTier.FREE,
                status=SubscriptionStatus.ACTIVE,
                monthly_video_minutes_limit=10.0,  # 10 minutes for free tier
                concurrent_uploads_limit=1,
                max_video_duration_seconds=60,
                max_export_quality="720p",
                watermark_enabled=True
            )
            
            db.add(subscription)
            db.commit()
            
            # Send welcome email
            try:
                verification_link = f"{settings.BASE_URL}/verify-email?token={db_user.verification_token}" if hasattr(settings, 'BASE_URL') else None
                email_service.send_welcome_email(
                    user_email=db_user.email,
                    user_name=db_user.full_name or db_user.email.split('@')[0],
                    verification_link=verification_link
                )
                
                # Send admin notification
                email_service.send_new_user_notification(
                    user_email=db_user.email,
                    user_name=db_user.full_name or db_user.email.split('@')[0]
                )
            except Exception as email_error:
                logger.warning(f"Failed to send welcome email to {db_user.email}: {email_error}")
            
            logger.info(f"User created: {db_user.email} (ID: {db_user.id})")
            return db_user
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Database integrity error creating user: {e}")
            raise ValueError("User with this email already exists")
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating user: {e}")
            raise
    
    @staticmethod
    async def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate user with email/password."""
        try:
            user = db.query(User).filter(User.email == email).first()
            
            if not user:
                logger.warning(f"Login attempt with non-existent email: {email}")
                return None
            
            if not user.hashed_password:
                logger.warning(f"Login attempt for OAuth-only user: {email}")
                return None
            
            if not verify_password(password, user.hashed_password):
                logger.warning(f"Invalid password for user: {email}")
                return None
            
            if not user.is_active:
                logger.warning(f"Login attempt for inactive user: {email}")
                return None
            
            logger.info(f"User authenticated: {email}")
            return user
            
        except Exception as e:
            logger.error(f"Error authenticating user {email}: {e}")
            return None
    
    @staticmethod
    async def create_oauth_user(
        db: Session, 
        email: str, 
        full_name: str, 
        provider: str, 
        provider_id: str,
        avatar_url: Optional[str] = None
    ) -> User:
        """Create user from OAuth provider."""
        try:
            # Check if user exists with this email
            existing_user = db.query(User).filter(User.email == email).first()
            
            if existing_user:
                # Link OAuth account to existing user
                if provider == "google" and not existing_user.google_id:
                    existing_user.google_id = provider_id
                elif provider == "microsoft" and not existing_user.microsoft_id:
                    existing_user.microsoft_id = provider_id
                elif provider == "apple" and not existing_user.apple_id:
                    existing_user.apple_id = provider_id
                
                # Update profile if needed
                if not existing_user.full_name and full_name:
                    existing_user.full_name = full_name
                if not existing_user.avatar_url and avatar_url:
                    existing_user.avatar_url = avatar_url
                
                existing_user.is_verified = True  # OAuth accounts are pre-verified
                db.commit()
                
                logger.info(f"OAuth account linked for user: {email} ({provider})")
                return existing_user
            
            # Create new OAuth user
            oauth_fields = {}
            if provider == "google":
                oauth_fields["google_id"] = provider_id
            elif provider == "microsoft":
                oauth_fields["microsoft_id"] = provider_id
            elif provider == "apple":
                oauth_fields["apple_id"] = provider_id
            
            db_user = User(
                email=email,
                full_name=full_name,
                avatar_url=avatar_url,
                is_verified=True,  # OAuth accounts are pre-verified
                agreed_to_terms=True,  # Assumed for OAuth
                gdpr_consent=True,    # Assumed for OAuth
                **oauth_fields
            )
            
            db.add(db_user)
            db.flush()
            
            # Create free subscription
            subscription = Subscription(
                user_id=db_user.id,
                tier=SubscriptionTier.FREE,
                status=SubscriptionStatus.ACTIVE,
                monthly_video_minutes_limit=10.0,
                concurrent_uploads_limit=1,
                max_video_duration_seconds=60,
                max_export_quality="720p",
                watermark_enabled=True
            )
            
            db.add(subscription)
            db.commit()
            
            logger.info(f"OAuth user created: {email} via {provider} (ID: {db_user.id})")
            return db_user
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating OAuth user {email} via {provider}: {e}")
            raise
    
    @staticmethod
    async def create_user_tokens(user: User) -> Dict[str, Any]:
        """Create access and refresh tokens for user."""
        try:
            # Access token data
            access_token_data = {
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value
            }
            
            # Create tokens
            access_token = create_access_token(access_token_data)
            refresh_token = create_access_token(
                {"sub": str(user.id), "type": "refresh"},
                expires_delta=timedelta(days=30)
            )
            
            # Create user response
            user_response = UserResponse.from_db_user(user)
            
            return {
                "access_token": access_token,
                "token_type": "bearer", 
                "expires_in": 3600 * 24,  # 24 hours
                "refresh_token": refresh_token,
                "user": user_response
            }
            
        except Exception as e:
            logger.error(f"Error creating tokens for user {user.id}: {e}")
            raise
    
    @staticmethod
    async def verify_email(db: Session, token: str) -> bool:
        """Verify user email with token."""
        try:
            user = db.query(User).filter(User.verification_token == token).first()
            
            if not user:
                logger.warning(f"Email verification attempt with invalid token: {token[:10]}...")
                return False
            
            user.is_verified = True
            user.verification_token = None
            db.commit()
            
            logger.info(f"Email verified for user: {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying email with token {token[:10]}...: {e}")
            return False
    
    @staticmethod
    async def update_user(db: Session, user_id: int, update_data: Dict[str, Any]) -> Optional[User]:
        """Update user profile."""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return None
            
            for field, value in update_data.items():
                if hasattr(user, field):
                    setattr(user, field, value)
            
            db.commit()
            logger.info(f"User updated: {user.email}")
            return user
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user {user_id}: {e}")
            raise


# FastAPI dependencies
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_session)) -> User:
    """Get current authenticated user."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current authenticated admin user."""
    from app.database.models import UserRole
    
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    return current_user


auth_service = AuthService()