"""Security Features Tests for RemoteHive RBAC System.

This module tests security features including rate limiting, audit logging,
input validation, and other security mechanisms.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.mongodb_models import User
from backend.models.mongodb_models import AuditLog, Session
from backend.core.security import create_access_token, verify_token
from backend.core.rate_limiter import RateLimiter


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_login_rate_limiting(self, client):
        """Test rate limiting on login endpoint."""
        login_data = {"email": "test@example.com", "password": "wrongpassword"}
        
        # Make multiple failed login attempts
        responses = []
        for i in range(6):  # Exceed rate limit of 5 attempts
            response = client.post("/api/v1/auth/public/login", json=login_data)
            responses.append(response)
        
        # First 5 attempts should return 401 (unauthorized)
        for response in responses[:5]:
            assert response.status_code == 401
        
        # 6th attempt should be rate limited
        assert responses[5].status_code == 429
        assert "Too many requests" in responses[5].json()["detail"]
    
    def test_registration_rate_limiting(self, client):
        """Test rate limiting on registration endpoint."""
        # Make multiple registration attempts with same IP
        responses = []
        for i in range(4):  # Exceed rate limit of 3 registrations per hour
            registration_data = {
                "email": f"user{i}@example.com",
                "password": "TestPassword123!",
                "role": "jobseeker"
            }
            response = client.post("/api/v1/auth/public/register", json=registration_data)
            responses.append(response)
        
        # First 3 attempts should succeed or fail normally
        for response in responses[:3]:
            assert response.status_code in [201, 400]  # Success or validation error
        
        # 4th attempt should be rate limited
        assert responses[3].status_code == 429
        assert "Too many requests" in responses[3].json()["detail"]
    
    def test_password_reset_rate_limiting(self, client):
        """Test rate limiting on password reset endpoint."""
        reset_data = {"email": "test@example.com"}
        
        # Make multiple password reset requests
        responses = []
        for i in range(4):  # Exceed rate limit of 3 requests per hour
            response = client.post("/api/v1/auth/forgot-password", json=reset_data)
            responses.append(response)
        
        # First 3 attempts should succeed
        for response in responses[:3]:
            assert response.status_code == 200
        
        # 4th attempt should be rate limited
        assert responses[3].status_code == 429
        assert "Too many requests" in responses[3].json()["detail"]
    
    def test_api_endpoint_rate_limiting(self, client, admin_headers):
        """Test rate limiting on API endpoints."""
        # Make multiple requests to admin endpoint
        responses = []
        for i in range(101):  # Exceed rate limit of 100 requests per minute
            response = client.get("/api/admin/users", headers=admin_headers)
            responses.append(response)
        
        # First 100 requests should succeed
        for response in responses[:100]:
            assert response.status_code in [200, 401, 403]  # Success or auth error
        
        # 101st request should be rate limited
        assert responses[100].status_code == 429
        assert "Too many requests" in responses[100].json()["detail"]
    
    def test_rate_limit_headers(self, client):
        """Test rate limit headers in responses."""
        response = client.post("/api/v1/auth/public/login", json={"email": "test@example.com", "password": "wrong"})
        
        # Check rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
        
        # Verify header values
        assert int(response.headers["X-RateLimit-Limit"]) > 0
        assert int(response.headers["X-RateLimit-Remaining"]) >= 0
    
    def test_rate_limit_bypass_for_whitelisted_ips(self, client):
        """Test rate limit bypass for whitelisted IP addresses."""
        with patch('app.core.rate_limiter.get_client_ip') as mock_get_ip:
            # Mock whitelisted IP
            mock_get_ip.return_value = "127.0.0.1"  # Localhost should be whitelisted
            
            login_data = {"email": "test@example.com", "password": "wrongpassword"}
            
            # Make many requests (should not be rate limited)
            responses = []
            for i in range(10):
                response = client.post("/api/v1/auth/public/login", json=login_data)
                responses.append(response)
            
            # All requests should return 401 (not rate limited)
            for response in responses:
                assert response.status_code == 401
                assert "Too many requests" not in response.json().get("detail", "")


class TestAuditLogging:
    """Test audit logging functionality."""
    
    async def test_login_audit_logging(self, client, test_users, clean_database):
        """Test audit logging for login attempts."""
        # Successful login
        response = client.post(
            "/api/v1/auth/public/login",
            json={"email": "jobseeker@test.com", "password": "JobSeeker123!"}
        )
        assert response.status_code == 200
        
        # Check audit log
        audit_logs = await AuditLog.find(AuditLog.action == "login_success").to_list()
        assert len(audit_logs) >= 1
        
        latest_log = audit_logs[-1]
        assert latest_log.user_email == "jobseeker@test.com"
        assert latest_log.action == "login_success"
        assert latest_log.ip_address is not None
        assert latest_log.user_agent is not None
        
        # Failed login
        response = client.post(
            "/api/v1/auth/public/login",
            json={"email": "jobseeker@test.com", "password": "wrongpassword"}
        )
        assert response.status_code == 401
        
        # Check failed login audit log
        failed_logs = await AuditLog.find(AuditLog.action == "login_failed").to_list()
        assert len(failed_logs) >= 1
        
        latest_failed_log = failed_logs[-1]
        assert latest_failed_log.user_email == "jobseeker@test.com"
        assert latest_failed_log.action == "login_failed"
        assert "Invalid credentials" in latest_failed_log.details
    
    async def test_registration_audit_logging(self, client, clean_database):
        """Test audit logging for user registration."""
        registration_data = {
            "email": "newuser@example.com",
            "password": "NewUser123!",
            "role": "jobseeker"
        }
        
        response = client.post("/api/v1/auth/public/register", json=registration_data)
        assert response.status_code == 201
        
        # Check audit log
        audit_logs = await AuditLog.find(AuditLog.action == "user_registered").to_list()
        assert len(audit_logs) >= 1
        
        latest_log = audit_logs[-1]
        assert latest_log.user_email == "newuser@example.com"
        assert latest_log.action == "user_registered"
        assert latest_log.details["role"] == "jobseeker"
    
    async def test_password_change_audit_logging(self, client, test_users):
        """Test audit logging for password changes."""
        # Login first
        login_response = client.post(
            "/api/v1/auth/public/login",
            json={"email": "jobseeker@test.com", "password": "JobSeeker123!"}
        )
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
        
        # Change password
        response = client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": "JobSeeker123!",
                "new_password": "NewPassword123!"
            }
        )
        assert response.status_code == 200
        
        # Check audit log
        audit_logs = await AuditLog.find(AuditLog.action == "password_changed").to_list()
        assert len(audit_logs) >= 1
        
        latest_log = audit_logs[-1]
        assert latest_log.user_email == "jobseeker@test.com"
        assert latest_log.action == "password_changed"
    
    async def test_admin_action_audit_logging(self, client, admin_headers, test_users):
        """Test audit logging for admin actions."""
        # Admin updates user role
        response = client.put(
            "/api/admin/users/jobseeker@test.com/role",
            headers=admin_headers,
            json={"role": "employer"}
        )
        assert response.status_code == 200
        
        # Check audit log
        audit_logs = await AuditLog.find(AuditLog.action == "user_role_updated").to_list()
        assert len(audit_logs) >= 1
        
        latest_log = audit_logs[-1]
        assert latest_log.action == "user_role_updated"
        assert latest_log.details["target_user"] == "jobseeker@test.com"
        assert latest_log.details["new_role"] == "employer"
    
    async def test_suspicious_activity_logging(self, client, test_users):
        """Test logging of suspicious activities."""
        # Multiple failed login attempts (suspicious)
        for i in range(5):
            client.post(
                "/api/v1/auth/public/login",
                json={"email": "jobseeker@test.com", "password": "wrongpassword"}
            )
        
        # Check for suspicious activity log
        audit_logs = await AuditLog.find(AuditLog.action == "suspicious_activity").to_list()
        assert len(audit_logs) >= 1
        
        latest_log = audit_logs[-1]
        assert latest_log.action == "suspicious_activity"
        assert "Multiple failed login attempts" in latest_log.details["description"]
    
    async def test_audit_log_retention(self, clean_database):
        """Test audit log retention policy."""
        # Create old audit log (older than retention period)
        old_log = AuditLog(
            user_email="test@example.com",
            action="test_action",
            timestamp=datetime.utcnow() - timedelta(days=91),  # 91 days old
            ip_address="127.0.0.1",
            user_agent="Test Agent",
            details={"test": "data"}
        )
        await old_log.insert()
        
        # Create recent audit log
        recent_log = AuditLog(
            user_email="test@example.com",
            action="test_action",
            timestamp=datetime.utcnow(),
            ip_address="127.0.0.1",
            user_agent="Test Agent",
            details={"test": "data"}
        )
        await recent_log.insert()
        
        # Run cleanup (this would normally be a scheduled task)
        from backend.tasks.cleanup import cleanup_old_audit_logs
        await cleanup_old_audit_logs()
        
        # Check that old log is deleted but recent log remains
        remaining_logs = await AuditLog.find(AuditLog.user_email == "test@example.com").to_list()
        assert len(remaining_logs) == 1
        assert remaining_logs[0].id == recent_log.id


class TestInputValidation:
    """Test input validation and sanitization."""
    
    def test_sql_injection_prevention(self, client):
        """Test prevention of SQL injection attacks."""
        # Attempt SQL injection in login
        malicious_input = "admin@test.com'; DROP TABLE users; --"
        response = client.post(
            "/api/v1/auth/public/login",
            json={"email": malicious_input, "password": "password"}
        )
        
        # Should return validation error, not execute SQL
        assert response.status_code == 422  # Validation error
        assert "Invalid email format" in str(response.json())
    
    def test_xss_prevention(self, client, admin_headers):
        """Test prevention of XSS attacks."""
        # Attempt XSS in user creation
        malicious_script = "<script>alert('XSS')</script>"
        response = client.post(
            "/api/admin/users",
            headers=admin_headers,
            json={
                "email": "test@example.com",
                "password": "Password123!",
                "role": "jobseeker",
                "full_name": malicious_script
            }
        )
        
        if response.status_code == 201:
            # If user created, check that script is sanitized
            user_data = response.json()
            assert "<script>" not in user_data.get("full_name", "")
            assert "&lt;script&gt;" in user_data.get("full_name", "") or malicious_script not in user_data.get("full_name", "")
    
    def test_email_validation(self, client):
        """Test email format validation."""
        invalid_emails = [
            "invalid-email",
            "@example.com",
            "user@",
            "user..name@example.com",
            "user@.com",
            "user@example."
        ]
        
        for invalid_email in invalid_emails:
            response = client.post(
                "/api/v1/auth/public/register",
                json={
                    "email": invalid_email,
                    "password": "Password123!",
                    "role": "jobseeker"
                }
            )
            assert response.status_code == 422
            assert "email" in str(response.json()).lower()
    
    def test_password_strength_validation(self, client):
        """Test password strength requirements."""
        weak_passwords = [
            "123456",
            "password",
            "abc123",
            "Password",  # No number or special char
            "password123",  # No uppercase or special char
            "PASSWORD123!",  # No lowercase
            "Pass1!",  # Too short
        ]
        
        for weak_password in weak_passwords:
            response = client.post(
                "/api/auth/register",
                json={
                    "email": "test@example.com",
                    "password": weak_password,
                    "role": "jobseeker"
                }
            )
            assert response.status_code == 422
            assert "password" in str(response.json()).lower()
    
    def test_role_validation(self, client):
        """Test role validation."""
        invalid_roles = ["invalid_role", "hacker", "root", ""]
        
        for invalid_role in invalid_roles:
            response = client.post(
                "/api/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "Password123!",
                    "role": invalid_role
                }
            )
            assert response.status_code == 422
            assert "role" in str(response.json()).lower()
    
    def test_request_size_limits(self, client):
        """Test request size limitations."""
        # Create oversized payload
        large_data = "x" * (1024 * 1024 * 2)  # 2MB string
        
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "Password123!",
                "role": "jobseeker",
                "bio": large_data
            }
        )
        
        # Should reject oversized request
        assert response.status_code in [413, 422]  # Payload too large or validation error


class TestSessionSecurity:
    """Test session security features."""
    
    async def test_session_creation_and_tracking(self, client, test_users, clean_database):
        """Test session creation and tracking."""
        # Login to create session
        response = await client.post(
            "/api/v1/auth/public/login",
            json={"email": "jobseeker@test.com", "password": "JobSeeker123!"}
        )
        assert response.status_code == 200
        
        token = response.json()["access_token"]
        
        # Check session was created
        # First get the user to find their ID
        user = await User.find_one(User.email == "jobseeker@test.com")
        sessions = await Session.find(Session.user_id == user.id).to_list()
        assert len(sessions) >= 1
        
        latest_session = sessions[-1]
        assert latest_session.is_active is True
        assert latest_session.ip_address is not None
        assert latest_session.user_agent is not None
    
    async def test_concurrent_session_limits(self, client, test_users):
        """Test concurrent session limits."""
        login_data = {"email": "jobseeker@test.com", "password": "JobSeeker123!"}
        
        # Create multiple sessions
        tokens = []
        for i in range(6):  # Exceed limit of 5 concurrent sessions
            response = await client.post("/api/v1/auth/public/login", json=login_data)
            if response.status_code == 200:
                tokens.append(response.json()["access_token"])
        
        # Check that old sessions are invalidated
        # First get the user to find their ID
        user = await User.find_one(User.email == "jobseeker@test.com")
        active_sessions = await Session.find(
            Session.user_id == user.id,
            Session.is_active == True
        ).to_list()
        
        assert len(active_sessions) <= 5  # Should not exceed limit
    
    async def test_session_expiration(self, client, test_users):
        """Test session expiration."""
        # Login
        response = await client.post(
            "/api/v1/auth/public/login",
            json={"email": "jobseeker@test.com", "password": "JobSeeker123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Mock expired token
        with patch('app.core.security.verify_token') as mock_verify:
            mock_verify.side_effect = Exception("Token expired")
            
            # Try to access protected endpoint
            response = await client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == 401
        assert "invalid" in response.json()["error"]["message"].lower()
    
    async def test_session_invalidation_on_logout(self, client, test_users):
        """Test session invalidation on logout."""
        # Login
        response = await client.post(
            "/api/v1/auth/public/login",
            json={"email": "jobseeker@test.com", "password": "JobSeeker123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Logout
        response = await client.post("/api/v1/auth/logout", headers=headers, json={})
        assert response.status_code == 200
        
        # Check session is invalidated
        # First get the user to find their ID
        user = await User.find_one(User.email == "jobseeker@test.com")
        sessions = await Session.find(
            Session.user_id == user.id,
            Session.is_active == True
        ).to_list()
        
        # Should have no active sessions or token should be blacklisted
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
    
    async def test_session_hijacking_prevention(self, client, test_users):
        """Test session hijacking prevention."""
        # Login from one IP
        with patch('app.core.security.get_client_ip') as mock_ip:
            mock_ip.return_value = "192.168.1.1"
            
            response = await client.post(
                "/api/v1/auth/public/login",
                json={"email": "jobseeker@test.com", "password": "JobSeeker123!"}
            )
            token = response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            
            # Try to use token from different IP
            mock_ip.return_value = "10.0.0.1"
            
            response = await client.get("/api/v1/auth/me", headers=headers)
            
            # Should detect IP change and require re-authentication
            if response.status_code == 401:
                assert "suspicious" in response.json()["error"]["message"].lower() or "ip" in response.json()["error"]["message"].lower()


class TestTokenSecurity:
    """Test JWT token security features."""
    
    async def test_token_blacklisting(self, client, test_users):
        """Test token blacklisting functionality."""
        # Login
        response = await client.post(
            "/api/v1/auth/public/login",
            json={"email": "jobseeker@test.com", "password": "JobSeeker123!"}
        )
        assert response.status_code == 200, f"Login failed: {response.json()}"
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Use token (should work)
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        
        # Logout (blacklist token)
        response = await client.post("/api/v1/auth/logout", headers=headers, json={})
        if response.status_code != 200:
            import logging
            logging.error(f"Logout failed with status {response.status_code}")
            logging.error(f"Response: {response.json()}")
            # Also try to get the response text
            logging.error(f"Response text: {response.text}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.json() if response.status_code != 500 else response.text}"
        
        # Try to use blacklisted token
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        assert "blacklisted" in response.json()["error"]["message"].lower() or "invalid" in response.json()["error"]["message"].lower()
    
    async def test_token_refresh_security(self, client, test_users):
        """Test refresh token security."""
        # Login
        response = await client.post(
            "/api/v1/auth/public/login",
            json={"email": "jobseeker@test.com", "password": "JobSeeker123!"}
        )
        assert response.status_code == 200, f"Login failed: {response.json()}"
        refresh_token = response.json()["refresh_token"]
        
        # Use refresh token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 200
        
        new_access_token = response.json()["access_token"]
        new_refresh_token = response.json()["refresh_token"]
        
        # Old refresh token should be invalidated
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["error"]["message"].lower()
    
    async def test_token_tampering_detection(self, client):
        """Test detection of tampered tokens."""
        # Create valid token
        token = create_access_token(subject="test@example.com")
        
        # Tamper with token
        tampered_token = token[:-10] + "tampered123"
        headers = {"Authorization": f"Bearer {tampered_token}"}
        
        # Try to use tampered token
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        assert "invalid" in response.json()["error"]["message"].lower()
    
    async def test_token_algorithm_confusion(self, client):
        """Test prevention of algorithm confusion attacks."""
        import jwt
        
        # Try to create token with 'none' algorithm
        malicious_token = jwt.encode(
            {"sub": "admin@test.com", "role": "super_admin"},
            "",
            algorithm="none"
        )
        
        headers = {"Authorization": f"Bearer {malicious_token}"}
        
        # Should reject token with 'none' algorithm
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        assert "invalid" in response.json()["error"]["message"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])