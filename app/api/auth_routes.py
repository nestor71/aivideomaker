from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
import secrets

from app.database.base import get_session
from app.database.models import User
from app.schemas.auth import (
    UserCreate, UserLogin, UserResponse, Token, 
    PasswordReset, EmailVerification, OAuthCallback
)
from app.services.auth_service import auth_service
from app.services.oauth_service import oauth_service
from app.auth.dependencies import get_current_user, rate_limit_moderate
from app.core.logger import logger

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register", response_model=Token)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_session),
    _: bool = Depends(rate_limit_moderate)
):
    """Register new user."""
    try:
        # Create user
        user = await auth_service.create_user(db, user_data)
        
        # Create tokens
        token_data = await auth_service.create_user_tokens(user)
        
        # TODO: Send verification email
        logger.info(f"User registered: {user.email}")
        
        return token_data
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=Token)
async def login(
    response: Response,
    user_data: UserLogin,
    db: Session = Depends(get_session),
    _: bool = Depends(rate_limit_moderate)
):
    """Login user."""
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(
            db, user_data.email, user_data.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Create tokens
        token_data = await auth_service.create_user_tokens(user)
        
        # Set HTTP-only cookie for better security
        response.set_cookie(
            key="access_token",
            value=token_data["access_token"],
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=86400  # 24 hours
        )
        
        logger.info(f"User logged in: {user.email}")
        return token_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/logout")
async def logout(response: Response):
    """Logout user."""
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Optional[UserResponse] = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get current user information."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Refresh user data from database
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_db_user(user)


# OAuth Routes
@router.get("/oauth/providers")
async def get_oauth_providers():
    """Get available OAuth providers."""
    providers = oauth_service.get_available_providers()
    return {"providers": providers}


@router.get("/oauth/{provider}/authorize")
async def oauth_authorize(
    provider: str,
    request: Request,
    response: Response
):
    """Start OAuth authorization flow."""
    oauth_provider = oauth_service.get_provider_service(provider)
    
    if not oauth_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth provider not found"
        )
    
    try:
        auth_url, state = await oauth_provider.get_authorization_url()
        
        # Store state in session for CSRF protection
        response.set_cookie(
            key=f"oauth_state_{provider}",
            value=state,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=600  # 10 minutes
        )
        
        return {"auth_url": auth_url}
        
    except Exception as e:
        logger.error(f"OAuth authorize error for {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authorization failed"
        )


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    response: Response,
    code: str,
    state: str,
    db: Session = Depends(get_session)
):
    """Handle OAuth callback."""
    oauth_provider = oauth_service.get_provider_service(provider)
    
    if not oauth_provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth provider not found"
        )
    
    # Verify state for CSRF protection
    stored_state = request.cookies.get(f"oauth_state_{provider}")
    if not stored_state or stored_state != state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter"
        )
    
    try:
        # Exchange code for token
        token_data = await oauth_provider.exchange_code_for_token(code)
        
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange code for token"
            )
        
        # Get user info
        access_token = token_data.get("access_token")
        
        if provider == "apple":
            # Apple returns user info in id_token
            id_token = token_data.get("id_token")
            user_info = await oauth_provider.decode_identity_token(id_token)
        else:
            user_info = await oauth_provider.get_user_info(access_token)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get user information"
            )
        
        # Create or find user
        user = await auth_service.create_oauth_user(
            db=db,
            email=user_info["email"],
            full_name=user_info["full_name"],
            provider=provider,
            provider_id=user_info["provider_id"],
            avatar_url=user_info.get("avatar_url")
        )
        
        # Create tokens
        token_response = await auth_service.create_user_tokens(user)
        
        # Set cookie and clean up state
        response.set_cookie(
            key="access_token",
            value=token_response["access_token"],
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=86400
        )
        response.delete_cookie(f"oauth_state_{provider}")
        
        # Redirect to frontend success page
        redirect_url = f"/?login=success&provider={provider}"
        return RedirectResponse(url=redirect_url, status_code=302)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback error for {provider}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth authentication failed"
        )


# Apple Sign-In handles POST callback
@router.post("/oauth/apple/callback")
async def apple_oauth_callback(
    request: Request,
    response: Response,
    code: str = Form(...),
    state: str = Form(...),
    id_token: Optional[str] = Form(None),
    user: Optional[str] = Form(None),  # Apple sends user info only on first auth
    db: Session = Depends(get_session)
):
    """Handle Apple Sign-In POST callback."""
    return await oauth_callback("apple", request, response, code, state, db)


@router.post("/verify-email")
async def verify_email(
    verification: EmailVerification,
    db: Session = Depends(get_session)
):
    """Verify user email."""
    try:
        success = await auth_service.verify_email(db, verification.token)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token"
            )
        
        return {"message": "Email verified successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email verification failed"
        )


@router.post("/forgot-password")
async def forgot_password(
    password_reset: PasswordReset,
    db: Session = Depends(get_session),
    _: bool = Depends(rate_limit_moderate)
):
    """Request password reset."""
    # TODO: Implement password reset email
    # For now, just return success (don't reveal if email exists)
    return {"message": "If the email exists, a reset link has been sent"}


@router.get("/check-auth")
async def check_auth(current_user: Optional[UserResponse] = Depends(get_current_user)):
    """Check if user is authenticated."""
    return {
        "authenticated": current_user is not None,
        "user": current_user
    }