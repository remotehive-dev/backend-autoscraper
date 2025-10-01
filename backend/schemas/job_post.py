from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import datetime
from backend.core.enums import JobType, WorkLocation, JobStatus, ExperienceLevel, JobAction, JobPriority, RejectionReason

# Base Job Post Schema
class JobPostBase(BaseModel):
    title: str
    description: str
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    benefits: Optional[str] = None
    job_type: JobType
    work_location: WorkLocation = WorkLocation.REMOTE
    experience_level: ExperienceLevel
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: Optional[str] = None
    is_remote: bool = True
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    skills_required: Optional[List[str]] = None
    education_level: Optional[str] = None
    application_deadline: Optional[datetime] = None
    is_featured: bool = False
    is_urgent: bool = False

# Job Post Creation Schema
class JobPostCreate(JobPostBase):
    employer_id: Optional[str] = None  # Optional for admin users to specify employer (UUID string)
    employer_number: Optional[str] = None  # RH00 series number
    auto_publish: bool = False
    scheduled_publish_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    workflow_notes: Optional[str] = None
    admin_priority: int = 0
    requires_review: bool = False
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if len(v.strip()) < 3:
            raise ValueError('Title must be at least 3 characters long')
        return v.strip()
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if len(v.strip()) < 50:
            raise ValueError('Description must be at least 50 characters long')
        return v.strip()
    
    @field_validator('salary_max')
    @classmethod
    def validate_salary_range(cls, v, info):
        if v is not None and hasattr(info, 'data') and 'salary_min' in info.data and info.data['salary_min'] is not None:
            if v < info.data['salary_min']:
                raise ValueError('Maximum salary must be greater than minimum salary')
        return v

# Job Post Update Schema
class JobPostUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    benefits: Optional[str] = None
    job_type: Optional[JobType] = None
    work_location: Optional[WorkLocation] = None
    experience_level: Optional[ExperienceLevel] = None
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: Optional[str] = None
    is_remote: Optional[bool] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    skills_required: Optional[List[str]] = None
    education_level: Optional[str] = None
    application_deadline: Optional[datetime] = None
    is_featured: Optional[bool] = None
    is_urgent: Optional[bool] = None
    auto_publish: Optional[bool] = None
    scheduled_publish_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    workflow_notes: Optional[str] = None
    admin_priority: Optional[int] = None
    requires_review: Optional[bool] = None

# Job Post Status Update Schema
class JobPostStatusUpdate(BaseModel):
    status: JobStatus

# Job Workflow Action Schemas
class JobWorkflowAction(BaseModel):
    action: JobAction
    reason: Optional[str] = None
    notes: Optional[str] = None

class JobApprovalAction(BaseModel):
    action: JobAction = JobAction.APPROVE
    notes: Optional[str] = None
    publish_immediately: bool = False

class JobRejectionAction(BaseModel):
    action: JobAction = JobAction.REJECT
    rejection_reason: RejectionReason
    notes: Optional[str] = None

class JobPublishAction(BaseModel):
    action: JobAction = JobAction.PUBLISH
    priority: Optional[JobPriority] = JobPriority.NORMAL
    is_featured: bool = False
    is_urgent: bool = False

class JobFlagAction(BaseModel):
    action: JobAction = JobAction.FLAG
    reason: str
    notes: Optional[str] = None

# Job Workflow Log Schema
class JobWorkflowLogSchema(BaseModel):
    id: int
    job_post_id: str
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    performed_by: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: datetime

# Job Post Response Schema
class JobPost(JobPostBase):
    id: str  # UUID string
    employer_id: str  # UUID string
    employer_number: Optional[str] = None  # RH00 series number
    status: JobStatus
    priority: Optional[str] = "normal"
    workflow_stage: Optional[str] = "draft"
    auto_publish: bool = False
    scheduled_publish_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    last_workflow_action: Optional[str] = None
    workflow_notes: Optional[str] = None
    admin_priority: int = 0
    requires_review: bool = False
    review_completed_at: Optional[datetime] = None
    review_completed_by: Optional[str] = None
    
    # Approval Workflow
    submitted_for_approval_at: Optional[datetime] = None
    submitted_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejection_notes: Optional[str] = None
    
    # Publishing Workflow
    published_at: Optional[datetime] = None
    published_by: Optional[str] = None
    unpublished_at: Optional[datetime] = None
    unpublished_by: Optional[str] = None
    
    # Job Features
    is_featured: bool = False
    is_urgent: bool = False
    is_flagged: bool = False
    flagged_at: Optional[datetime] = None
    flagged_by: Optional[str] = None
    flagged_reason: Optional[str] = None
    
    # Analytics
    views_count: int
    applications_count: int
    
    # External Integration
    external_id: Optional[str] = None
    external_source: Optional[str] = None
    external_url: Optional[str] = None
    
    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Job Post with Employer Info
class JobPostWithEmployer(JobPost):
    employer: dict  # Will be populated with employer info

# Job Post List Response
class JobPostList(BaseModel):
    jobs: List[JobPost]
    total: int
    page: int
    per_page: int
    pages: int

# Job Post Search Schema
class JobPostSearch(BaseModel):
    query: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[JobType] = None
    work_location: Optional[WorkLocation] = None
    experience_level: Optional[ExperienceLevel] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    skills: Optional[List[str]] = None
    remote_only: bool = False
    page: int = 1
    per_page: int = 20

# Job Post Statistics Schema
class JobPostStats(BaseModel):
    total_jobs: int
    active_jobs: int
    draft_jobs: int
    closed_jobs: int
    featured_jobs: int
    remote_jobs: int
    jobs_this_month: int
    avg_applications_per_job: float