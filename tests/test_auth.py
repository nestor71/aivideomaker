"""
Authentication and authorization tests
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models import User, UserRole
from app.services.auth_service import AuthService


class TestUserRegistration:
    """Test user registration functionality"""
    
    def test_register_valid_user(self, client: TestClient, test_user_data):
        """Test successful user registration"""
        response = client.post("/api/auth/register", json=test_user_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == test_user_data["email"]
        assert data["user"]["full_name"] == test_user_data["full_name"]
        assert data["user"]["subscription_tier"] == "free"
        assert data["user"]["role"] == "user"
    
    def test_register_duplicate_email(self, client: TestClient, test_user_data):
        """Test registration with duplicate email fails"""
        # First registration
        response = client.post("/api/auth/register", json=test_user_data)
        assert response.status_code == 200
        
        # Second registration with same email
        response = client.post("/api/auth/register", json=test_user_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    
    def test_register_invalid_email(self, client: TestClient):
        """Test registration with invalid email fails"""
        invalid_data = {
            "email": "invalid-email",
            "password": "TestPass123",
            "full_name": "Test User"
        }
        
        response = client.post("/api/auth/register", json=invalid_data)
        assert response.status_code == 422
    
    def test_register_weak_password(self, client: TestClient):
        """Test registration with weak password fails"""
        weak_password_data = {
            "email": "test@example.com",
            "password": "123",  # Too short
            "full_name": "Test User"
        }
        
        response = client.post("/api/auth/register", json=weak_password_data)
        assert response.status_code == 422
    
    def test_register_missing_fields(self, client: TestClient):
        """Test registration with missing fields fails"""
        incomplete_data = {
            "email": "test@example.com"
            # Missing password and full_name
        }
        
        response = client.post("/api/auth/register", json=incomplete_data)
        assert response.status_code == 422


class TestUserLogin:
    """Test user login functionality"""
    
    def test_login_valid_credentials(self, client: TestClient, test_user_data):
        """Test successful login with valid credentials"""
        # First register the user
        client.post("/api/auth/register", json=test_user_data)
        
        # Then login
        login_data = {
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        }
        
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == test_user_data["email"]
    
    def test_login_invalid_credentials(self, client: TestClient, test_user_data):
        """Test login with invalid credentials fails"""
        # Register user first
        client.post("/api/auth/register", json=test_user_data)
        
        # Try login with wrong password
        login_data = {
            "email": test_user_data["email"],
            "password": "wrongpassword"
        }
        
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with nonexistent user fails"""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "TestPass123"
        }
        
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 401
    
    def test_login_inactive_user(self, client: TestClient, test_user_data, db_session: Session):
        """Test login with inactive user fails"""
        # Register user
        client.post("/api/auth/register", json=test_user_data)
        
        # Deactivate user in database
        user = db_session.query(User).filter(User.email == test_user_data["email"]).first()
        user.is_active = False
        db_session.commit()
        
        # Try to login
        login_data = {
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        }
        
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 401


class TestUserProfile:
    """Test user profile functionality"""
    
    def test_get_current_user(self, client: TestClient, auth_headers):
        """Test getting current user profile"""
        response = client.get("/api/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "email" in data
        assert "full_name" in data
        assert "subscription_tier" in data
        assert data["subscription_tier"] == "free"
    
    def test_get_current_user_without_auth(self, client: TestClient):
        """Test getting current user without authentication fails"""
        response = client.get("/api/auth/me")
        assert response.status_code == 401
    
    def test_get_current_user_invalid_token(self, client: TestClient):
        """Test getting current user with invalid token fails"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 401


class TestTokenRefresh:
    """Test token refresh functionality"""
    
    def test_refresh_valid_token(self, client: TestClient, test_user_data):
        """Test refreshing a valid token"""
        # Register and login
        client.post("/api/auth/register", json=test_user_data)
        login_response = client.post("/api/auth/login", json={
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        })
        
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh the token
        response = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    def test_refresh_invalid_token(self, client: TestClient):
        """Test refreshing an invalid token fails"""
        response = client.post("/api/auth/refresh", json={
            "refresh_token": "invalid_token"
        })
        
        assert response.status_code == 401


class TestPasswordReset:
    """Test password reset functionality"""
    
    def test_request_password_reset(self, client: TestClient, test_user_data, mock_email_service):
        """Test password reset request"""
        # Register user first
        client.post("/api/auth/register", json=test_user_data)
        
        # Request password reset
        response = client.post("/api/auth/forgot-password", json={
            "email": test_user_data["email"]
        })
        
        assert response.status_code == 200
        assert "message" in response.json()
        
        # Verify email was sent
        mock_email_service.assert_called_once()
    
    def test_request_password_reset_nonexistent_user(self, client: TestClient):
        """Test password reset for nonexistent user still returns success (security)"""
        response = client.post("/api/auth/forgot-password", json={
            "email": "nonexistent@example.com"
        })
        
        # Should return success for security reasons
        assert response.status_code == 200


class TestAccountManagement:
    """Test account management functionality"""
    
    def test_update_profile(self, client: TestClient, auth_headers):
        """Test updating user profile"""
        update_data = {
            "full_name": "Updated Name"
        }
        
        response = client.put("/api/auth/profile", json=update_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"
    
    def test_change_password(self, client: TestClient, auth_headers, test_user_data):
        """Test changing password"""
        change_data = {
            "current_password": test_user_data["password"],
            "new_password": "NewTestPass123"
        }
        
        response = client.put("/api/auth/change-password", json=change_data, headers=auth_headers)
        
        assert response.status_code == 200
        assert "message" in response.json()
    
    def test_change_password_wrong_current(self, client: TestClient, auth_headers):
        """Test changing password with wrong current password fails"""
        change_data = {
            "current_password": "wrongpassword",
            "new_password": "NewTestPass123"
        }
        
        response = client.put("/api/auth/change-password", json=change_data, headers=auth_headers)
        
        assert response.status_code == 400
    
    def test_delete_account(self, client: TestClient, auth_headers):
        """Test deleting user account"""
        response = client.delete("/api/auth/account", headers=auth_headers)
        
        assert response.status_code == 200
        assert "message" in response.json()
        
        # Verify user can't access profile after deletion
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 401


class TestUserRoles:
    """Test user role functionality"""
    
    def test_admin_access(self, client: TestClient, admin_auth_headers):
        """Test admin user can access admin routes"""
        response = client.get("/api/admin/users", headers=admin_auth_headers)
        assert response.status_code == 200
    
    def test_regular_user_admin_access_denied(self, client: TestClient, auth_headers):
        """Test regular user cannot access admin routes"""
        response = client.get("/api/admin/users", headers=auth_headers)
        assert response.status_code == 403
    
    def test_role_based_permissions(self, client: TestClient, auth_headers, admin_auth_headers):
        """Test different permissions for different roles"""
        # Regular user should not be able to access admin dashboard
        response = client.get("/api/admin/dashboard", headers=auth_headers)
        assert response.status_code == 403
        
        # Admin user should be able to access admin dashboard
        response = client.get("/api/admin/dashboard", headers=admin_auth_headers)
        assert response.status_code == 200