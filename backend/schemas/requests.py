#!/usr/bin/env python3
"""
Request Schemas for RemoteHive API
Provides standardized request models with comprehensive validation
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, computed_field
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date
from enum import Enum
import re

from backend.schemas.base import BaseSchema, ValidationPatterns


class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"


class FilterOperator(str, Enum):
    """Filter operators for advanced filtering"""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    BETWEEN = "between"
    REGEX = "regex"


class DateRange(BaseModel):
    """Date range for filtering"""
    start_date: Optional[date] = Field(None, description="Start date (inclusive)")
    end_date: Optional[date] = Field(None, description="End date (inclusive)")
    
    @model_validator(mode='before')
    @classmethod
    def validate_date_range(cls, values):
        start_date = values.get('start_date')
        end_date = values.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValueError('start_date must be before or equal to end_date')
        
        return values
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }
    })


class FilterCondition(BaseModel):
    """Individual filter condition"""
    field: str = Field(..., description="Field name to filter on")
    operator: FilterOperator = Field(..., description="Filter operator")
    value: Optional[Union[str, int, float, bool, List[Any]]] = Field(None, description="Filter value")
    case_sensitive: bool = Field(False, description="Whether string comparisons are case sensitive")
    
    @field_validator('field')
    @classmethod
    def validate_field(cls, v):
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', v):
            raise ValueError('Field name must be a valid identifier')
        return v
    
    @model_validator(mode='before')
    @classmethod
    def validate_condition(cls, values):
        operator = values.get('operator')
        value = values.get('value')
        
        # Operators that don't require a value
        no_value_operators = {FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL}
        
        if operator in no_value_operators and value is not None:
            raise ValueError(f'Operator {operator} should not have a value')
        
        if operator not in no_value_operators and value is None:
            raise ValueError(f'Operator {operator} requires a value')
        
        # Validate list operators
        list_operators = {FilterOperator.IN, FilterOperator.NOT_IN}
        if operator in list_operators and not isinstance(value, list):
            raise ValueError(f'Operator {operator} requires a list value')
        
        # Validate between operator
        if operator == FilterOperator.BETWEEN:
            if not isinstance(value, list) or len(value) != 2:
                raise ValueError('BETWEEN operator requires a list with exactly 2 values')
        
        return values
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "field": "salary",
            "operator": "gte",
            "value": 50000,
            "case_sensitive": False
        }
    })


class SortCondition(BaseModel):
    """Individual sort condition"""
    field: str = Field(..., description="Field name to sort by")
    order: SortOrder = Field(SortOrder.ASC, description="Sort order")
    nulls_first: bool = Field(False, description="Whether null values should appear first")
    
    @field_validator('field')
    @classmethod
    def validate_field(cls, v):
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', v):
            raise ValueError('Field name must be a valid identifier')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "field": "created_at",
            "order": "desc",
            "nulls_first": False
        }
    })


class PaginationRequest(BaseModel):
    """Pagination parameters for list requests"""
    page: int = Field(1, ge=1, le=10000, description="Page number (1-based)")
    size: int = Field(20, ge=1, le=1000, description="Number of items per page")
    
    @computed_field
    @property
    def offset(self) -> int:
        """Calculate offset for database queries"""
        return (self.page - 1) * self.size
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "page": 1,
            "size": 20
        }
    })


class SearchRequest(BaseSchema):
    """Base search request with filtering, sorting, and pagination"""
    query: Optional[str] = Field(None, max_length=500, description="Search query string")
    filters: Optional[List[FilterCondition]] = Field(None, description="Filter conditions")
    sort: Optional[List[SortCondition]] = Field(None, description="Sort conditions")
    pagination: PaginationRequest = Field(default_factory=PaginationRequest, description="Pagination parameters")
    include_deleted: bool = Field(False, description="Whether to include soft-deleted records")
    include_metadata: bool = Field(False, description="Whether to include metadata in response")
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        if v is not None:
            # Basic XSS protection
            if re.search(r'<[^>]*script[^>]*>', v, re.IGNORECASE):
                raise ValueError('Query contains potentially malicious content')
            # Remove excessive whitespace
            v = re.sub(r'\s+', ' ', v.strip())
        return v
    
    @field_validator('filters')
    @classmethod
    def validate_filters(cls, v):
        if v is not None and len(v) > 50:
            raise ValueError('Maximum 50 filter conditions allowed')
        return v
    
    @field_validator('sort')
    @classmethod
    def validate_sort(cls, v):
        if v is not None and len(v) > 10:
            raise ValueError('Maximum 10 sort conditions allowed')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query": "remote developer",
            "filters": [
                {
                    "field": "salary",
                    "operator": "gte",
                    "value": 50000
                },
                {
                    "field": "location",
                    "operator": "contains",
                    "value": "remote",
                    "case_sensitive": False
                }
            ],
            "sort": [
                {
                    "field": "created_at",
                    "order": "desc"
                }
            ],
            "pagination": {
                "page": 1,
                "size": 20
            },
            "include_deleted": False,
            "include_metadata": True
        }
    })


class BulkOperationRequest(BaseSchema):
    """Base bulk operation request"""
    operation: str = Field(..., description="Type of bulk operation")
    items: List[Dict[str, Any]] = Field(..., min_length=1, max_length=1000, description="Items to process")
    validate_all: bool = Field(True, description="Whether to validate all items before processing")
    stop_on_error: bool = Field(True, description="Whether to stop processing on first error")
    batch_size: int = Field(100, ge=1, le=1000, description="Number of items to process in each batch")
    
    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        allowed_operations = {'create', 'update', 'delete', 'upsert', 'import', 'export'}
        if v not in allowed_operations:
            raise ValueError(f'Operation must be one of: {", ".join(allowed_operations)}')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "operation": "create",
            "items": [
                {"title": "Job 1", "description": "Description 1"},
                {"title": "Job 2", "description": "Description 2"}
            ],
            "validate_all": True,
            "stop_on_error": True,
            "batch_size": 100
        }
    })


class FileUploadRequest(BaseSchema):
    """File upload request metadata"""
    filename: str = Field(..., max_length=255, description="Original filename")
    content_type: str = Field(..., description="MIME type of the file")
    size: int = Field(..., ge=1, le=100_000_000, description="File size in bytes")
    checksum: Optional[str] = Field(None, description="File checksum for integrity verification")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional file metadata")
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        # Security: prevent path traversal
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Filename contains invalid characters')
        
        # Check for allowed extensions (example)
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.txt', '.csv', '.xlsx'}
        if not any(v.lower().endswith(ext) for ext in allowed_extensions):
            raise ValueError('File type not allowed')
        
        return v
    
    @field_validator('content_type')
    @classmethod
    def validate_content_type(cls, v):
        allowed_types = {
            'image/jpeg', 'image/png', 'image/gif',
            'application/pdf', 'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain', 'text/csv',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        if v not in allowed_types:
            raise ValueError('Content type not allowed')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "filename": "resume.pdf",
            "content_type": "application/pdf",
            "size": 1024000,
            "checksum": "sha256:abc123def456",
            "metadata": {
                "description": "User resume",
                "category": "document"
            }
        }
    })


class ExportRequest(BaseSchema):
    """Data export request"""
    format: str = Field(..., description="Export format")
    filters: Optional[List[FilterCondition]] = Field(None, description="Filter conditions for export")
    fields: Optional[List[str]] = Field(None, description="Specific fields to export")
    include_headers: bool = Field(True, description="Whether to include column headers")
    date_range: Optional[DateRange] = Field(None, description="Date range for export")
    compression: bool = Field(False, description="Whether to compress the export file")
    
    @field_validator('format')
    @classmethod
    def validate_format(cls, v):
        allowed_formats = {'csv', 'xlsx', 'json', 'xml', 'pdf'}
        if v not in allowed_formats:
            raise ValueError(f'Format must be one of: {", ".join(allowed_formats)}')
        return v
    
    @field_validator('fields')
    @classmethod
    def validate_fields(cls, v):
        if v is not None:
            if len(v) > 100:
                raise ValueError('Maximum 100 fields allowed for export')
            for field in v:
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', field):
                    raise ValueError(f'Invalid field name: {field}')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "format": "csv",
            "filters": [
                {
                    "field": "status",
                    "operator": "eq",
                    "value": "active"
                }
            ],
            "fields": ["id", "title", "description", "created_at"],
            "include_headers": True,
            "date_range": {
                "start_date": "2024-01-01",
                "end_date": "2024-12-31"
            },
            "compression": False
        }
    })


class ImportRequest(BaseSchema):
    """Data import request"""
    file_url: str = Field(..., description="URL of the file to import")
    format: str = Field(..., description="Import format")
    mapping: Optional[Dict[str, str]] = Field(None, description="Field mapping from import to system fields")
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="Custom validation rules")
    skip_duplicates: bool = Field(True, description="Whether to skip duplicate records")
    update_existing: bool = Field(False, description="Whether to update existing records")
    batch_size: int = Field(100, ge=1, le=1000, description="Number of records to process in each batch")
    
    @field_validator('file_url')
    @classmethod
    def validate_file_url(cls, v):
        if not re.match(ValidationPatterns.URL, v):
            raise ValueError('Invalid file URL')
        return v
    
    @field_validator('format')
    @classmethod
    def validate_format(cls, v):
        allowed_formats = {'csv', 'xlsx', 'json', 'xml'}
        if v not in allowed_formats:
            raise ValueError(f'Format must be one of: {", ".join(allowed_formats)}')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "file_url": "https://example.com/data.csv",
            "format": "csv",
            "mapping": {
                "job_title": "title",
                "job_desc": "description",
                "company_name": "company"
            },
            "validation_rules": {
                "title": {"required": True, "max_length": 200},
                "description": {"required": True, "min_length": 50}
            },
            "skip_duplicates": True,
            "update_existing": False,
            "batch_size": 100
        }
    })


class WebhookRequest(BaseSchema):
    """Webhook configuration request"""
    url: str = Field(..., description="Webhook URL")
    events: List[str] = Field(..., min_length=1, description="Events to subscribe to")
    secret: Optional[str] = Field(None, min_length=16, max_length=64, description="Webhook secret for signature verification")
    headers: Optional[Dict[str, str]] = Field(None, description="Custom headers to send with webhook")
    timeout: int = Field(30, ge=1, le=300, description="Webhook timeout in seconds")
    retry_count: int = Field(3, ge=0, le=10, description="Number of retry attempts")
    active: bool = Field(True, description="Whether the webhook is active")
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not re.match(ValidationPatterns.URL, v):
            raise ValueError('Invalid webhook URL')
        if not v.startswith('https://'):
            raise ValueError('Webhook URL must use HTTPS')
        return v
    
    @field_validator('events')
    @classmethod
    def validate_events(cls, v):
        allowed_events = {
            'job.created', 'job.updated', 'job.deleted',
            'application.created', 'application.updated', 'application.deleted',
            'user.created', 'user.updated', 'user.deleted',
            'payment.completed', 'payment.failed'
        }
        for event in v:
            if event not in allowed_events:
                raise ValueError(f'Invalid event: {event}')
        return v
    
    @field_validator('headers')
    @classmethod
    def validate_headers(cls, v):
        if v is not None:
            if len(v) > 20:
                raise ValueError('Maximum 20 custom headers allowed')
            for key, value in v.items():
                if not re.match(r'^[a-zA-Z0-9-_]+$', key):
                    raise ValueError(f'Invalid header name: {key}')
                if len(value) > 1000:
                    raise ValueError(f'Header value too long: {key}')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "url": "https://api.example.com/webhooks/remotehive",
            "events": ["job.created", "application.created"],
            "secret": "webhook_secret_key_123",
            "headers": {
                "X-Custom-Header": "custom-value"
            },
            "timeout": 30,
            "retry_count": 3,
            "active": True
        }
    })


class ScheduleRequest(BaseSchema):
    """Task scheduling request"""
    name: str = Field(..., max_length=100, description="Schedule name")
    cron_expression: str = Field(..., description="Cron expression for scheduling")
    task_type: str = Field(..., description="Type of task to schedule")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Task parameters")
    timezone: str = Field("UTC", description="Timezone for the schedule")
    active: bool = Field(True, description="Whether the schedule is active")
    max_retries: int = Field(3, ge=0, le=10, description="Maximum number of retries")
    
    @field_validator('cron_expression')
    @classmethod
    def validate_cron_expression(cls, v):
        # Basic cron validation (5 or 6 fields)
        parts = v.split()
        if len(parts) not in [5, 6]:
            raise ValueError('Cron expression must have 5 or 6 fields')
        return v
    
    @field_validator('task_type')
    @classmethod
    def validate_task_type(cls, v):
        allowed_tasks = {
            'scrape_jobs', 'send_notifications', 'cleanup_data',
            'generate_reports', 'backup_database', 'sync_external_data'
        }
        if v not in allowed_tasks:
            raise ValueError(f'Task type must be one of: {", ".join(allowed_tasks)}')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Daily Job Scraping",
            "cron_expression": "0 2 * * *",
            "task_type": "scrape_jobs",
            "parameters": {
                "source": "indeed",
                "keywords": ["remote", "developer"]
            },
            "timezone": "UTC",
            "active": True,
            "max_retries": 3
        }
    })


class HealthCheckRequest(BaseSchema):
    """Health check request"""
    include_dependencies: bool = Field(False, description="Whether to check external dependencies")
    include_metrics: bool = Field(False, description="Whether to include performance metrics")
    timeout: int = Field(10, ge=1, le=60, description="Timeout for health checks in seconds")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "include_dependencies": True,
            "include_metrics": True,
            "timeout": 10
        }
    })