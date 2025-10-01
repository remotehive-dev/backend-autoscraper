"""Comprehensive RBAC Integration Tests for RemoteHive.

This module contains integration tests for the Role-Based Access Control (RBAC) system,
including authentication, authorization, user management, and security features.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

from backend.main import app
from backend.database.database import DatabaseManager
from backend.models.mongodb_models import User, ContactSubmission, ContactInformation, SeoSettings, Review, Ad
from backend.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash
from backend.core.rbac import RBACManager
from beanie import init_beanie
import motor.motor_asyncio


class TestRBACIntegration:
    """Integration tests for RBAC system."""
    
    @pytest.fixture(scope="class")
    async def setup_test_db(self):
        """Set up test database with clean state."""
        # Initialize test database
        client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
        database = client.test_remotehive_rbac
        
        # Initialize Beanie with test database
        await init_beanie(
            database=database,
            document_models=[
                User, ContactSubmission, ContactInformation, 
                SeoSettings, Review, Ad
            ]
        )
        
        # Clean up any existing test data
        await User.delete_all()
        
        yield database
        
        # Cleanup after tests
        await User.delete_all()
        client.close()
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    async def test_users(self, setup_test_db):
        """Create test users with different roles."""
        users = {
            'super_admin': await User(
                email="superadmin@test.com",
                password_hash=get_password_hash("SuperAdmin123!"),
                role="super_admin",
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow()
            ).insert(),
            
            'admin': await User(
                email="admin@test.com",
                password_hash=get_password_hash("Admin123!"),
                role="admin",
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow()
            ).insert(),
            
            'employer': await User(
                email="employer@test.com",
                password_hash=get_password_hash("Employer123!"),
                role="employer",
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow()
            ).insert(),
            
            'jobseeker': await User(
                email="jobseeker@test.com",
                password_hash=get_password_hash("JobSeeker123!"),
                role="jobseeker",
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow()
            ).insert(),
            
            'inactive': await User(
                email="inactive@test.com",
                password_hash=get_password_hash("Inactive123!"),
                role="jobseeker",
                is_active=False,
                is_verified=True,
                created_at=datetime.utcnow()
            ).insert()
        }
        
        return users


class TestAuthentication:
    """Test authentication endpoints and functionality."""
    
    def test_login_success(self, client, test_users):
        """Test successful login with valid credentials."""
        response = client.post(
            "/api/v1/auth/public/login",
            json={
                "email": "admin@test.com",
                "password": "Admin123!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "admin@test.com"
        assert data["user"]["role"] == "admin"
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post(
            "/api/v1/auth/public/login",
            json={
                "email": "admin@test.com",
                "password": "WrongPassword"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["error"]["message"]
    
    def test_login_inactive_user(self, client, test_users):
        """Test login with inactive user account."""
        response = client.post(
            "/api/v1/auth/public/login",
            json={
                "email": "inactive@test.com",
                "password": "Inactive123!"
            }
        )
        
        assert response.status_code == 401
        assert "Account is inactive" in response.json()["error"]["message"]
    
    def test_register_success(self, client):
        """Test successful user registration."""
        response = client.post(
            "/api/v1/auth/public/register",
            json={
                "email": "newuser@test.com",
                "password": "NewUser123!",
                "role": "jobseeker"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@test.com"
        assert data["role"] == "jobseeker"
        assert data["is_active"] is True
        assert "id" in data
    
    def test_register_duplicate_email(self, client, test_users):
        """Test registration with existing email."""
        response = client.post(
            "/api/v1/auth/public/register",
            json={
                "email": "admin@test.com",
                "password": "NewPassword123!",
                "role": "jobseeker"
            }
        )
        
        assert response.status_code == 400
        assert "Email already registered" in response.json()["error"]["message"]
    
    def test_refresh_token_success(self, client, test_users):
        """Test successful token refresh."""
        # First login to get tokens
        login_response = client.post(
            "/api/v1/auth/public/login",
            json={
                "email": "admin@test.com",
                "password": "Admin123!"
            }
        )
        
        refresh_token = login_response.json()["refresh_token"]
        
        # Use refresh token to get new access token
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_refresh_token_invalid(self, client):
        """Test refresh with invalid token."""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token"}
        )
        
        assert response.status_code == 401
        assert "Invalid refresh token" in response.json()["error"]["message"]


class TestAuthorization:
    """Test role-based authorization and permissions."""
    
    def get_auth_headers(self, client, email, password):
        """Helper to get authorization headers."""
        response = client.post(
            "/api/v1/auth/public/login",
            json={"email": email, "password": password}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_super_admin_access(self, client, test_users):
        """Test super admin can access all endpoints."""
        headers = self.get_auth_headers(client, "superadmin@test.com", "SuperAdmin123!")
        
        # Test admin endpoints
        response = client.get("/api/admin/users", headers=headers)
        assert response.status_code == 200
        
        # Test system management
        response = client.get("/api/admin/system/stats", headers=headers)
        assert response.status_code == 200
        
        # Test user management
        response = client.get("/api/admin/users/1", headers=headers)
        assert response.status_code in [200, 404]  # 404 if user doesn't exist
    
    def test_admin_access(self, client, test_users):
        """Test admin role permissions."""
        headers = self.get_auth_headers(client, "admin@test.com", "Admin123!")
        
        # Admin can access user management
        response = client.get("/api/admin/users", headers=headers)
        assert response.status_code == 200
        
        # Admin cannot access super admin endpoints
        response = client.delete("/api/admin/system/reset", headers=headers)
        assert response.status_code == 403
    
    def test_employer_access(self, client, test_users):
        """Test employer role permissions."""
        headers = self.get_auth_headers(client, "employer@test.com", "Employer123!")
        
        # Employer can access job management
        response = client.get("/api/jobs", headers=headers)
        assert response.status_code == 200
        
        # Employer cannot access admin endpoints
        response = client.get("/api/admin/users", headers=headers)
        assert response.status_code == 403
    
    def test_jobseeker_access(self, client, test_users):
        """Test jobseeker role permissions."""
        headers = self.get_auth_headers(client, "jobseeker@test.com", "JobSeeker123!")
        
        # Jobseeker can access job listings
        response = client.get("/api/jobs", headers=headers)
        assert response.status_code == 200
        
        # Jobseeker cannot access admin endpoints
        response = client.get("/api/admin/users", headers=headers)
        assert response.status_code == 403
        
        # Jobseeker cannot create jobs
        response = client.post("/api/jobs", headers=headers, json={})
        assert response.status_code == 403
    
    def test_unauthenticated_access(self, client):
        """Test access without authentication."""
        # Public endpoints should work
        response = client.get("/api/health")
        assert response.status_code == 200
        
        # Protected endpoints should require auth
        response = client.get("/api/admin/users")
        assert response.status_code == 401
        
        response = client.get("/api/jobs")
        assert response.status_code == 401


class TestUserManagement:
    """Test user management functionality."""
    
    def get_admin_headers(self, client):
        """Helper to get admin authorization headers."""
        response = client.post(
            "/api/v1/auth/public/login",
            json={"email": "admin@test.com", "password": "Admin123!"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_list_users(self, client, test_users):
        """Test listing users with pagination."""
        headers = self.get_admin_headers(client)
        
        response = client.get("/api/admin/users", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert len(data["users"]) >= 4  # At least our test users
    
    def test_get_user_by_id(self, client, test_users):
        """Test getting specific user by ID."""
        headers = self.get_admin_headers(client)
        user_id = str(test_users['admin'].id)
        
        response = client.get(f"/api/admin/users/{user_id}", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"
    
    def test_update_user_role(self, client, test_users):
        """Test updating user role."""
        headers = self.get_admin_headers(client)
        user_id = str(test_users['jobseeker'].id)
        
        response = client.put(
            f"/api/admin/users/{user_id}/role",
            headers=headers,
            json={"role": "employer"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "employer"
    
    def test_deactivate_user(self, client, test_users):
        """Test deactivating user account."""
        headers = self.get_admin_headers(client)
        user_id = str(test_users['jobseeker'].id)
        
        response = client.put(
            f"/api/admin/users/{user_id}/deactivate",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
    
    def test_activate_user(self, client, test_users):
        """Test activating user account."""
        headers = self.get_admin_headers(client)
        user_id = str(test_users['inactive'].id)
        
        response = client.put(
            f"/api/admin/users/{user_id}/activate",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True


class TestSecurityFeatures:
    """Test security features and middleware."""
    
    def test_password_validation(self, client):
        """Test password strength validation."""
        # Weak password should be rejected
        response = client.post(
            "/api/v1/auth/public/register",
            json={
                "email": "weakpass@test.com",
                "password": "123",
                "role": "jobseeker"
            }
        )
        
        assert response.status_code == 422
        assert "password" in response.json()["error"]["details"][0]["field"]
    
    def test_email_validation(self, client):
        """Test email format validation."""
        response = client.post(
            "/api/v1/auth/public/register",
            json={
                "email": "invalid-email",
                "password": "ValidPass123!",
                "role": "jobseeker"
            }
        )
        
        assert response.status_code == 422
        assert "email" in response.json()["error"]["details"][0]["field"]
    
    def test_token_expiration(self, client, test_users):
        """Test token expiration handling."""
        # Create expired token
        expired_token = create_access_token(
            data={"sub": "admin@test.com"},
            expires_delta=timedelta(seconds=-1)
        )
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/admin/users", headers=headers)
        
        assert response.status_code == 401
        assert "Token expired" in response.json()["error"]["message"]
    
    def test_invalid_token_format(self, client):
        """Test handling of malformed tokens."""
        headers = {"Authorization": "Bearer invalid_token_format"}
        response = client.get("/api/admin/users", headers=headers)
        
        assert response.status_code == 401
        assert "Invalid token" in response.json()["error"]["message"]
    
    @patch('app.middleware.security.time.time')
    def test_rate_limiting(self, mock_time, client):
        """Test rate limiting on authentication endpoints."""
        mock_time.return_value = 1000.0
        
        # Make multiple rapid requests
        for i in range(10):
            response = client.post(
                "/api/v1/auth/public/login",
                json={
                    "email": "admin@test.com",
                    "password": "WrongPassword"
                }
            )
        
        # Should be rate limited after too many attempts
        assert response.status_code == 429
        assert "Rate limit exceeded" in response.json()["error"]["message"]


class TestSystemAnalytics:
    """Test system analytics and monitoring endpoints."""
    
    def get_super_admin_headers(self, client):
        """Helper to get super admin authorization headers."""
        response = client.post(
            "/api/v1/auth/public/login",
            json={"email": "superadmin@test.com", "password": "SuperAdmin123!"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_system_stats(self, client, test_users):
        """Test system statistics endpoint."""
        headers = self.get_super_admin_headers(client)
        
        response = client.get("/api/admin/system/stats", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "total_users" in data
        assert "active_users" in data
        assert "users_by_role" in data
        assert "recent_registrations" in data
    
    def test_audit_logs(self, client, test_users):
        """Test audit log retrieval."""
        headers = self.get_super_admin_headers(client)
        
        response = client.get("/api/admin/audit/logs", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "logs" in data
        assert "total" in data
    
    def test_security_events(self, client, test_users):
        """Test security events monitoring."""
        headers = self.get_super_admin_headers(client)
        
        response = client.get("/api/admin/security/events", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "events" in data
        assert "summary" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])