from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from backend.core.enums import ExperienceLevel, EmploymentType

# Base Job Seeker Schema
class JobSeekerBase(BaseModel):
    current_title: Optional[str] = None
    experience_level: Optional[str] = None  # Changed from ExperienceLevel to str to match MongoDB
    years_of_experience: Optional[int] = None
    skills: Optional[List[str]] = None
    preferred_job_types: Optional[List[str]] = None  # Changed from List[EmploymentType] to List[str]
    preferred_locations: Optional[List[str]] = None
    remote_work_preference: bool = True
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    salary_currency: str = "USD"
    resume_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None  # Added field from MongoDB model
    github_url: Optional[str] = None  # Added field from MongoDB model
    bio: Optional[str] = None  # Added field from MongoDB model
    salary_expectation_min: Optional[int] = None  # Added field from MongoDB model
    salary_expectation_max: Optional[int] = None  # Added field from MongoDB model
    availability_date: Optional[datetime] = None  # Added field from MongoDB model
    cover_letter_template: Optional[str] = None
    is_actively_looking: bool = True
    available_start_date: Optional[datetime] = None  # Keep this for backward compatibility
    education_level: Optional[str] = None
    field_of_study: Optional[str] = None
    university: Optional[str] = None
    graduation_year: Optional[int] = None

    @validator('years_of_experience')
    def validate_experience(cls, v):
        if v is not None and v < 0:
            raise ValueError('Years of experience must be non-negative')
        return v

    @validator('graduation_year')
    def validate_graduation_year(cls, v):
        if v is not None:
            current_year = datetime.now().year
            if v < 1950 or v > current_year + 10:
                raise ValueError('Invalid graduation year')
        return v

# Job Seeker Create Schema
class JobSeekerCreate(JobSeekerBase):
    pass

# Job Seeker Update Schema
class JobSeekerUpdate(BaseModel):
    current_title: Optional[str] = None
    experience_level: Optional[str] = None  # Changed from ExperienceLevel to str
    years_of_experience: Optional[int] = None
    skills: Optional[List[str]] = None
    preferred_job_types: Optional[List[str]] = None  # Changed from List[EmploymentType] to List[str]
    preferred_locations: Optional[List[str]] = None
    remote_work_preference: Optional[bool] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    salary_currency: Optional[str] = None
    resume_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None  # Added field from MongoDB model
    github_url: Optional[str] = None  # Added field from MongoDB model
    bio: Optional[str] = None  # Added field from MongoDB model
    salary_expectation_min: Optional[int] = None  # Added field from MongoDB model
    salary_expectation_max: Optional[int] = None  # Added field from MongoDB model
    availability_date: Optional[datetime] = None  # Added field from MongoDB model
    cover_letter_template: Optional[str] = None
    is_actively_looking: Optional[bool] = None
    available_start_date: Optional[datetime] = None
    education_level: Optional[str] = None
    field_of_study: Optional[str] = None
    university: Optional[str] = None
    graduation_year: Optional[int] = None

# Job Seeker Response Schema
class JobSeeker(JobSeekerBase):
    id: str  # Changed from int to str for MongoDB ObjectId
    user_id: str  # Changed from int to str for MongoDB ObjectId
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Job Seeker Profile Schema (with user info)
class JobSeekerProfile(JobSeeker):
    user: dict  # Will be populated with user info

# Job Seeker List Response
class JobSeekerList(BaseModel):
    job_seekers: List[JobSeeker]
    total: int
    page: int
    per_page: int
    pages: int

# Job Seeker Statistics Schema
class JobSeekerStats(BaseModel):
    total_job_seekers: int
    active_job_seekers: int
    new_job_seekers_this_month: int
    avg_applications_per_seeker: float
    top_skills: List[dict]
    experience_level_distribution: dict

# Job Seeker Dashboard Statistics Schema
class JobSeekerDashboardStats(BaseModel):
    applications_sent: int
    saved_jobs: int
    profile_views: int
    interview_requests: int
    response_rate: float
    last_activity: Optional[datetime] = None

# Job Recommendation Schema
class JobRecommendation(BaseModel):
    job_id: str
    title: str
    company: str
    location: Optional[str] = None
    salary_range: Optional[str] = None
    match_score: float
    match_reasons: List[str]
    posted_date: Optional[datetime] = None
    employment_type: Optional[str] = None
    remote_option: Optional[bool] = None

# Profile Strength Schema
class ProfileStrength(BaseModel):
    overall_score: int
    completeness_percentage: float
    strengths: List[str]
    improvement_suggestions: List[str]
    missing_sections: List[str]