from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
from backend.core.enums import ApplicationStatus

# Base Job Application Schema
class JobApplicationBase(BaseModel):
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    expected_salary: Optional[int] = None
    salary_currency: str = "USD"
    available_start_date: Optional[datetime] = None
    applicant_email: Optional[str] = None
    applicant_phone: Optional[str] = None

    @field_validator('expected_salary')
    @classmethod
    def validate_salary(cls, v):
        if v is not None and v < 0:
            raise ValueError('Expected salary must be non-negative')
        return v

# Job Application Create Schema
class JobApplicationCreate(JobApplicationBase):
    job_post_id: int

# Job Application Update Schema
class JobApplicationUpdate(BaseModel):
    cover_letter: Optional[str] = None
    resume_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    expected_salary: Optional[int] = None
    salary_currency: Optional[str] = None
    available_start_date: Optional[datetime] = None
    applicant_email: Optional[str] = None
    applicant_phone: Optional[str] = None

# Job Application Status Update Schema
class JobApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    status_notes: Optional[str] = None
    interview_scheduled_at: Optional[datetime] = None
    interview_notes: Optional[str] = None
    interview_feedback: Optional[str] = None
    interview_rating: Optional[int] = None
    employer_notes: Optional[str] = None

    @field_validator('interview_rating')
    @classmethod
    def validate_rating(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError('Interview rating must be between 1 and 5')
        return v

# Job Application Response Schema
class JobApplication(JobApplicationBase):
    id: int
    job_post_id: int
    applicant_id: int
    status: ApplicationStatus
    status_notes: Optional[str] = None
    interview_scheduled_at: Optional[datetime] = None
    interview_notes: Optional[str] = None
    interview_feedback: Optional[str] = None
    interview_rating: Optional[int] = None
    viewed_by_employer: bool
    viewed_at: Optional[datetime] = None
    employer_notes: Optional[str] = None
    external_id: Optional[str] = None
    external_source: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    status_changed_at: datetime
    
    class Config:
        from_attributes = True

# Job Application with Job Info
class JobApplicationWithJob(JobApplication):
    job_post: dict  # Will be populated with job post info

# Job Application with Applicant Info
class JobApplicationWithApplicant(JobApplication):
    applicant: dict  # Will be populated with applicant info

# Job Application Full Details
class JobApplicationFull(JobApplication):
    job_post: dict  # Will be populated with job post info
    applicant: dict  # Will be populated with applicant info

# Job Application List Response
class JobApplicationList(BaseModel):
    applications: List[JobApplication]
    total: int
    page: int
    per_page: int
    pages: int

# Job Application Statistics Schema
class JobApplicationStats(BaseModel):
    total_applications: int
    pending_applications: int
    reviewing_applications: int
    shortlisted_applications: int
    interviewed_applications: int
    accepted_applications: int
    rejected_applications: int
    applications_this_month: int
    avg_time_to_response: float  # in days
    top_job_posts_by_applications: List[dict]

# Job Application Search Schema
class JobApplicationSearch(BaseModel):
    status: Optional[ApplicationStatus] = None
    job_post_id: Optional[int] = None
    applicant_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    viewed_only: Optional[bool] = None
    page: int = 1
    per_page: int = 20