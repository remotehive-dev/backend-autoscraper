"""Pytest configuration and shared fixtures for RBAC tests.

This module provides shared fixtures and configuration for all RBAC integration tests.
"""

import pytest
import asyncio
import os
from datetime import datetime
from typing import Dict, Any
from fastapi.testclient import TestClient
from httpx import AsyncClient
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

# Disable rate limiting for tests
os.environ["RATE_LIMIT_ENABLED"] = "false"

from backend.main import app
from backend.database.database import DatabaseManager
from backend.database.mongodb_models import (
    User, ContactSubmission, ContactInformation, 
    SeoSettings, Review, Ad, UserSession, PasswordResetToken, LoginAttempt
)
from backend.models.mongodb_models import Session
from backend.core.security import get_password_hash


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_database():
    """Create test database and initialize Beanie."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    database = client.test_remotehive
    
    # Initialize Beanie with test database
    await init_beanie(
        database=database,
        document_models=[
            User,
            ContactSubmission,
            ContactInformation,
            SeoSettings,
            Review,
            Ad,
            UserSession,
            PasswordResetToken,
            Session,
            LoginAttempt
        ]
    )
    
    yield database
    
    # Clean up test database
    await database.drop_collection("users")
    await database.drop_collection("contact_submissions")
    await database.drop_collection("contact_information")
    await database.drop_collection("seo_settings")
    await database.drop_collection("reviews")
    await database.drop_collection("ads")
    await database.drop_collection("user_sessions")
    await database.drop_collection("password_reset_tokens")
    await database.drop_collection("sessions")
    await database.drop_collection("login_attempts")
    client.close()


@pytest.fixture
async def client(test_database):
    """Create FastAPI async test client with initialized database."""
    from backend.database.database import DatabaseManager
    from unittest.mock import Mock, patch, AsyncMock
    from backend. import database.database as db_module
    from backend.main import app
    from backend.core.database import get_db
    
    # Create and initialize database manager
    db_manager = DatabaseManager()
    
    # Mock the mongodb_manager to return our test database
    mock_mongodb_manager = Mock()
    mock_mongodb_manager.get_database.return_value = test_database
    mock_mongodb_manager.get_client.return_value = Mock()
    
    db_manager.mongodb_manager = mock_mongodb_manager
    db_manager._initialized = True
    
    # Store the manager globally so get_database_manager() can find it
    db_module.db_manager = db_manager
    
    # Override the get_db dependency to return our test database
    async def override_get_db():
        return test_database
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Mock the init_database function to prevent startup database initialization
    with patch('app.database.init_database', new_callable=AsyncMock) as mock_init_db:
        mock_init_db.return_value = None
        
        # Mock the create_default_data function to prevent default user creation
        with patch('app.core.database.create_default_data', new_callable=AsyncMock) as mock_create_default:
            mock_create_default.return_value = None
            
            try:
                async with AsyncClient(app=app, base_url="http://test") as ac:
                    yield ac
            finally:
                # Clean up dependency override
                app.dependency_overrides.clear()


@pytest.fixture
async def async_client():
    """Create async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def clean_database(test_database):
    """Clean database before each test."""
    # Clean up all collections
    await User.delete_all()
    await ContactSubmission.delete_all()
    await ContactInformation.delete_all()
    await SeoSettings.delete_all()
    await Review.delete_all()
    await Ad.delete_all()
    await UserSession.delete_all()
    await PasswordResetToken.delete_all()
    await Session.delete_all()
    await LoginAttempt.delete_all()
    
    yield
    
    # Clean up after test
    await User.delete_all()
    await ContactSubmission.delete_all()
    await ContactInformation.delete_all()
    await SeoSettings.delete_all()
    await Review.delete_all()
    await Ad.delete_all()
    await UserSession.delete_all()
    await PasswordResetToken.delete_all()
    await Session.delete_all()
    await LoginAttempt.delete_all()


@pytest.fixture
async def test_users(clean_database) -> Dict[str, User]:
    """Create test users with different roles."""
    users = {}
    
    # Super Admin
    users['super_admin'] = await User(
        email="superadmin@test.com",
        password_hash=get_password_hash("SuperAdmin123!"),
        first_name="Super",
        last_name="Admin",
        role="super_admin",
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow()
    ).insert()
    
    # Admin
    users['admin'] = await User(
        email="admin@test.com",
        password_hash=get_password_hash("Admin123!"),
        first_name="Test",
        last_name="Admin",
        role="admin",
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow()
    ).insert()
    
    # Employer
    users['employer'] = await User(
        email="employer@test.com",
        password_hash=get_password_hash("Employer123!"),
        first_name="Test",
        last_name="Employer",
        role="employer",
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow()
    ).insert()
    
    # Job Seeker
    users['jobseeker'] = await User(
        email="jobseeker@test.com",
        password_hash=get_password_hash("JobSeeker123!"),
        first_name="Test",
        last_name="JobSeeker",
        role="job_seeker",
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow()
    ).insert()
    
    # Inactive User
    users['inactive'] = await User(
        email="inactive@test.com",
        password_hash=get_password_hash("Inactive123!"),
        first_name="Inactive",
        last_name="User",
        role="job_seeker",
        is_active=False,
        is_verified=True,
        created_at=datetime.utcnow()
    ).insert()
    
    return users


