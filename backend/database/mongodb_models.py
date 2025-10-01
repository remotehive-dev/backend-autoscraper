#!/usr/bin/env python3
"""
MongoDB Document Models using Beanie ODM
Replacement for SQLAlchemy models to work with MongoDB Atlas
"""

from beanie import Document, Indexed, Link
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid
# from bson import ObjectId  # Removed to fix Pydantic schema generation

# Import enums from core
from backend.core.enums import ScraperStatus, ScraperSource, CSVImportStatus


class UserRole(str, Enum):
    JOB_SEEKER = "job_seeker"
    EMPLOYER = "employer"
    FREELANCER = "freelancer"
    NEWSLETTER_SUBSCRIBER = "newsletter_subscriber"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(Document):
    """User document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    clerk_user_id: Optional[str] = Field(None, unique=True)
    email: EmailStr = Field(unique=True)
    password_hash: Optional[str] = None
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: UserRole = UserRole.JOB_SEEKER
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "users"
        indexes = [
            "email",
            "clerk_user_id",
            "role",
            "is_active"
        ]


class ContactSubmission(Document):
    """Contact form submission document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str
    email: str
    subject: str
    message: str
    inquiry_type: str = "general"
    phone: Optional[str] = None
    company_name: Optional[str] = None
    status: str = "new"
    priority: str = "medium"
    assigned_to: Optional[str] = None
    admin_notes: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    source: str = "website_contact_form"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    
    class Settings:
        name = "contact_submissions"
        indexes = [
            "email",
            "status",
            "created_at",
            "inquiry_type"
        ]


class ContactInformation(Document):
    """Contact information document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    category: str
    label: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    office_hours: Optional[str] = None
    timezone: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    is_primary: bool = False
    display_order: int = 0
    meta_data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "contact_information"
        indexes = [
            "category",
            "is_active",
            "is_primary"
        ]


class SeoSettings(Document):
    """SEO settings document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    site_title: Optional[str] = None
    site_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    og_type: str = "website"
    twitter_card: str = "summary_large_image"
    twitter_site: Optional[str] = None
    twitter_creator: Optional[str] = None
    canonical_url: Optional[str] = None
    robots_txt: Optional[str] = None
    sitemap_url: Optional[str] = None
    google_analytics_id: Optional[str] = None
    google_tag_manager_id: Optional[str] = None
    facebook_pixel_id: Optional[str] = None
    google_site_verification: Optional[str] = None
    bing_site_verification: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "seo_settings"


class Review(Document):
    """Review document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    author: str
    email: Optional[str] = None
    rating: int
    title: Optional[str] = None
    content: str
    company: Optional[str] = None
    position: Optional[str] = None
    status: str = "pending"
    featured: bool = False
    helpful_count: int = 0
    verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "reviews"
        indexes = [
            "status",
            "featured",
            "rating",
            "created_at"
        ]


class Ad(Document):
    """Advertisement document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str
    type: str
    position: str
    status: str = "active"
    content: Optional[str] = None
    script_code: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    budget: Optional[float] = None
    clicks: int = 0
    impressions: int = 0
    revenue: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "ads"
        indexes = [
            "status",
            "position",
            "type"
        ]


class JobSeeker(Document):
    """Job seeker profile document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    user_id: str = Field(..., unique=True)  # Reference to User document
    current_title: Optional[str] = None
    experience_level: Optional[str] = None
    years_of_experience: Optional[int] = None
    skills: Optional[str] = None  # JSON string for skills array
    preferred_job_types: Optional[str] = None  # JSON string for job types array
    preferred_locations: Optional[str] = None  # JSON string for locations array
    remote_work_preference: bool = False
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    salary_currency: str = "USD"
    resume_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    cover_letter_template: Optional[str] = None
    is_actively_looking: bool = True
    education_level: Optional[str] = None
    field_of_study: Optional[str] = None
    university: Optional[str] = None
    graduation_year: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "job_seekers"
        indexes = [
            "user_id",
            "experience_level",
            "is_actively_looking"
        ]


class Employer(Document):
    """Employer profile document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    user_id: str  # Reference to User document
    employer_number: Optional[str] = Field(None, unique=True)  # RH00 series
    company_name: str
    company_email: Indexed(str, unique=True)
    company_phone: Optional[str] = None
    company_website: Optional[str] = None
    company_description: Optional[str] = None
    company_logo: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    location: Optional[str] = None
    is_verified: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "employers"
        indexes = [
            "user_id",
            "company_email",
            "employer_number",
            "is_verified"
        ]


