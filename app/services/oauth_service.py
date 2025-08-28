from typing import Dict, Optional, Tuple
import httpx
import secrets
import base64
import hashlib
from urllib.parse import urlencode, parse_qs
from authlib.integrations.httpx_client import AsyncOAuth2Client
from app.core.config import settings
from app.core.logger import logger


class GoogleOAuthService:
    """Google OAuth2 service."""
    
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = "http://localhost:8000/api/auth/oauth/google/callback"
        self.scopes = ["openid", "email", "profile"]
    
    async def get_authorization_url(self) -> Tuple[str, str]:
        """Get Google OAuth authorization URL and state."""
        state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "response_type": "code",
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        return auth_url, state
    
    async def exchange_code_for_token(self, code: str) -> Optional[Dict]:
        """Exchange authorization code for access token."""
        try:
            async with httpx.AsyncClient() as client:
                token_data = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri
                }
                
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Google token exchange failed: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error exchanging Google code for token: {e}")
            return None
    
    async def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Get user information from Google."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    return {
                        "provider_id": user_data.get("id"),
                        "email": user_data.get("email"),
                        "full_name": user_data.get("name"),
                        "avatar_url": user_data.get("picture"),
                        "verified_email": user_data.get("verified_email", False)
                    }
                else:
                    logger.error(f"Google user info failed: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting Google user info: {e}")
            return None


class MicrosoftOAuthService:
    """Microsoft OAuth2 service."""
    
    def __init__(self):
        self.client_id = settings.MICROSOFT_CLIENT_ID
        self.client_secret = settings.MICROSOFT_CLIENT_SECRET
        self.tenant_id = settings.MICROSOFT_TENANT_ID
        self.redirect_uri = "http://localhost:8000/api/auth/oauth/microsoft/callback"
        self.scopes = ["openid", "profile", "email"]
    
    async def get_authorization_url(self) -> Tuple[str, str]:
        """Get Microsoft OAuth authorization URL and state."""
        state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "response_type": "code",
            "state": state,
            "response_mode": "query"
        }
        
        auth_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize?{urlencode(params)}"
        return auth_url, state
    
    async def exchange_code_for_token(self, code: str) -> Optional[Dict]:
        """Exchange authorization code for access token."""
        try:
            async with httpx.AsyncClient() as client:
                token_data = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri
                }
                
                response = await client.post(
                    f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Microsoft token exchange failed: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error exchanging Microsoft code for token: {e}")
            return None
    
    async def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Get user information from Microsoft."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    return {
                        "provider_id": user_data.get("id"),
                        "email": user_data.get("mail") or user_data.get("userPrincipalName"),
                        "full_name": user_data.get("displayName"),
                        "avatar_url": None,  # Microsoft Graph requires separate call for photo
                        "verified_email": True  # Microsoft accounts are verified
                    }
                else:
                    logger.error(f"Microsoft user info failed: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting Microsoft user info: {e}")
            return None


class AppleOAuthService:
    """Apple Sign-In OAuth2 service."""
    
    def __init__(self):
        self.client_id = settings.APPLE_CLIENT_ID
        self.client_secret = settings.APPLE_CLIENT_SECRET
        self.key_id = settings.APPLE_KEY_ID
        self.team_id = settings.APPLE_TEAM_ID
        self.redirect_uri = "http://localhost:8000/api/auth/oauth/apple/callback"
        self.scopes = ["name", "email"]
    
    async def get_authorization_url(self) -> Tuple[str, str]:
        """Get Apple OAuth authorization URL and state."""
        state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "response_type": "code",
            "state": state,
            "response_mode": "form_post"
        }
        
        auth_url = f"https://appleid.apple.com/auth/authorize?{urlencode(params)}"
        return auth_url, state
    
    async def exchange_code_for_token(self, code: str) -> Optional[Dict]:
        """Exchange authorization code for access token."""
        try:
            # Apple requires client_secret to be a JWT
            client_secret = self._generate_client_secret()
            
            async with httpx.AsyncClient() as client:
                token_data = {
                    "client_id": self.client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri
                }
                
                response = await client.post(
                    "https://appleid.apple.com/auth/token",
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Apple token exchange failed: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error exchanging Apple code for token: {e}")
            return None
    
    def _generate_client_secret(self) -> str:
        """Generate Apple client secret JWT."""
        # This is a simplified version - in production, you'd use proper JWT library
        # and load the private key from Apple
        import time
        import jwt
        
        now = int(time.time())
        
        payload = {
            "iss": self.team_id,
            "aud": "https://appleid.apple.com",
            "sub": self.client_id,
            "iat": now,
            "exp": now + 3600
        }
        
        # Note: You need to replace this with actual Apple private key
        # For now, return the static secret from config
        return self.client_secret
    
    async def decode_identity_token(self, id_token: str) -> Optional[Dict]:
        """Decode Apple identity token to get user info."""
        try:
            # In production, you should verify the JWT signature
            import jwt
            
            # Decode without verification for development
            # In production, verify with Apple's public keys
            payload = jwt.decode(id_token, options={"verify_signature": False})
            
            return {
                "provider_id": payload.get("sub"),
                "email": payload.get("email"),
                "full_name": None,  # Apple doesn't always provide name
                "avatar_url": None,
                "verified_email": payload.get("email_verified", False)
            }
            
        except Exception as e:
            logger.error(f"Error decoding Apple identity token: {e}")
            return None


class OAuthService:
    """Main OAuth service that coordinates all providers."""
    
    def __init__(self):
        self.google = GoogleOAuthService()
        self.microsoft = MicrosoftOAuthService()
        self.apple = AppleOAuthService()
    
    def get_provider_service(self, provider: str):
        """Get OAuth service for provider."""
        services = {
            "google": self.google,
            "microsoft": self.microsoft,
            "apple": self.apple
        }
        return services.get(provider)
    
    def is_provider_configured(self, provider: str) -> bool:
        """Check if OAuth provider is configured."""
        configs = {
            "google": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
            "microsoft": bool(settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET),
            "apple": bool(settings.APPLE_CLIENT_ID and settings.APPLE_CLIENT_SECRET)
        }
        return configs.get(provider, False)
    
    def get_available_providers(self) -> list:
        """Get list of configured OAuth providers."""
        providers = []
        for provider in ["google", "microsoft", "apple"]:
            if self.is_provider_configured(provider):
                providers.append(provider)
        return providers


# Global instance
oauth_service = OAuthService()