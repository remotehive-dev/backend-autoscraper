"""MongoDB models using Beanie ODM for RemoteHive application"""

from beanie import Document, Indexed, PydanticObjectId
from pydantic import BaseModel, Field, EmailStr, ConfigDict, computed_field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid
# from bson import ObjectId  # Removed to fix Pydantic schema generation

# Enums
class UserRole(str, Enum):
    JOB_SEEKER = "job_seeker"
    EMPLOYER = "employer"
    FREELANCER = "freelancer"
    GEEK_WORKER = "geek_worker"
    NEWSLETTER_SUBSCRIBER = "newsletter_subscriber"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class JobStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    EXPIRED = "expired"

class ApplicationStatus(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    SHORTLISTED = "shortlisted"
    INTERVIEWED = "interviewed"
    REJECTED = "rejected"
    HIRED = "hired"

class ContactStatus(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

# Base Document with common fields
class BaseDocument(Document):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        use_state_management = True

# User Management Models
class User(BaseDocument):
    clerk_user_id: Optional[str] = Field(None, unique=True)
    email: EmailStr = Field(unique=True)
    password_hash: Optional[str] = None
    first_name: str
    last_name: str
    full_name: Optional[str] = None  # For OAuth users who provide full name
    phone: Optional[str] = None
    role: UserRole = Field(default=UserRole.JOB_SEEKER)
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    last_login: Optional[datetime] = None
    profile_picture: Optional[str] = None  # Profile picture URL from OAuth
    
    # OAuth-related fields
    oauth_provider: Optional[str] = None  # google, facebook, etc.
    oauth_id: Optional[str] = None  # OAuth provider user ID
    oauth_access_token: Optional[str] = None  # Current access token
    oauth_refresh_token: Optional[str] = None  # Refresh token
    oauth_token_expires_at: Optional[datetime] = None  # Token expiration time
    
    @computed_field
    @property
    def is_admin(self) -> bool:
        """Check if user has admin or super_admin role"""
        return self.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]
    
    @computed_field
    @property
    def display_name(self) -> str:
        """Get display name, preferring full_name if available"""
        if self.full_name:
            return self.full_name
        return f"{self.first_name} {self.last_name}"
    
    class Settings:
        name = "users"
        indexes = [
            "email",
            "clerk_user_id",
            "role",
            "is_active"
        ]

class JobSeeker(BaseDocument):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    user_id: PydanticObjectId = Field(..., description="Reference to User document")
    current_title: Optional[str] = None
    experience_level: Optional[str] = None
    years_of_experience: Optional[int] = None
    skills: List[str] = Field(default_factory=list)
    preferred_job_types: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    remote_work_preference: bool = Field(default=False)
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    salary_currency: str = Field(default="USD")
    resume_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    bio: Optional[str] = None
    salary_expectation_min: Optional[int] = None
    salary_expectation_max: Optional[int] = None
    availability_date: Optional[datetime] = None
    cover_letter_template: Optional[str] = None
    is_actively_looking: bool = Field(default=True)
    education_level: Optional[str] = None
    field_of_study: Optional[str] = None
    university: Optional[str] = None
    graduation_year: Optional[int] = None
    
    class Settings:
        name = "job_seekers"
        indexes = [
            "user_id",
            "experience_level",
            "is_actively_looking"
        ]

class Employer(BaseDocument):
    user_id: Optional[PydanticObjectId] = Field(None, description="Reference to User document")
    company_name: str = Field(..., description="Company name")
    company_description: Optional[str] = Field(None, description="Company description")
    company_website: Optional[str] = Field(None, description="Company website URL")
    company_size: Optional[str] = Field(None, description="Company size range")
    industry: Optional[str] = Field(None, description="Industry type")
    location: Optional[str] = Field(None, description="Company location")
    logo_url: Optional[str] = Field(None, description="Company logo URL")
    verified: bool = Field(default=False, description="Company verification status")
    subscription_plan: Optional[str] = Field(None, description="Current subscription plan")
    subscription_expires_at: Optional[datetime] = Field(None, description="Subscription expiry date")
    
    class Settings:
        name = "employers"


class Freelancer(BaseDocument):
    user_id: Optional[PydanticObjectId] = Field(None, description="Reference to User document")
    professional_title: str = Field(..., description="Professional title/role")
    bio: Optional[str] = Field(None, description="Professional bio")
    skills: List[str] = Field(default_factory=list, description="List of skills")
    hourly_rate: Optional[float] = Field(None, description="Hourly rate in USD")
    availability: Optional[str] = Field(None, description="Availability status")
    portfolio_url: Optional[str] = Field(None, description="Portfolio website URL")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    github_url: Optional[str] = Field(None, description="GitHub profile URL")
    experience_years: Optional[int] = Field(None, description="Years of experience")
    languages: List[str] = Field(default_factory=list, description="Spoken languages")
    timezone: Optional[str] = Field(None, description="Preferred timezone")
    verified: bool = Field(default=False, description="Profile verification status")
    rating: Optional[float] = Field(None, description="Average rating")
    total_projects: int = Field(default=0, description="Total completed projects")
    
    class Settings:
        name = "freelancers"


class GeekWorker(BaseDocument):
    user_id: Optional[PydanticObjectId] = Field(None, description="Reference to User document")
    professional_title: str = Field(..., description="Professional title/role")
    bio: Optional[str] = Field(None, description="Professional bio")
    skills: List[str] = Field(default_factory=list, description="List of technical skills")
    specializations: List[str] = Field(default_factory=list, description="Technical specializations")
    experience_level: Optional[str] = Field(None, description="Experience level (junior, mid, senior, lead)")
    years_of_experience: Optional[int] = Field(None, description="Years of experience")
    hourly_rate: Optional[float] = Field(None, description="Hourly rate in USD")
    availability: Optional[str] = Field(None, description="Availability status")
    remote_work_preference: bool = Field(default=True, description="Preference for remote work")
    portfolio_url: Optional[str] = Field(None, description="Portfolio website URL")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    github_url: Optional[str] = Field(None, description="GitHub profile URL")
    stackoverflow_url: Optional[str] = Field(None, description="Stack Overflow profile URL")
    personal_website: Optional[str] = Field(None, description="Personal website URL")
    languages: List[str] = Field(default_factory=list, description="Spoken languages")
    programming_languages: List[str] = Field(default_factory=list, description="Programming languages")
    frameworks: List[str] = Field(default_factory=list, description="Frameworks and technologies")
    timezone: Optional[str] = Field(None, description="Preferred timezone")
    verified: bool = Field(default=False, description="Profile verification status")
    rating: Optional[float] = Field(None, description="Average rating")
    total_projects: int = Field(default=0, description="Total completed projects")
    certifications: List[str] = Field(default_factory=list, description="Professional certifications")
    education_level: Optional[str] = Field(None, description="Highest education level")
    field_of_study: Optional[str] = Field(None, description="Field of study")
    
    class Settings:
        name = "geek_workers"


class NewsletterSubscriber(BaseDocument):
    email: str = Field(..., description="Subscriber email address")
    user_id: Optional[PydanticObjectId] = Field(None, description="Reference to User document if registered")
    subscription_type: str = Field(default="geeks_and_perks", description="Newsletter type")
    preferences: Dict[str, bool] = Field(default_factory=dict, description="Subscription preferences")
    subscribed_at: datetime = Field(default_factory=datetime.utcnow, description="Subscription date")
    is_active: bool = Field(default=True, description="Subscription status")
    unsubscribed_at: Optional[datetime] = Field(None, description="Unsubscription date")
    source: Optional[str] = Field(None, description="Subscription source")
    
    class Settings:
        name = "newsletter_subscribers"


# RBAC Models
class Permission(BaseDocument):
    name: str = Field(..., description="Permission name")
    resource: str = Field(..., description="Resource being protected")
    action: str = Field(..., description="Action allowed on resource")
    description: Optional[str] = Field(None, description="Permission description")
    is_active: bool = Field(default=True, description="Permission status")
    
    class Settings:
        name = "permissions"
        indexes = [
            [("name", 1)],
            [("resource", 1), ("action", 1)]
        ]


class RolePermission(BaseDocument):
    role: UserRole = Field(..., description="User role")
    permission_id: PydanticObjectId = Field(..., description="Reference to Permission document")
    granted_at: datetime = Field(default_factory=datetime.utcnow, description="When permission was granted")
    granted_by: Optional[PydanticObjectId] = Field(None, description="User who granted this permission")
    is_active: bool = Field(default=True, description="Permission assignment status")
    
    class Settings:
        name = "role_permissions"
        indexes = [
            [("role", 1), ("permission_id", 1)],
            "is_active"
        ]


# Lead Management Models
class LeadSource(str, Enum):
    GOOGLE_AUTH = "google_auth"
    LINKEDIN_SIGNUP = "linkedin_signup"
    SSO = "sso"
    NORMAL_AUTH = "normal_auth"
    DIRECT_SIGNUP = "direct_signup"
    REFERRAL = "referral"
    SOCIAL_MEDIA = "social_media"
    EMAIL_CAMPAIGN = "email_campaign"
    WEBSITE_FORM = "website_form"
    API = "api"
    IMPORT = "import"
    OTHER = "other"


class LeadCategory(str, Enum):
    EMPLOYER = "employer"
    JOB_SEEKER = "jobseeker"
    FREELANCER = "freelancer"
    CORPORATE_SIGNUP = "corporate_signup"
    NEWSLETTER_SUBSCRIBER = "newsletter_subscriber"
    PARTNERSHIP = "partnership"
    VENDOR = "vendor"
    OTHER = "other"


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    NURTURING = "nurturing"
    PROPOSAL_SENT = "proposal_sent"
    NEGOTIATION = "negotiation"
    CONVERTED = "converted"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    UNQUALIFIED = "unqualified"
    ON_HOLD = "on_hold"


class LeadScore(str, Enum):
    COLD = "cold"  # 0-25
    WARM = "warm"  # 26-50
    HOT = "hot"    # 51-75
    BURNING = "burning"  # 76-100


class ActivityType(str, Enum):
    EMAIL = "email"
    CALL = "call"
    MEETING = "meeting"
    NOTE = "note"
    TASK = "task"
    FOLLOW_UP = "follow_up"
    PROPOSAL = "proposal"
    CONTRACT = "contract"
    PAYMENT = "payment"
    STATUS_CHANGE = "status_change"
    ASSIGNMENT = "assignment"
    OTHER = "other"


class Lead(BaseDocument):
    # Basic Information
    first_name: str = Field(..., description="Lead first name")
    last_name: str = Field(..., description="Lead last name")
    email: Indexed(EmailStr) = Field(..., description="Lead email address")
    phone: Optional[str] = Field(None, description="Lead phone number")
    company: Optional[str] = Field(None, description="Lead company name")
    job_title: Optional[str] = Field(None, description="Lead job title")
    
    # Lead Classification
    lead_source: LeadSource = Field(..., description="How the lead was acquired")
    lead_category: LeadCategory = Field(..., description="Type of lead")
    status: LeadStatus = Field(default=LeadStatus.NEW, description="Current lead status")
    
    # Lead Scoring and Quality
    score: int = Field(default=0, description="Lead score (0-100)")
    score_grade: LeadScore = Field(default=LeadScore.COLD, description="Lead score grade")
    quality_rating: Optional[int] = Field(None, description="Manual quality rating (1-5)")
    
    # Assignment and Ownership
    assigned_to: Optional[PydanticObjectId] = Field(None, description="Assigned sales rep/admin user ID")
    assigned_at: Optional[datetime] = Field(None, description="When lead was assigned")
    assigned_by: Optional[PydanticObjectId] = Field(None, description="Who assigned the lead")
    
    # Contact Information
    website: Optional[str] = Field(None, description="Lead website")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    address: Optional[str] = Field(None, description="Lead address")
    city: Optional[str] = Field(None, description="Lead city")
    state: Optional[str] = Field(None, description="Lead state/province")
    country: Optional[str] = Field(None, description="Lead country")
    postal_code: Optional[str] = Field(None, description="Lead postal code")
    
    # Lead Details
    industry: Optional[str] = Field(None, description="Lead industry")
    company_size: Optional[str] = Field(None, description="Company size range")
    annual_revenue: Optional[str] = Field(None, description="Annual revenue range")
    budget: Optional[str] = Field(None, description="Budget range")
    timeline: Optional[str] = Field(None, description="Expected timeline")
    
    # Tracking Information
    user_id: Optional[PydanticObjectId] = Field(None, description="Associated user ID if converted")
    utm_source: Optional[str] = Field(None, description="UTM source parameter")
    utm_medium: Optional[str] = Field(None, description="UTM medium parameter")
    utm_campaign: Optional[str] = Field(None, description="UTM campaign parameter")
    utm_term: Optional[str] = Field(None, description="UTM term parameter")
    utm_content: Optional[str] = Field(None, description="UTM content parameter")
    referrer_url: Optional[str] = Field(None, description="Referrer URL")
    landing_page: Optional[str] = Field(None, description="Landing page URL")
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    
    # Engagement Tracking
    first_contact_date: Optional[datetime] = Field(None, description="Date of first contact")
    last_contact_date: Optional[datetime] = Field(None, description="Date of last contact")
    last_activity_date: Optional[datetime] = Field(None, description="Date of last activity")
    next_follow_up_date: Optional[datetime] = Field(None, description="Next scheduled follow-up")
    
    # Conversion Tracking
    converted_at: Optional[datetime] = Field(None, description="Conversion date")
    conversion_value: Optional[float] = Field(None, description="Conversion value in USD")
    lost_reason: Optional[str] = Field(None, description="Reason for lost lead")
    
    # Additional Information
    notes: Optional[str] = Field(None, description="General notes about the lead")
    tags: List[str] = Field(default_factory=list, description="Lead tags")
    custom_fields: Dict[str, Any] = Field(default_factory=dict, description="Custom fields")
    
    # System Fields
    is_active: bool = Field(default=True, description="Lead active status")
    is_duplicate: bool = Field(default=False, description="Duplicate lead flag")
    duplicate_of: Optional[PydanticObjectId] = Field(None, description="Original lead ID if duplicate")
    
    @computed_field
    @property
    def full_name(self) -> str:
        """Get full name of the lead"""
        return f"{self.first_name} {self.last_name}"
    
    @computed_field
    @property
    def is_qualified(self) -> bool:
        """Check if lead is qualified"""
        return self.status in [LeadStatus.QUALIFIED, LeadStatus.NURTURING, 
                              LeadStatus.PROPOSAL_SENT, LeadStatus.NEGOTIATION]
    
    @computed_field
    @property
    def is_converted(self) -> bool:
        """Check if lead is converted"""
        return self.status in [LeadStatus.CONVERTED, LeadStatus.CLOSED_WON]
    
    @computed_field
    @property
    def days_since_created(self) -> int:
        """Get days since lead was created"""
        return (datetime.utcnow() - self.created_at).days
    
    @computed_field
    @property
    def days_since_last_contact(self) -> Optional[int]:
        """Get days since last contact"""
        if self.last_contact_date:
            return (datetime.utcnow() - self.last_contact_date).days
        return None
    
    class Settings:
        name = "leads"
        indexes = [
            "email",
            "lead_source",
            "lead_category",
            "status",
            "assigned_to",
            "score",
            "created_at",
            "is_active",
            [("first_name", 1), ("last_name", 1)],
            [("company", 1), ("email", 1)]
        ]


class LeadActivity(BaseDocument):
    lead_id: PydanticObjectId = Field(..., description="Reference to Lead document")
    activity_type: ActivityType = Field(..., description="Type of activity")
    title: str = Field(..., description="Activity title")
    description: Optional[str] = Field(None, description="Activity description")
    
    # Activity Details
    performed_by: Optional[PydanticObjectId] = Field(None, description="User who performed the activity")
    performed_at: datetime = Field(default_factory=datetime.utcnow, description="When activity was performed")
    
    # Communication Details
    email_subject: Optional[str] = Field(None, description="Email subject if email activity")
    email_body: Optional[str] = Field(None, description="Email body if email activity")
    call_duration: Optional[int] = Field(None, description="Call duration in minutes")
    call_outcome: Optional[str] = Field(None, description="Call outcome")
    meeting_location: Optional[str] = Field(None, description="Meeting location")
    meeting_attendees: List[str] = Field(default_factory=list, description="Meeting attendees")
    
    # Task Details
    due_date: Optional[datetime] = Field(None, description="Task due date")
    completed_at: Optional[datetime] = Field(None, description="Task completion date")
    priority: Priority = Field(default=Priority.MEDIUM, description="Activity priority")
    
    # Attachments and Links
    attachments: List[str] = Field(default_factory=list, description="Attachment URLs")
    related_urls: List[str] = Field(default_factory=list, description="Related URLs")
    
    # System Fields
    is_automated: bool = Field(default=False, description="Whether activity was automated")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Settings:
        name = "lead_activities"
        indexes = [
            "lead_id",
            "activity_type",
            "performed_by",
            "performed_at",
            "due_date",
            [("lead_id", 1), ("performed_at", -1)]
        ]


class LeadTask(BaseDocument):
    lead_id: PydanticObjectId = Field(..., description="Reference to Lead document")
    title: str = Field(..., description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    
    # Assignment
    assigned_to: PydanticObjectId = Field(..., description="Assigned user ID")
    assigned_by: Optional[PydanticObjectId] = Field(None, description="User who assigned the task")
    assigned_at: datetime = Field(default_factory=datetime.utcnow, description="Assignment date")
    
    # Scheduling
    due_date: datetime = Field(..., description="Task due date")
    reminder_date: Optional[datetime] = Field(None, description="Reminder date")
    
    # Status
    is_completed: bool = Field(default=False, description="Task completion status")
    completed_at: Optional[datetime] = Field(None, description="Task completion date")
    completed_by: Optional[PydanticObjectId] = Field(None, description="User who completed the task")
    
    # Priority and Category
    priority: Priority = Field(default=Priority.MEDIUM, description="Task priority")
    category: Optional[str] = Field(None, description="Task category")
    
    # Additional Details
    notes: Optional[str] = Field(None, description="Task notes")
    attachments: List[str] = Field(default_factory=list, description="Attachment URLs")
    
    class Settings:
        name = "lead_tasks"
        indexes = [
            "lead_id",
            "assigned_to",
            "due_date",
            "is_completed",
            "priority",
            [("assigned_to", 1), ("due_date", 1)],
            [("lead_id", 1), ("due_date", 1)]
        ]


class LeadNote(BaseDocument):
    lead_id: PydanticObjectId = Field(..., description="Reference to Lead document")
    title: Optional[str] = Field(None, description="Note title")
    content: str = Field(..., description="Note content")
    
    # Authorship
    created_by: PydanticObjectId = Field(..., description="User who created the note")
    
    # Visibility
    is_private: bool = Field(default=False, description="Whether note is private")
    visible_to: List[PydanticObjectId] = Field(default_factory=list, description="Users who can see this note")
    
    # Categorization
    category: Optional[str] = Field(None, description="Note category")
    tags: List[str] = Field(default_factory=list, description="Note tags")
    
    # Attachments
    attachments: List[str] = Field(default_factory=list, description="Attachment URLs")
    
    class Settings:
        name = "lead_notes"
        indexes = [
            "lead_id",
            "created_by",
            "created_at",
            [("lead_id", 1), ("created_at", -1)]
        ]


class PasswordResetToken(BaseDocument):
    email: EmailStr = Field(..., description="Email address for password reset")
    user_type: str = Field(..., description="Type of user (admin, employer, job_seeker, etc.)")
    token_hash: str = Field(..., description="Hashed reset token")
    expires_at: datetime = Field(..., description="Token expiration time")
    used: bool = Field(default=False, description="Whether token has been used")
    used_at: Optional[datetime] = Field(None, description="When token was used")
    
    class Settings:
        name = "password_reset_tokens"
        indexes = [
            [("email", 1)],
            [("token_hash", 1)],
            [("expires_at", 1)],
            [("email", 1), ("user_type", 1)]
        ]

# Job Management Models
class JobPost(BaseDocument):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    employer_id: PydanticObjectId = Field(..., description="Reference to Employer document")
    title: str
    description: str
    requirements: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    skills_required: List[str] = Field(default_factory=list)
    job_type: str  # full-time, part-time, contract, freelance
    experience_level: str  # entry, mid, senior, executive
    location: Optional[str] = None
    is_remote: bool = Field(default=False)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = Field(default="USD")
    benefits: List[str] = Field(default_factory=list)
    status: JobStatus = Field(default=JobStatus.DRAFT)
    application_deadline: Optional[datetime] = None
    external_url: Optional[str] = None
    views_count: int = Field(default=0)
    applications_count: int = Field(default=0)
    featured: bool = Field(default=False)
    
    class Settings:
        name = "job_posts"
        indexes = [
            "employer_id",
            "status",
            "job_type",
            "experience_level",
            "is_remote",
            "featured",
            "created_at"
        ]

class JobApplication(BaseDocument):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    job_post_id: PydanticObjectId = Field(..., description="Reference to JobPost document")
    job_seeker_id: PydanticObjectId = Field(..., description="Reference to JobSeeker document")
    status: ApplicationStatus = Field(default=ApplicationStatus.PENDING)
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    additional_documents: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    interview_scheduled: Optional[datetime] = None
    feedback: Optional[str] = None
    
    class Settings:
        name = "job_applications"
        indexes = [
            "job_post_id",
            "job_seeker_id",
            "status",
            "created_at"
        ]

class SavedJob(BaseDocument):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    job_seeker_id: PydanticObjectId = Field(..., description="Reference to JobSeeker document")
    job_post_id: PydanticObjectId = Field(..., description="Reference to JobPost document")
    notes: Optional[str] = Field(None, description="Personal notes about the job")
    saved_at: datetime = Field(default_factory=datetime.utcnow, description="When the job was saved")
    
    class Settings:
        name = "saved_jobs"
        indexes = [
            "job_seeker_id",
            "job_post_id",
            "saved_at",
            [("job_seeker_id", 1), ("job_post_id", 1)]  # Compound index for uniqueness
        ]

class AutoApplySettings(BaseDocument):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    job_seeker_id: PydanticObjectId = Field(..., description="Reference to JobSeeker document")
    enabled: bool = Field(default=False, description="Whether auto-apply is enabled")
    max_applications_per_day: int = Field(default=5, description="Maximum applications per day")
    keywords: List[str] = Field(default_factory=list, description="Keywords to match in job posts")
    excluded_companies: List[str] = Field(default_factory=list, description="Companies to exclude")
    salary_min: Optional[int] = Field(None, description="Minimum salary requirement")
    location_preferences: List[str] = Field(default_factory=list, description="Preferred locations")
    job_types: List[str] = Field(default_factory=list, description="Preferred job types")
    experience_level: Optional[str] = Field(None, description="Experience level preference")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When settings were created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When settings were last updated")
    
    class Settings:
        name = "auto_apply_settings"
        indexes = [
            "job_seeker_id",
            "enabled",
            "created_at",
            "updated_at"
        ]

# Contact Management Models
class ContactSubmission(BaseDocument):
    name: str
    email: EmailStr
    subject: str
    message: str
    inquiry_type: str = Field(default="general")
    phone: Optional[str] = None
    company_name: Optional[str] = None
    status: ContactStatus = Field(default=ContactStatus.NEW)
    priority: Priority = Field(default=Priority.MEDIUM)
    assigned_to: Optional[str] = None
    admin_notes: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    source: str = Field(default="website_contact_form")
    resolved_at: Optional[datetime] = None
    
    class Settings:
        name = "contact_submissions"
        indexes = [
            "email",
            "status",
            "priority",
            "inquiry_type",
            "created_at"
        ]

class ContactInformation(BaseDocument):
    category: str
    label: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    office_hours: Optional[str] = None
    timezone: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    is_primary: bool = Field(default=False)
    display_order: int = Field(default=0)
    meta_data: Optional[Dict[str, Any]] = None
    
    class Settings:
        name = "contact_information"
        indexes = [
            "category",
            "is_active",
            "is_primary",
            "display_order"
        ]

# CMS Models
class SeoSettings(BaseDocument):
    site_title: Optional[str] = None
    site_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    og_type: str = Field(default="website")
    twitter_card: str = Field(default="summary_large_image")
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
    
    class Settings:
        name = "seo_settings"

class Review(BaseDocument):
    author: str
    email: Optional[EmailStr] = None
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = None
    content: str
    company: Optional[str] = None
    position: Optional[str] = None
    status: str = Field(default="pending")
    featured: bool = Field(default=False)
    helpful_count: int = Field(default=0)
    verified: bool = Field(default=False)
    
    class Settings:
        name = "reviews"
        indexes = [
            "status",
            "featured",
            "rating",
            "verified",
            "created_at"
        ]

class Ad(BaseDocument):
    name: str
    type: str
    position: str
    status: str = Field(default="active")
    content: Optional[str] = None
    script_code: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    budget: Optional[float] = None
    clicks: int = Field(default=0)
    impressions: int = Field(default=0)
    revenue: float = Field(default=0.0)
    
    class Settings:
        name = "ads"
        indexes = [
            "status",
            "type",
            "position",
            "start_date",
            "end_date"
        ]

# Payment Models
class PaymentGateway(BaseDocument):
    name: str
    provider: str  # stripe, paypal, razorpay, etc.
    is_active: bool = Field(default=True)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    supported_currencies: List[str] = Field(default_factory=list)
    transaction_fee_percentage: Optional[float] = None
    
    class Settings:
        name = "payment_gateways"
        indexes = ["provider", "is_active"]

class Transaction(BaseDocument):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    user_id: PydanticObjectId = Field(..., description="Reference to User document")
    gateway_id: PydanticObjectId = Field(..., description="Reference to PaymentGateway document")
    transaction_id: str = Field(..., unique=True)
    amount: float
    currency: str = Field(default="USD")
    status: str  # pending, completed, failed, refunded
    payment_method: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Settings:
        name = "transactions"
        indexes = [
            "user_id",
            "transaction_id",
            "status",
            "created_at"
        ]

class Refund(BaseDocument):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    transaction_id: PydanticObjectId = Field(..., description="Reference to Transaction document")
    amount: float
    reason: str
    status: str = Field(default="pending")
    processed_at: Optional[datetime] = None
    refund_id: Optional[str] = None
    
    class Settings:
        name = "refunds"
        indexes = [
            "transaction_id",
            "status",
            "created_at"
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


class OAuthAccount(BaseDocument):
    """OAuth account linking for users"""
    user_id: PydanticObjectId = Field(..., description="Reference to User document")
    provider: str = Field(..., description="OAuth provider (google, linkedin, github)")
    provider_user_id: str = Field(..., description="User ID from OAuth provider")
    email: EmailStr = Field(..., description="Email from OAuth provider")
    access_token: Optional[str] = Field(None, description="OAuth access token")
    refresh_token: Optional[str] = Field(None, description="OAuth refresh token")
    token_expires_at: Optional[datetime] = Field(None, description="Token expiration time")
    scope: Optional[str] = Field(None, description="OAuth scope granted")
    profile_data: Dict[str, Any] = Field(default_factory=dict, description="Additional profile data")
    is_active: bool = Field(default=True, description="Account link status")
    
    class Settings:
        name = "oauth_accounts"
        indexes = [
            "user_id",
            "provider",
            "provider_user_id",
            ["provider", "provider_user_id"],
            "email"
        ]


class Session(BaseDocument):
    """User session management"""
    user_id: PydanticObjectId = Field(..., description="Reference to User document")
    session_id: str = Field(..., unique=True, description="Unique session identifier")
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    expires_at: datetime = Field(..., description="Session expiration time")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    device_info: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Device information")
    is_active: bool = Field(default=True, description="Session status")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    
    class Settings:
        name = "sessions"
        indexes = [
            "user_id",
            "session_id",
            "access_token",
            "refresh_token",
            "expires_at",
            "is_active"
        ]


class AuditLog(BaseDocument):
    """Audit logging for security and compliance"""
    user_id: Optional[PydanticObjectId] = Field(None, description="User who performed the action")
    action: str = Field(..., description="Action performed")
    resource: str = Field(..., description="Resource affected")
    resource_id: Optional[str] = Field(None, description="ID of affected resource")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional action details")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    session_id: Optional[str] = Field(None, description="Session identifier")
    status: str = Field(..., description="Action status (success, failure, error)")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Action timestamp")
    
    class Settings:
        name = "audit_logs"
        indexes = [
            "user_id",
            "action",
            "resource",
            "timestamp",
            "status",
            "ip_address"
        ]

# Export all models
__all__ = [
    "User",
    "JobSeeker", 
    "Employer",
    "Freelancer",
    "NewsletterSubscriber",
    "Permission",
    "RolePermission",
    "JobPost",
    "JobApplication",
    "SavedJob",
    "AutoApplySettings",
    "Lead",
    "LeadActivity",
    "LeadTask",
    "LeadNote",
    "ContactSubmission",
    "ContactInformation",
    "SeoSettings",
    "Review",
    "Ad",
    "PaymentGateway",
    "Transaction",
    "Refund",
    "EmailVerificationToken",
    "PasswordResetToken",
    "OAuthAccount",
    "Session",
    "AuditLog",
    "UserRole",
    "JobStatus",
    "ApplicationStatus",
    "ContactStatus",
    "Priority"
]