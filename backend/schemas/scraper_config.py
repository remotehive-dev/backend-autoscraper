from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from backend.core.enums import ScraperSource

class ScheduleInterval(str, Enum):
    """Enum for schedule intervals"""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class ScraperConfigBase(BaseModel):
    """Base schema for scraper configuration"""
    scraper_name: str = Field(..., min_length=1, max_length=255, description="Configuration name")
    source: ScraperSource = Field(..., description="Scraper source platform")
    base_url: str = Field(..., description="Base URL for scraping")
    search_queries: Optional[List[str]] = Field(default=[], description="List of search queries")
    max_pages: int = Field(default=10, ge=1, le=100, description="Maximum pages to scrape")
    delay_between_requests: float = Field(default=1.0, ge=0.1, le=10.0, description="Delay between requests in seconds")
    is_active: bool = Field(default=True, description="Whether the configuration is active")
    ml_parsing_enabled: bool = Field(default=False, description="Enable ML parsing")
    auto_apply_enabled: bool = Field(default=False, description="Enable auto-apply feature")
    schedule_enabled: bool = Field(default=False, description="Enable scheduled scraping")
    schedule_interval: Optional[ScheduleInterval] = Field(default=None, description="Schedule interval")
    
    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('Base URL must start with http:// or https://')
        return v
    
    @field_validator('schedule_interval')
    @classmethod
    def validate_schedule_interval(cls, v, info):
        if hasattr(info, 'data') and info.data.get('schedule_enabled') and not v:
            raise ValueError('Schedule interval is required when schedule is enabled')
        return v

class ScraperConfigCreate(ScraperConfigBase):
    """Schema for creating a new scraper configuration"""
    pass

class ScraperConfigUpdate(BaseModel):
    """Schema for updating a scraper configuration"""
    scraper_name: Optional[str] = Field(None, min_length=1, max_length=255)
    source: Optional[ScraperSource] = None
    base_url: Optional[str] = None
    search_queries: Optional[List[str]] = None
    max_pages: Optional[int] = Field(None, ge=1, le=100)
    delay_between_requests: Optional[float] = Field(None, ge=0.1, le=10.0)
    is_active: Optional[bool] = None
    ml_parsing_enabled: Optional[bool] = None
    auto_apply_enabled: Optional[bool] = None
    schedule_enabled: Optional[bool] = None
    schedule_interval: Optional[ScheduleInterval] = None
    
    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('Base URL must start with http:// or https://')
        return v

class ScraperConfigResponse(ScraperConfigBase):
    """Schema for scraper configuration response"""
    id: int
    user_id: int
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ScraperConfigListResponse(BaseModel):
    """Schema for paginated scraper configuration list response"""
    configs: List[ScraperConfigResponse]
    total: int
    skip: int
    limit: int
    
class ScraperConfigStats(BaseModel):
    """Schema for scraper configuration statistics"""
    id: int
    scraper_name: str
    is_active: bool
    last_run_at: Optional[datetime] = None
    created_at: datetime
    total_runs: int = 0
    success_rate: float = 0.0
    avg_jobs_per_run: float = 0.0
    
class BulkScraperConfigCreate(BaseModel):
    """Schema for creating multiple scraper configurations"""
    configs: List[ScraperConfigCreate] = Field(..., min_items=1, max_items=50)
    
class BulkScraperConfigResponse(BaseModel):
    """Schema for bulk scraper configuration creation response"""
    created: List[ScraperConfigResponse]
    failed: List[Dict[str, Any]] = []
    total_created: int
    total_failed: int
    
class ScraperConfigSearch(BaseModel):
    """Schema for scraper configuration search"""
    query: str = Field(..., min_length=1, description="Search query")
    user_id: Optional[int] = None
    is_active: Optional[bool] = None
    
class ScraperConfigFilter(BaseModel):
    """Schema for filtering scraper configurations"""
    user_id: Optional[int] = None
    is_active: Optional[bool] = None
    schedule_enabled: Optional[bool] = None
    ml_parsing_enabled: Optional[bool] = None
    auto_apply_enabled: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    last_run_after: Optional[datetime] = None
    last_run_before: Optional[datetime] = None