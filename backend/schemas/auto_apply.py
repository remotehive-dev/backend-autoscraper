from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AutoApplySettingsBase(BaseModel):
    """Base schema for auto-apply settings"""
    is_enabled: bool = False
    max_applications_per_day: int = Field(default=5, ge=1, le=50)
    preferred_job_types: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    min_salary: Optional[int] = Field(None, ge=0)
    max_salary: Optional[int] = Field(None, ge=0)
    salary_currency: str = Field(default="USD", max_length=10)
    keywords_include: Optional[List[str]] = None
    keywords_exclude: Optional[List[str]] = None
    company_size_preference: Optional[str] = None
    remote_only: bool = False
    cover_letter_template: Optional[str] = None


class AutoApplySettingsCreate(AutoApplySettingsBase):
    """Schema for creating auto-apply settings"""
    pass


class AutoApplySettingsUpdate(BaseModel):
    """Schema for updating auto-apply settings"""
    is_enabled: Optional[bool] = None
    max_applications_per_day: Optional[int] = Field(None, ge=1, le=50)
    preferred_job_types: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    min_salary: Optional[int] = Field(None, ge=0)
    max_salary: Optional[int] = Field(None, ge=0)
    salary_currency: Optional[str] = Field(None, max_length=10)
    keywords_include: Optional[List[str]] = None
    keywords_exclude: Optional[List[str]] = None
    company_size_preference: Optional[str] = None
    remote_only: Optional[bool] = None
    cover_letter_template: Optional[str] = None


class AutoApplySettingsResponse(AutoApplySettingsBase):
    """Schema for auto-apply settings response"""
    id: int
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AutoApplyStats(BaseModel):
    """Schema for auto-apply statistics"""
    total_auto_applications: int
    applications_today: int
    applications_this_week: int
    applications_this_month: int
    success_rate: float
    avg_applications_per_day: float
    remaining_applications_today: int