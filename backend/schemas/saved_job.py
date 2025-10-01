from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from backend.schemas.job_post import JobPost


class SavedJobBase(BaseModel):
    """Base schema for saved job"""
    notes: Optional[str] = None


class SavedJobCreate(SavedJobBase):
    """Schema for creating a saved job"""
    job_post_id: str = Field(..., description="ID of the job post to save")


class SavedJobUpdate(BaseModel):
    """Schema for updating a saved job"""
    notes: Optional[str] = None


class SavedJobResponse(SavedJobBase):
    """Schema for saved job response"""
    id: int
    user_id: str
    job_post_id: str
    job_post: Optional[JobPost] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class SavedJobList(BaseModel):
    """Schema for saved jobs list response"""
    saved_jobs: list[SavedJobResponse]
    total: int
    page: int
    per_page: int
    total_pages: int