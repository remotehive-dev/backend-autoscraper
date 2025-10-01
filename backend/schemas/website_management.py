from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class WebsiteStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"

class WebsiteConfig(BaseModel):
    url: str = Field(..., description="Website URL to scrape")
    name: Optional[str] = Field(None, description="Display name for the website")
    scraping_frequency: Optional[int] = Field(24, description="Scraping frequency in hours")
    max_pages: Optional[int] = Field(10, description="Maximum pages to scrape")
    selectors: Optional[Dict[str, str]] = Field(default_factory=dict, description="CSS selectors for data extraction")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Custom headers for requests")
    enabled: bool = Field(True, description="Whether scraping is enabled")
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

class WebsiteUploadResponse(BaseModel):
    upload_id: str
    total_websites: int
    valid_websites: int
    invalid_websites: int
    status: str
    errors: List[Dict[str, Any]]
    created_at: datetime
    processed_websites: List[Dict[str, Any]]

class WebsiteUploadStatus(BaseModel):
    upload_id: str
    status: str
    progress: float
    total_websites: int
    processed_websites: int
    valid_websites: int
    invalid_websites: int
    errors: List[Dict[str, Any]]
    created_at: datetime
    completed_at: Optional[datetime] = None

class WebsiteValidationResult(BaseModel):
    url: str
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    extracted_data: Optional[Dict[str, Any]] = None

class ManagedWebsiteResponse(BaseModel):
    id: int
    url: str
    name: Optional[str]
    status: WebsiteStatus
    last_scraped: Optional[datetime]
    scraping_frequency: int
    max_pages: int
    total_jobs_found: int
    enabled: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class WebsiteCreateRequest(BaseModel):
    url: str
    name: Optional[str] = None
    scraping_frequency: int = Field(24, ge=1, le=168)  # 1 hour to 1 week
    max_pages: int = Field(10, ge=1, le=100)
    selectors: Optional[Dict[str, str]] = None
    headers: Optional[Dict[str, str]] = None
    enabled: bool = True

class WebsiteUpdateRequest(BaseModel):
    name: Optional[str] = None
    scraping_frequency: Optional[int] = Field(None, ge=1, le=168)
    max_pages: Optional[int] = Field(None, ge=1, le=100)
    selectors: Optional[Dict[str, str]] = None
    headers: Optional[Dict[str, str]] = None
    enabled: Optional[bool] = None
    status: Optional[WebsiteStatus] = None