class JobPost(Document):
    """Job post document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    employer_id: str  # Reference to Employer document
    title: str
    description: str
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    benefits: Optional[str] = None
    job_type: str
    work_location: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    experience_level: Optional[str] = None
    education_level: Optional[str] = None
    skills_required: Optional[List[str]] = None
    application_deadline: Optional[datetime] = None
    is_remote: bool = False
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: Optional[str] = None
    
    # Status and workflow
    status: str = "draft"
    priority: str = "normal"
    workflow_stage: str = "draft"
    employer_number: Optional[str] = None
    auto_publish: bool = False
    scheduled_publish_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    last_workflow_action: Optional[str] = None
    workflow_notes: Optional[str] = None
    admin_priority: int = 0
    requires_review: bool = False
    review_completed_at: Optional[datetime] = None
    review_completed_by: Optional[str] = None
    
    # Approval workflow
    submitted_for_approval_at: Optional[datetime] = None
    submitted_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejection_notes: Optional[str] = None
    
    # Publishing
    published_at: Optional[datetime] = None
    published_by: Optional[str] = None
    unpublished_at: Optional[datetime] = None
    unpublished_by: Optional[str] = None
    unpublish_reason: Optional[str] = None
    
    # Flags and features
    is_featured: bool = False
    is_urgent: bool = False
    is_flagged: bool = False
    flagged_at: Optional[datetime] = None
    flagged_by: Optional[str] = None
    flagged_reason: Optional[str] = None
    
    # Metrics
    views_count: int = 0
    applications_count: int = 0
    
    # External integration
    external_apply_url: Optional[str] = None
    external_id: Optional[str] = None
    external_source: Optional[str] = None
    
    # Denormalized data
    company_name: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "job_posts"
        indexes = [
            "employer_id",
            "status",
            "workflow_stage",
            "is_remote",
            "job_type",
            "created_at",
            "published_at",
            "application_deadline"
        ]


class JobWorkflowLog(Document):
    """Job workflow log document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    job_post_id: str  # Reference to JobPost document
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    performed_by: str  # Reference to User document
    reason: Optional[str] = None
    notes: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "job_workflow_logs"
        indexes = [
            "job_post_id",
            "action",
            "performed_by",
            "created_at"
        ]


class JobApplication(Document):
    """Job application document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    job_post_id: str  # Reference to JobPost document
    job_seeker_id: str  # Reference to JobSeeker document
    status: str = "pending"
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    additional_documents: Optional[List[str]] = None
    application_source: str = "website"
    notes: Optional[str] = None
    employer_notes: Optional[str] = None
    interview_scheduled_at: Optional[datetime] = None
    interview_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "job_applications"
        indexes = [
            "job_post_id",
            "job_seeker_id",
            "status",
            "created_at"
        ]


# Scraper Models
class ScraperConfig(Document):
    """Scraper configuration document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    user_id: str  # Reference to User document
    name: str
    target_url: str
    selectors: Dict[str, Any]
    schedule_enabled: bool = False
    schedule_interval: Optional[int] = None
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "scraper_configs"
        indexes = [
            "user_id",
            "is_active",
            "schedule_enabled"
        ]


class ScraperLog(Document):
    """Scraper log document model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    scraper_config_id: str  # Reference to ScraperConfig document
    status: ScraperStatus
    message: Optional[str] = None
    error_details: Optional[str] = None
    items_found: int = 0
    items_processed: int = 0
    execution_time: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "scraper_logs"
        indexes = [
            "scraper_config_id",
            "status",
            "created_at"
        ]


class ScraperState(Document):
    """Scraper state document model for Redis backup and persistence"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    scraper_config_id: str  # Reference to ScraperConfig document
    current_state: str = "idle"
    state_data: Dict[str, Any] = Field(default_factory=dict)
    redis_key: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    is_paused: bool = False
    current_page: int = 0
    processed_urls: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "scraper_states"
        indexes = [
            "scraper_config_id",
            "redis_key",
            "current_state",
            "last_updated"
        ]


class EmailVerificationToken(Document):
    """Email verification token for user email verification"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    user_id: str = Field(..., description="User ID this token belongs to")
    token: str = Field(..., description="Unique verification token")
    expires_at: datetime = Field(..., description="Token expiration timestamp")
    is_used: bool = Field(default=False, description="Whether token has been used")
    used_at: Optional[datetime] = Field(None, description="When token was used")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "email_verification_tokens"
        indexes = [
            "user_id",
            "token",
            "expires_at"
        ]


class PasswordResetToken(Document):
    """Password reset token for user password reset functionality"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    user_id: str = Field(..., description="User ID this token belongs to")
    email: str = Field(..., description="Email address for password reset")
    token: str = Field(..., description="Unique password reset token")
    expires_at: datetime = Field(..., description="Token expiration timestamp")
    is_used: bool = Field(default=False, description="Whether token has been used")
    used_at: Optional[datetime] = Field(None, description="When token was used")
    ip_address: Optional[str] = Field(None, description="IP address of reset request")
    user_agent: Optional[str] = Field(None, description="User agent of reset request")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "password_reset_tokens"
        indexes = [
            "user_id",
            "email",
            "token",
            "expires_at",
            "is_used"
        ]


class LoginAttempt(Document):
    """Login attempt tracking for security purposes"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    email: str = Field(..., description="Email address used in login attempt")
    ip_address: str = Field(..., description="IP address of login attempt")
    user_agent: Optional[str] = Field(None, description="User agent string")
    success: bool = Field(..., description="Whether login was successful")
    failure_reason: Optional[str] = Field(None, description="Reason for login failure")
    user_id: Optional[str] = Field(None, description="User ID if login was successful")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "login_attempts"
        indexes = [
            "email",
            "ip_address",
            "success",
            "created_at",
            "user_id"
        ]


class UserSession(Document):
    """User session tracking"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    user_id: str = Field(..., description="User ID for this session")
    session_token: str = Field(..., description="Unique session token")
    ip_address: str = Field(..., description="IP address of session")
    user_agent: Optional[str] = Field(None, description="User agent string")
    is_active: bool = Field(default=True, description="Whether session is active")
    expires_at: datetime = Field(..., description="Session expiration timestamp")
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "user_sessions"
        indexes = [
            "user_id",
            "session_token",
            "is_active",
            "expires_at",
            "last_activity"
        ]