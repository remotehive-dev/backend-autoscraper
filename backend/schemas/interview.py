from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class InterviewType(str, Enum):
    """Interview type enumeration"""
    VIDEO = "video"
    PHONE = "phone"
    IN_PERSON = "in-person"


class InterviewStatus(str, Enum):
    """Interview status enumeration"""
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"


class InterviewBase(BaseModel):
    """Base schema for interview"""
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    scheduled_date: datetime
    duration_minutes: int = Field(default=60, ge=15, le=480)
    interview_type: InterviewType = InterviewType.VIDEO
    meeting_link: Optional[str] = None
    location: Optional[str] = None
    status: InterviewStatus = InterviewStatus.SCHEDULED


class InterviewCreate(InterviewBase):
    """Schema for creating an interview"""
    job_application_id: str = Field(..., description="ID of the job application")
    candidate_id: str = Field(..., description="ID of the candidate")


class InterviewUpdate(BaseModel):
    """Schema for updating an interview"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=15, le=480)
    interview_type: Optional[InterviewType] = None
    meeting_link: Optional[str] = None
    location: Optional[str] = None
    status: Optional[InterviewStatus] = None
    feedback: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)


class InterviewResponse(InterviewBase):
    """Schema for interview response"""
    id: str
    job_application_id: str
    interviewer_id: str
    candidate_id: str
    feedback: Optional[str] = None
    rating: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class InterviewList(BaseModel):
    """Schema for interviews list response"""
    interviews: list[InterviewResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class InterviewStats(BaseModel):
    """Schema for interview statistics"""
    total_interviews: int
    scheduled_interviews: int
    completed_interviews: int
    cancelled_interviews: int
    upcoming_interviews: int
    avg_rating: Optional[float] = None