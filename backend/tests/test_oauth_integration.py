"""OAuth Integration Tests for RemoteHive RBAC System.

This module tests OAuth authentication flows for Google, LinkedIn, and GitHub providers.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from urllib.parse import parse_qs, urlparse

from backend.main import app
from backend.models.mongodb_models import User, OAuthAccount
from backend.core.security import create_access_token


class TestOAuthIntegration:
    """Test OAuth authentication flows."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_google_oauth_initiate(self, client):
        """Test initiating Google OAuth flow."""
        response = client.get("/api/v1/auth/oauth/google")
        
        assert response.status_code == 302
        location = response.headers["location"]
        
        # Verify redirect URL contains required parameters
        parsed_url = urlparse(location)
        assert "accounts.google.com" in parsed_url.netloc
        assert "/oauth2/auth" in parsed_url.path
        
        query_params = parse_qs(parsed_url.query)
        assert "client_id" in query_params
        assert "redirect_uri" in query_params
        assert "scope" in query_params
        assert "response_type" in query_params
        assert query_params["response_type"][0] == "code"
    
    def test_linkedin_oauth_initiate(self, client):
        """Test initiating LinkedIn OAuth flow."""
        response = client.get("/api/v1/auth/oauth/linkedin")
        
        assert response.status_code == 302
        location = response.headers["location"]
        
        # Verify redirect URL contains required parameters
        parsed_url = urlparse(location)
        assert "linkedin.com" in parsed_url.netloc
        assert "/oauth/v2/authorization" in parsed_url.path
        
        query_params = parse_qs(parsed_url.query)
        assert "client_id" in query_params
        assert "redirect_uri" in query_params
        assert "scope" in query_params
        assert "response_type" in query_params
        assert query_params["response_type"][0] == "code"
    
    def test_github_oauth_initiate(self, client):
        """Test initiating GitHub OAuth flow."""
        response = client.get("/api/v1/auth/oauth/github")
        
        assert response.status_code == 302
        location = response.headers["location"]
        
        # Verify redirect URL contains required parameters
        parsed_url = urlparse(location)
        assert "github.com" in parsed_url.netloc
        assert "/login/oauth/authorize" in parsed_url.path
        
        query_params = parse_qs(parsed_url.query)
        assert "client_id" in query_params
        assert "redirect_uri" in query_params
        assert "scope" in query_params
    
    @patch('app.services.oauth.GoogleOAuthService.exchange_code_for_token')
    @patch('app.services.oauth.GoogleOAuthService.get_user_info')
    async def test_google_oauth_callback_new_user(self, mock_get_user_info, mock_exchange_token, client, clean_database):
        """Test Google OAuth callback with new user."""
        # Mock OAuth responses
        mock_exchange_token.return_value = {
            "access_token": "mock_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        mock_get_user_info.return_value = {
            "id": "google_123456",
            "email": "newuser@gmail.com",
            "name": "New User",
            "picture": "https://example.com/avatar.jpg",
            "verified_email": True
        }
        
        # Test callback
        response = client.get("/api/v1/auth/oauth/google/callback?code=mock_auth_code&state=mock_state")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response contains tokens and user info
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data
        assert data["user"]["email"] == "newuser@gmail.com"
        assert data["user"]["role"] == "jobseeker"  # Default role
        
        # Verify user was created in database
        user = await User.find_one(User.email == "newuser@gmail.com")
        assert user is not None
        assert user.is_verified is True
        assert user.oauth_provider == "google"
    
    @patch('app.services.oauth.GoogleOAuthService.exchange_code_for_token')
    @patch('app.services.oauth.GoogleOAuthService.get_user_info')
    async def test_google_oauth_callback_existing_user(self, mock_get_user_info, mock_exchange_token, client, test_users):
        """Test Google OAuth callback with existing user."""
        # Create existing user with OAuth account
        existing_user = await User(
            email="existing@gmail.com",
            role="employer",
            is_active=True,
            is_verified=True,
            oauth_provider="google",
            oauth_id="google_123456"
        ).insert()
        
        # Mock OAuth responses
        mock_exchange_token.return_value = {
            "access_token": "mock_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        mock_get_user_info.return_value = {
            "id": "google_123456",
            "email": "existing@gmail.com",
            "name": "Existing User",
            "picture": "https://example.com/avatar.jpg",
            "verified_email": True
        }
        
        # Test callback
        response = client.get("/api/v1/auth/oauth/google/callback?code=mock_auth_code&state=mock_state")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response contains tokens and existing user info
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data
        assert data["user"]["email"] == "existing@gmail.com"
        assert data["user"]["role"] == "employer"  # Existing role preserved
    
    @patch('app.services.oauth.LinkedInOAuthService.exchange_code_for_token')
    @patch('app.services.oauth.LinkedInOAuthService.get_user_info')
    async def test_linkedin_oauth_callback(self, mock_get_user_info, mock_exchange_token, client, clean_database):
        """Test LinkedIn OAuth callback."""
        # Mock OAuth responses
        mock_exchange_token.return_value = {
            "access_token": "mock_linkedin_token",
            "token_type": "Bearer",
            "expires_in": 5184000
        }
        
        mock_get_user_info.return_value = {
            "id": "linkedin_789",
            "emailAddress": "professional@linkedin.com",
            "firstName": "Professional",
            "lastName": "User",
            "pictureUrl": "https://example.com/linkedin-avatar.jpg"
        }
        
        # Test callback
        response = client.get("/api/v1/auth/oauth/linkedin/callback?code=mock_auth_code&state=mock_state")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "professional@linkedin.com"
        assert data["user"]["oauth_provider"] == "linkedin"
        
        # Verify user was created
        user = await User.find_one(User.email == "professional@linkedin.com")
        assert user is not None
        assert user.oauth_provider == "linkedin"
        assert user.oauth_id == "linkedin_789"
    
    @patch('app.services.oauth.GitHubOAuthService.exchange_code_for_token')
    @patch('app.services.oauth.GitHubOAuthService.get_user_info')
    async def test_github_oauth_callback(self, mock_get_user_info, mock_exchange_token, client, clean_database):
        """Test GitHub OAuth callback."""
        # Mock OAuth responses
        mock_exchange_token.return_value = {
            "access_token": "mock_github_token",
            "token_type": "bearer",
            "scope": "user:email"
        }
        
        mock_get_user_info.return_value = {
            "id": 12345,
            "login": "developer123",
            "email": "developer@github.com",
            "name": "Developer User",
            "avatar_url": "https://example.com/github-avatar.jpg"
        }
        
        # Test callback
        response = client.get("/api/v1/auth/oauth/github/callback?code=mock_auth_code&state=mock_state")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "developer@github.com"
        assert data["user"]["oauth_provider"] == "github"
        
        # Verify user was created
        user = await User.find_one(User.email == "developer@github.com")
        assert user is not None
        assert user.oauth_provider == "github"
        assert user.oauth_id == "12345"
    
    def test_oauth_callback_missing_code(self, client):
        """Test OAuth callback without authorization code."""
        response = client.get("/api/v1/auth/oauth/google/callback")
        
        assert response.status_code == 400
        assert "Authorization code required" in response.json()["error"]["message"]
    
    def test_oauth_callback_invalid_state(self, client):
        """Test OAuth callback with invalid state parameter."""
        response = client.get("/api/v1/auth/oauth/google/callback?code=mock_code&state=invalid_state")
        
        assert response.status_code == 400
        assert "Invalid state parameter" in response.json()["error"]["message"]
    
    @patch('app.services.oauth.GoogleOAuthService.exchange_code_for_token')
    def test_oauth_token_exchange_failure(self, mock_exchange_token, client):
        """Test OAuth callback when token exchange fails."""
        # Mock token exchange failure
        mock_exchange_token.side_effect = Exception("Token exchange failed")
        
        response = client.get("/api/v1/auth/oauth/google/callback?code=invalid_code&state=mock_state")
        
        assert response.status_code == 400
        assert "OAuth authentication failed" in response.json()["error"]["message"]
    
    async def test_oauth_account_linking(self, client, test_users):
        """Test linking OAuth account to existing user."""
        # Get auth headers for existing user
        login_response = client.post(
            "/api/v1/auth/public/login",
            json={"email": "jobseeker@test.com", "password": "JobSeeker123!"}
        )
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Mock OAuth user info
        with patch('app.services.oauth.GoogleOAuthService.get_user_info') as mock_get_user_info:
            mock_get_user_info.return_value = {
                "id": "google_link_123",
                "email": "jobseeker@test.com",
                "name": "Job Seeker",
                "picture": "https://example.com/avatar.jpg",
                "verified_email": True
            }
            
            # Link OAuth account
            response = client.post(
                "/api/v1/auth/oauth/link/google",
                headers=headers,
                json={"access_token": "mock_google_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "OAuth account linked successfully"
            
            # Verify user was updated
            user = await User.find_one(User.email == "jobseeker@test.com")
            assert user.oauth_provider == "google"
            assert user.oauth_id == "google_link_123"
    
    async def test_oauth_account_unlinking(self, client, test_users):
        """Test unlinking OAuth account from user."""
        # Create user with OAuth account
        oauth_user = await User(
            email="oauth@test.com",
            role="jobseeker",
            is_active=True,
            is_verified=True,
            oauth_provider="google",
            oauth_id="google_unlink_123",
            password_hash=None  # OAuth-only user
        ).insert()
        
        # Login with OAuth user
        token = create_access_token(subject="oauth@test.com")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to unlink OAuth account (should fail if no password set)
        response = client.delete("/api/v1/auth/oauth/unlink", headers=headers)
        
        assert response.status_code == 400
        assert "Cannot unlink OAuth account" in response.json()["error"]["message"]
    
    def test_oauth_role_assignment(self, client, clean_database):
        """Test role assignment during OAuth registration."""
        with patch('app.services.oauth.GoogleOAuthService.exchange_code_for_token') as mock_exchange_token, \
             patch('app.services.oauth.GoogleOAuthService.get_user_info') as mock_get_user_info:
            
            mock_exchange_token.return_value = {
                "access_token": "mock_access_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
            
            mock_get_user_info.return_value = {
                "id": "google_role_test",
                "email": "roletest@gmail.com",
                "name": "Role Test User",
                "picture": "https://example.com/avatar.jpg",
                "verified_email": True
            }
            
            # Test with role parameter
            response = client.get("/api/v1/auth/oauth/google/callback?code=mock_code&state=mock_state&role=employer")
            
            assert response.status_code == 200
            data = response.json()
            assert data["user"]["role"] == "employer"
    
    async def test_oauth_email_verification(self, client, clean_database):
        """Test that OAuth users are automatically verified."""
        with patch('app.services.oauth.GoogleOAuthService.exchange_code_for_token') as mock_exchange_token, \
             patch('app.services.oauth.GoogleOAuthService.get_user_info') as mock_get_user_info:
            
            mock_exchange_token.return_value = {
                "access_token": "mock_access_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
            
            mock_get_user_info.return_value = {
                "id": "google_verified_test",
                "email": "verified@gmail.com",
                "name": "Verified User",
                "picture": "https://example.com/avatar.jpg",
                "verified_email": True
            }
            
            # Complete OAuth flow
            response = client.get("/api/v1/auth/oauth/google/callback?code=mock_code&state=mock_state")
            
            assert response.status_code == 200
            
            # Verify user is automatically verified
            user = await User.find_one(User.email == "verified@gmail.com")
            assert user.is_verified is True
            assert user.email_verified_at is not None


class TestOAuthSecurity:
    """Test OAuth security features."""
    
    def test_oauth_state_validation(self, client):
        """Test OAuth state parameter validation."""
        # Test missing state
        response = client.get("/api/v1/auth/oauth/google/callback?code=mock_code")
        assert response.status_code == 400
        
        # Test invalid state format
        response = client.get("/api/v1/auth/oauth/google/callback?code=mock_code&state=invalid")
        assert response.status_code == 400
    
    def test_oauth_csrf_protection(self, client):
        """Test CSRF protection in OAuth flow."""
        # Initiate OAuth flow to get valid state
        response = client.get("/api/v1/auth/oauth/google")
        location = response.headers["location"]
        parsed_url = urlparse(location)
        query_params = parse_qs(parsed_url.query)
        valid_state = query_params["state"][0]
        
        # Test with different state (CSRF attack simulation)
        response = client.get(f"/api/v1/auth/oauth/google/callback?code=mock_code&state=different_state")
        assert response.status_code == 400
        assert "Invalid state parameter" in response.json()["error"]["message"]
    
    def test_oauth_scope_validation(self, client):
        """Test OAuth scope validation."""
        with patch('app.services.oauth.GoogleOAuthService.exchange_code_for_token') as mock_exchange_token:
            # Mock insufficient scope response
            mock_exchange_token.return_value = {
                "access_token": "mock_token",
                "scope": "openid"  # Missing email scope
            }
            
            response = client.get("/api/v1/auth/oauth/google/callback?code=mock_code&state=mock_state")
            assert response.status_code == 400
            assert "Insufficient OAuth scope" in response.json()["error"]["message"]
    
    async def test_oauth_email_domain_restrictions(self, client, clean_database):
        """Test OAuth email domain restrictions if configured."""
        with patch('app.core.config.settings.ALLOWED_OAUTH_DOMAINS', ['company.com']), \
             patch('app.services.oauth.GoogleOAuthService.exchange_code_for_token') as mock_exchange_token, \
             patch('app.services.oauth.GoogleOAuthService.get_user_info') as mock_get_user_info:
            
            mock_exchange_token.return_value = {
                "access_token": "mock_access_token",
                "token_type": "Bearer",
                "expires_in": 3600
            }
            
            mock_get_user_info.return_value = {
                "id": "google_domain_test",
                "email": "user@unauthorized-domain.com",
                "name": "Unauthorized User",
                "verified_email": True
            }
            
            response = client.get("/api/v1/auth/oauth/google/callback?code=mock_code&state=mock_state")
            
            assert response.status_code == 403
            assert "Email domain not allowed" in response.json()["error"]["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])