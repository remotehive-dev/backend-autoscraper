from pydantic import BaseModel, field_validator, HttpUrl
from typing import Optional, List
from datetime import datetime
from backend.core.enums import CompanySize, Industry

# Base Employer Schema
class EmployerBase(BaseModel):
    employer_number: Optional[str] = None  # RH00 series number
    company_name: str
    company_description: Optional[str] = None
    company_website: Optional[str] = None
    company_logo_url: Optional[str] = None
    company_size: Optional[CompanySize] = None
    industry: Optional[Industry] = None
    company_email: Optional[str] = None
    company_phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    linkedin_company_url: Optional[str] = None
    twitter_url: Optional[str] = None
    facebook_url: Optional[str] = None
    is_verified: bool = False
    is_premium: bool = False

    @field_validator('postal_code')
    @classmethod
    def validate_postal_code(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        return v

    @field_validator('company_name')
    @classmethod
    def validate_company_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Company name must be at least 2 characters long')
        return v.strip()

# Employer Create Schema
class EmployerCreate(EmployerBase):
    pass

# Employer Update Schema
class EmployerUpdate(BaseModel):
    employer_number: Optional[str] = None  # RH00 series number (read-only in updates)
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    company_website: Optional[str] = None
    company_logo_url: Optional[str] = None
    company_size: Optional[CompanySize] = None
    industry: Optional[Industry] = None
    company_email: Optional[str] = None
    company_phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    linkedin_company_url: Optional[str] = None
    twitter_url: Optional[str] = None
    facebook_url: Optional[str] = None

# Employer Response Schema
class Employer(EmployerBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Employer Profile Schema (with user info)
class EmployerProfile(Employer):
    user: dict  # Will be populated with user info

# Employer List Response
class EmployerList(BaseModel):
    employers: List[Employer]
    total: int
    page: int
    per_page: int
    pages: int

# Employer Statistics Schema
class EmployerStats(BaseModel):
    total_employers: int
    verified_employers: int
    new_employers_this_month: int
    avg_job_posts_per_employer: float
    top_industries: List[dict]
    company_size_distribution: dict
    rh_number_range: dict  # Latest RH number info
    active_employers_last_30_days: int

# Enhanced Employer with Job Stats
class EmployerWithJobStats(Employer):
    total_jobs: int = 0
    active_jobs: int = 0
    pending_jobs: int = 0
    draft_jobs: int = 0
    rejected_jobs: int = 0
    featured_jobs: int = 0
    avg_views: Optional[float] = None
    avg_applications: Optional[float] = None
    last_job_created: Optional[datetime] = None
    first_job_created: Optional[datetime] = None

# Employer Search/Filter Schema
class EmployerSearchParams(BaseModel):
    search: Optional[str] = None  # Search by company name, email, or RH number
    industry: Optional[Industry] = None
    company_size: Optional[CompanySize] = None
    is_verified: Optional[bool] = None
    is_premium: Optional[bool] = None
    has_active_jobs: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    sort_by: Optional[str] = "created_at"
    sort_order: Optional[str] = "desc"
    page: int = 1
    per_page: int = 20

# Employer Verification Schema
class EmployerVerification(BaseModel):
    is_verified: bool
    verification_notes: Optional[str] = None