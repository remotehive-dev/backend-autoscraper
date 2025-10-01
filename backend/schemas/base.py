#!/usr/bin/env python3
"""
Base Schema Classes for RemoteHive API
Provides common patterns, validation, and error handling for all API schemas
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum
import re
import html
from backend.core.exceptions import ValidationError


class APIVersion(str, Enum):
    """API Version enumeration"""
    V1 = "v1"
    V2 = "v2"


class ResponseStatus(str, Enum):
    """Standard response status values"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    PARTIAL = "partial"
    CREATED = "created"


class BaseSchema(BaseModel):
    """Base schema with common configuration and validation"""
    
    model_config = ConfigDict(
        # Enable ORM mode for database models
        from_attributes=True,
        # Validate assignment to prevent invalid data
        validate_assignment=True,
        # Use enum values instead of names
        use_enum_values=True,
        # Allow population by field name or alias
        populate_by_name=True,
        # Strict validation
        str_strip_whitespace=True,
        # Extra fields handling
        extra="forbid"
    )

    @field_validator('*', mode='before')
    @classmethod
    def sanitize_strings(cls, v):
        """Sanitize string inputs to prevent XSS and injection attacks"""
        if isinstance(v, str):
            # HTML escape
            v = html.escape(v)
            # Remove null bytes
            v = v.replace('\x00', '')
            # Strip whitespace
            v = v.strip()
            # Limit length
            if len(v) > 10000:
                raise ValueError("String too long")
        return v


class TimestampMixin(BaseModel):
    """Mixin for models with timestamp fields"""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PaginationMixin(BaseModel):
    """Mixin for paginated responses"""
    page: int = Field(1, ge=1, description="Page number (1-based)")
    per_page: int = Field(20, ge=1, le=100, description="Items per page (max 100)")
    total: int = Field(0, ge=0, description="Total number of items")
    pages: int = Field(0, ge=0, description="Total number of pages")


class APIResponse(BaseSchema):
    """Standard API response wrapper"""
    status: ResponseStatus = ResponseStatus.SUCCESS
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[Dict[str, Any]]] = None
    meta: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    version: APIVersion = APIVersion.V1


class ErrorResponse(BaseSchema):
    """Standard error response"""
    status: ResponseStatus = ResponseStatus.ERROR
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    field_errors: Optional[List[Dict[str, str]]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    request_id: Optional[str] = None
    version: APIVersion = APIVersion.V1


class ValidationErrorResponse(ErrorResponse):
    """Validation error response with field-specific errors"""
    error_code: str = "VALIDATION_ERROR"
    field_errors: List[Dict[str, str]] = Field(default_factory=list)


class PaginatedResponse(BaseSchema):
    """Paginated response wrapper"""
    status: ResponseStatus = ResponseStatus.SUCCESS
    data: List[Any] = Field(default_factory=list)
    pagination: PaginationMixin
    meta: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    version: APIVersion = APIVersion.V1


class SearchRequest(BaseSchema):
    """Base search request schema"""
    query: Optional[str] = Field(None, max_length=500, description="Search query")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sort_by: Optional[str] = Field(None, max_length=50)
    sort_order: Optional[str] = Field("asc", pattern="^(asc|desc)$")
    page: int = Field(1, ge=1, le=1000)
    per_page: int = Field(20, ge=1, le=100)

    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        if v and len(v.strip()) < 2:
            raise ValueError("Search query must be at least 2 characters")
        return v


class BulkOperationRequest(BaseSchema):
    """Base bulk operation request"""
    operation: str = Field(..., max_length=50)
    items: List[Dict[str, Any]] = Field(..., min_length=1, max_length=1000)
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator('items')
    @classmethod
    def validate_items(cls, v):
        if len(v) > 1000:
            raise ValueError("Bulk operations limited to 1000 items")
        return v


class BulkOperationResponse(BaseSchema):
    """Base bulk operation response"""
    status: ResponseStatus
    total_items: int
    successful_items: int
    failed_items: int
    results: List[Dict[str, Any]] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class HealthCheckResponse(BaseSchema):
    """Health check response"""
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str = Field(..., description="API version")
    services: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    uptime: Optional[float] = Field(None, description="Uptime in seconds")
    environment: Optional[str] = Field(None, description="Environment name")


class MetricsResponse(BaseSchema):
    """Metrics response"""
    metrics: Dict[str, Union[int, float, str]] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    period: Optional[str] = Field(None, description="Time period for metrics")


# Common validation patterns
class ValidationPatterns:
    """Common regex patterns for validation"""
    
    # Email pattern (basic)
    EMAIL = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    # Phone patterns
    PHONE_US = r'^\+?1?[2-9]\d{2}[2-9]\d{2}\d{4}$'
    PHONE_INTERNATIONAL = r'^\+?[1-9]\d{1,14}$'
    
    # URL pattern
    URL = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?$'
    
    # UUID pattern
    UUID = r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    
    # Alphanumeric with spaces
    ALPHANUMERIC_SPACES = r'^[a-zA-Z0-9\s]+$'
    
    # Safe text (letters, numbers, spaces, basic punctuation)
    SAFE_TEXT = r'^[a-zA-Z0-9\s.,!?\-_()]+$'
    
    # Slug pattern
    SLUG = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'


# Common field validators
def validate_password_strength(password: str) -> str:
    """Validate password strength"""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    
    if not re.search(r'[A-Z]', password):
        raise ValueError("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        raise ValueError("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        raise ValueError("Password must contain at least one digit")
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValueError("Password must contain at least one special character")
    
    return password


def validate_phone_number(phone: str) -> str:
    """Validate phone number format"""
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    if not re.match(ValidationPatterns.PHONE_INTERNATIONAL, cleaned):
        raise ValueError("Invalid phone number format")
    
    return cleaned


def validate_url(url: str) -> str:
    """Validate URL format"""
    if not re.match(ValidationPatterns.URL, url):
        raise ValueError("Invalid URL format")
    return url


def validate_slug(slug: str) -> str:
    """Validate slug format"""
    if not re.match(ValidationPatterns.SLUG, slug):
        raise ValueError("Invalid slug format. Use lowercase letters, numbers, and hyphens only")
    return slug