@pytest.fixture
def auth_headers():
    """Helper function to generate auth headers."""
    async def _get_auth_headers(client: AsyncClient, email: str, password: str) -> Dict[str, str]:
        """Get authorization headers for a user."""
        response = await client.post(
            "/api/v1/auth/public/login",
            json={"email": email, "password": password}
        )
        if response.status_code != 200:
            raise ValueError(f"Login failed: {response.json()}")
        
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    return _get_auth_headers


@pytest.fixture
async def super_admin_headers(client, test_users, auth_headers):
    """Get super admin authorization headers."""
    return await auth_headers(client, "superadmin@test.com", "SuperAdmin123!")


@pytest.fixture
async def admin_headers(client, test_users, auth_headers):
    """Get admin authorization headers."""
    return await auth_headers(client, "admin@test.com", "Admin123!")


@pytest.fixture
async def employer_headers(client, test_users, auth_headers):
    """Get employer authorization headers."""
    return await auth_headers(client, "employer@test.com", "Employer123!")


@pytest.fixture
async def jobseeker_headers(client, test_users, auth_headers):
    """Get jobseeker authorization headers."""
    return await auth_headers(client, "jobseeker@test.com", "JobSeeker123!")


# Test data fixtures
@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        "title": "Senior Python Developer",
        "description": "We are looking for a senior Python developer...",
        "company": "Tech Corp",
        "location": "Remote",
        "salary_min": 80000,
        "salary_max": 120000,
        "job_type": "full_time",
        "experience_level": "senior",
        "skills": ["Python", "FastAPI", "MongoDB", "Docker"]
    }


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "email": "newuser@test.com",
        "password": "NewUser123!",
        "role": "job_seeker",
        "first_name": "John",
        "last_name": "Doe"
    }


# Mock fixtures for external services
@pytest.fixture
def mock_email_service():
    """Mock email service for testing."""
    class MockEmailService:
        def __init__(self):
            self.sent_emails = []
        
        async def send_verification_email(self, email: str, token: str):
            self.sent_emails.append({
                "type": "verification",
                "email": email,
                "token": token
            })
            return True
        
        async def send_password_reset_email(self, email: str, token: str):
            self.sent_emails.append({
                "type": "password_reset",
                "email": email,
                "token": token
            })
            return True
    
    return MockEmailService()


@pytest.fixture
def mock_oauth_providers():
    """Mock OAuth providers for testing."""
    class MockOAuthProvider:
        def __init__(self, provider_name: str):
            self.provider_name = provider_name
            self.users = {
                "google": {
                    "id": "google_123",
                    "email": "user@gmail.com",
                    "name": "Google User",
                    "picture": "https://example.com/avatar.jpg"
                },
                "linkedin": {
                    "id": "linkedin_456",
                    "email": "user@linkedin.com",
                    "name": "LinkedIn User",
                    "picture": "https://example.com/linkedin-avatar.jpg"
                },
                "github": {
                    "id": "github_789",
                    "email": "user@github.com",
                    "name": "GitHub User",
                    "avatar_url": "https://example.com/github-avatar.jpg"
                }
            }
        
        async def get_user_info(self, access_token: str):
            return self.users.get(self.provider_name, {})
    
    return {
        "google": MockOAuthProvider("google"),
        "linkedin": MockOAuthProvider("linkedin"),
        "github": MockOAuthProvider("github")
    }


# Performance testing fixtures
@pytest.fixture
def performance_test_users():
    """Generate multiple users for performance testing."""
    async def _create_users(count: int = 100):
        users = []
        for i in range(count):
            user = User(
                email=f"perftest{i}@test.com",
                password_hash=get_password_hash("TestPass123!"),
                role="job_seeker" if i % 2 == 0 else "employer",
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow()
            )
            users.append(user)
        
        # Bulk insert for better performance
        await User.insert_many(users)
        return users
    
    return _create_users


# Security testing fixtures
@pytest.fixture
def security_test_data():
    """Data for security testing scenarios."""
    return {
        "sql_injection_attempts": [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin'--",
            "' OR 1=1#"
        ],
        "xss_attempts": [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>"
        ],
        "weak_passwords": [
            "123",
            "password",
            "admin",
            "12345678",
            "qwerty"
        ],
        "invalid_emails": [
            "invalid-email",
            "@domain.com",
            "user@",
            "user..name@domain.com",
            "user@domain"
        ]
    }