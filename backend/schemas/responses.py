#!/usr/bin/env python3
"""
Response Schemas for RemoteHive API
Provides standardized response models with comprehensive metadata
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Dict, Any, List, Optional, Union, Generic, TypeVar
from datetime import datetime
from enum import Enum

from backend.schemas.base import BaseSchema, APIVersion, ResponseStatus

# Generic type for data payload
T = TypeVar('T')


class ResponseMetadata(BaseModel):
    """Metadata for API responses"""
    request_id: Optional[str] = Field(None, description="Unique request identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    api_version: APIVersion = Field(APIVersion.V2, description="API version")
    processing_time_ms: Optional[int] = Field(None, description="Request processing time in milliseconds")
    server_id: Optional[str] = Field(None, description="Server instance identifier")
    rate_limit: Optional[Dict[str, Any]] = Field(None, description="Rate limiting information")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "request_id": "req_123456789",
            "timestamp": "2024-01-20T10:30:00Z",
            "api_version": "v2",
            "processing_time_ms": 150,
            "server_id": "srv_001",
            "rate_limit": {
                "limit": 1000,
                "remaining": 995,
                "reset_time": "2024-01-20T11:00:00Z"
            }
        }
    })


class PaginationMetadata(BaseModel):
    """Pagination metadata for list responses"""
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Number of items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")
    next_page: Optional[int] = Field(None, description="Next page number")
    previous_page: Optional[int] = Field(None, description="Previous page number")
    
    @field_validator('total_pages')
    @classmethod
    def calculate_total_pages(cls, v, values):
        size = values.get('size', 1)
        total_items = values.get('total_items', 0)
        return max(1, (total_items + size - 1) // size)
    
    @field_validator('has_next')
    @classmethod
    def calculate_has_next(cls, v, values):
        page = values.get('page', 1)
        total_pages = values.get('total_pages', 1)
        return page < total_pages
    
    @field_validator('has_previous')
    @classmethod
    def calculate_has_previous(cls, v, values):
        page = values.get('page', 1)
        return page > 1
    
    @field_validator('next_page')
    @classmethod
    def calculate_next_page(cls, v, values):
        page = values.get('page', 1)
        has_next = values.get('has_next', False)
        return page + 1 if has_next else None
    
    @field_validator('previous_page')
    @classmethod
    def calculate_previous_page(cls, v, values):
        page = values.get('page', 1)
        has_previous = values.get('has_previous', False)
        return page - 1 if has_previous else None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "page": 2,
            "size": 20,
            "total_items": 150,
            "total_pages": 8,
            "has_next": True,
            "has_previous": True,
            "next_page": 3,
            "previous_page": 1
        }
    })


class BaseResponse(BaseSchema, Generic[T]):
    """Base response model with common fields"""
    success: bool = Field(True, description="Whether the request was successful")
    status: ResponseStatus = Field(ResponseStatus.SUCCESS, description="Response status")
    message: Optional[str] = Field(None, description="Response message")
    data: Optional[T] = Field(None, description="Response data payload")
    metadata: Optional[ResponseMetadata] = Field(None, description="Response metadata")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "success",
            "message": "Operation completed successfully",
            "data": {},
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2",
                "processing_time_ms": 150
            }
        }
    })


class ListResponse(BaseResponse[List[T]]):
    """Response model for list operations"""
    data: List[T] = Field(default_factory=list, description="List of items")
    pagination: Optional[PaginationMetadata] = Field(None, description="Pagination metadata")
    filters_applied: Optional[Dict[str, Any]] = Field(None, description="Filters that were applied")
    sort_applied: Optional[List[Dict[str, str]]] = Field(None, description="Sort conditions that were applied")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "success",
            "message": "Items retrieved successfully",
            "data": [],
            "pagination": {
                "page": 1,
                "size": 20,
                "total_items": 100,
                "total_pages": 5,
                "has_next": True,
                "has_previous": False
            },
            "filters_applied": {
                "status": "active",
                "created_after": "2024-01-01"
            },
            "sort_applied": [
                {"field": "created_at", "order": "desc"}
            ],
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2"
            }
        }
    })


class CreatedResponse(BaseResponse[T]):
    """Response model for resource creation"""
    status: ResponseStatus = Field(ResponseStatus.CREATED, description="Created status")
    message: str = Field("Resource created successfully", description="Success message")
    resource_id: Optional[str] = Field(None, description="ID of the created resource")
    resource_url: Optional[str] = Field(None, description="URL to access the created resource")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "created",
            "message": "Resource created successfully",
            "data": {},
            "resource_id": "res_123456789",
            "resource_url": "/api/v1/resources/res_123456789",
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2"
            }
        }
    })


class UpdatedResponse(BaseResponse[T]):
    """Response model for resource updates"""
    message: str = Field("Resource updated successfully", description="Success message")
    changes_made: Optional[List[str]] = Field(None, description="List of fields that were changed")
    previous_version: Optional[str] = Field(None, description="Previous version identifier")
    current_version: Optional[str] = Field(None, description="Current version identifier")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "success",
            "message": "Resource updated successfully",
            "data": {},
            "changes_made": ["title", "description", "updated_at"],
            "previous_version": "v1.0",
            "current_version": "v1.1",
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2"
            }
        }
    })


class DeletedResponse(BaseResponse[None]):
    """Response model for resource deletion"""
    data: None = Field(None, description="No data for deletion response")
    message: str = Field("Resource deleted successfully", description="Success message")
    deleted_id: Optional[str] = Field(None, description="ID of the deleted resource")
    soft_delete: bool = Field(False, description="Whether this was a soft delete")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "success",
            "message": "Resource deleted successfully",
            "data": None,
            "deleted_id": "res_123456789",
            "soft_delete": True,
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2"
            }
        }
    })


class BulkOperationResult(BaseModel):
    """Result for a single item in a bulk operation"""
    index: int = Field(..., description="Index of the item in the original request")
    success: bool = Field(..., description="Whether the operation succeeded for this item")
    item_id: Optional[str] = Field(None, description="ID of the processed item")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    error_code: Optional[str] = Field(None, description="Error code if operation failed")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "index": 0,
            "success": True,
            "item_id": "item_123456789",
            "error": None,
            "error_code": None
        }
    })


class BulkOperationResponse(BaseResponse[List[BulkOperationResult]]):
    """Response model for bulk operations"""
    data: List[BulkOperationResult] = Field(..., description="Results for each item")
    total_items: int = Field(..., description="Total number of items processed")
    successful_items: int = Field(..., description="Number of successfully processed items")
    failed_items: int = Field(..., description="Number of failed items")
    processing_time_ms: Optional[int] = Field(None, description="Total processing time")
    
    @field_validator('successful_items')
    @classmethod
    def calculate_successful_items(cls, v, values):
        data = values.get('data', [])
        return sum(1 for result in data if result.success)
    
    @field_validator('failed_items')
    @classmethod
    def calculate_failed_items(cls, v, values):
        data = values.get('data', [])
        return sum(1 for result in data if not result.success)
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "success",
            "message": "Bulk operation completed",
            "data": [
                {
                    "index": 0,
                    "success": True,
                    "item_id": "item_123",
                    "error": None,
                    "error_code": None
                },
                {
                    "index": 1,
                    "success": False,
                    "item_id": None,
                    "error": "Validation failed",
                    "error_code": "VALIDATION_ERROR"
                }
            ],
            "total_items": 2,
            "successful_items": 1,
            "failed_items": 1,
            "processing_time_ms": 500,
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2"
            }
        }
    })


class FileUploadResponse(BaseResponse[Dict[str, Any]]):
    """Response model for file uploads"""
    data: Dict[str, Any] = Field(..., description="File upload details")
    file_id: str = Field(..., description="Unique file identifier")
    file_url: Optional[str] = Field(None, description="URL to access the uploaded file")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME type of the uploaded file")
    checksum: Optional[str] = Field(None, description="File checksum for integrity verification")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "success",
            "message": "File uploaded successfully",
            "data": {
                "filename": "resume.pdf",
                "original_name": "john_doe_resume.pdf",
                "upload_date": "2024-01-20T10:30:00Z"
            },
            "file_id": "file_123456789",
            "file_url": "/api/v1/files/file_123456789",
            "file_size": 1024000,
            "content_type": "application/pdf",
            "checksum": "sha256:abc123def456",
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2"
            }
        }
    })


class ExportResponse(BaseResponse[Dict[str, Any]]):
    """Response model for data exports"""
    data: Dict[str, Any] = Field(..., description="Export details")
    export_id: str = Field(..., description="Unique export identifier")
    download_url: str = Field(..., description="URL to download the export file")
    expires_at: datetime = Field(..., description="When the download URL expires")
    file_format: str = Field(..., description="Format of the exported file")
    record_count: int = Field(..., description="Number of records exported")
    file_size: Optional[int] = Field(None, description="Size of the export file in bytes")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "success",
            "message": "Export completed successfully",
            "data": {
                "filters_applied": {"status": "active"},
                "fields_exported": ["id", "title", "description"],
                "export_date": "2024-01-20T10:30:00Z"
            },
            "export_id": "exp_123456789",
            "download_url": "/api/v1/exports/exp_123456789/download",
            "expires_at": "2024-01-21T10:30:00Z",
            "file_format": "csv",
            "record_count": 1500,
            "file_size": 2048000,
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2"
            }
        }
    })


class ImportResponse(BaseResponse[Dict[str, Any]]):
    """Response model for data imports"""
    data: Dict[str, Any] = Field(..., description="Import details")
    import_id: str = Field(..., description="Unique import identifier")
    status: str = Field(..., description="Import status")
    records_processed: int = Field(..., description="Number of records processed")
    records_created: int = Field(..., description="Number of records created")
    records_updated: int = Field(..., description="Number of records updated")
    records_failed: int = Field(..., description="Number of records that failed")
    error_report_url: Optional[str] = Field(None, description="URL to download error report")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "success",
            "message": "Import completed successfully",
            "data": {
                "source_file": "jobs_import.csv",
                "import_date": "2024-01-20T10:30:00Z",
                "mapping_used": {"job_title": "title", "job_desc": "description"}
            },
            "import_id": "imp_123456789",
            "status": "completed",
            "records_processed": 1000,
            "records_created": 950,
            "records_updated": 30,
            "records_failed": 20,
            "error_report_url": "/api/v1/imports/imp_123456789/errors",
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2"
            }
        }
    })


class HealthCheckResponse(BaseResponse[Dict[str, Any]]):
    """Response model for health checks"""
    data: Dict[str, Any] = Field(..., description="Health check details")
    status: str = Field(..., description="Overall health status")
    checks: Dict[str, Dict[str, Any]] = Field(..., description="Individual component checks")
    uptime: int = Field(..., description="System uptime in seconds")
    version: str = Field(..., description="Application version")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "healthy",
            "message": "All systems operational",
            "data": {
                "environment": "production",
                "region": "us-east-1",
                "instance_id": "i-1234567890abcdef0"
            },
            "checks": {
                "database": {
                    "status": "healthy",
                    "response_time_ms": 15,
                    "last_check": "2024-01-20T10:30:00Z"
                },
                "redis": {
                    "status": "healthy",
                    "response_time_ms": 5,
                    "last_check": "2024-01-20T10:30:00Z"
                },
                "external_api": {
                    "status": "degraded",
                    "response_time_ms": 2000,
                    "last_check": "2024-01-20T10:30:00Z",
                    "error": "High response time"
                }
            },
            "uptime": 86400,
            "version": "2.1.0",
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2"
            }
        }
    })


class MetricsResponse(BaseResponse[Dict[str, Any]]):
    """Response model for system metrics"""
    data: Dict[str, Any] = Field(..., description="Metrics data")
    metrics: Dict[str, Union[int, float, str]] = Field(..., description="Key-value metrics")
    time_range: Dict[str, datetime] = Field(..., description="Time range for the metrics")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "success",
            "message": "Metrics retrieved successfully",
            "data": {
                "collection_time": "2024-01-20T10:30:00Z",
                "granularity": "1h"
            },
            "metrics": {
                "requests_per_second": 150.5,
                "average_response_time_ms": 250,
                "error_rate_percent": 0.5,
                "active_users": 1250,
                "memory_usage_percent": 65.2,
                "cpu_usage_percent": 45.8
            },
            "time_range": {
                "start": "2024-01-20T09:30:00Z",
                "end": "2024-01-20T10:30:00Z"
            },
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2"
            }
        }
    })


class AsyncOperationResponse(BaseResponse[Dict[str, Any]]):
    """Response model for asynchronous operations"""
    data: Dict[str, Any] = Field(..., description="Operation details")
    operation_id: str = Field(..., description="Unique operation identifier")
    status: str = Field(..., description="Operation status")
    progress_percent: Optional[int] = Field(None, ge=0, le=100, description="Operation progress percentage")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    status_url: str = Field(..., description="URL to check operation status")
    result_url: Optional[str] = Field(None, description="URL to get operation result when completed")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "status": "accepted",
            "message": "Operation started successfully",
            "data": {
                "operation_type": "bulk_import",
                "started_at": "2024-01-20T10:30:00Z",
                "parameters": {"file_size": 10485760, "record_count": 5000}
            },
            "operation_id": "op_123456789",
            "status": "running",
            "progress_percent": 25,
            "estimated_completion": "2024-01-20T10:35:00Z",
            "status_url": "/api/v1/operations/op_123456789/status",
            "result_url": "/api/v1/operations/op_123456789/result",
            "metadata": {
                "request_id": "req_123456789",
                "timestamp": "2024-01-20T10:30:00Z",
                "api_version": "v2"
            }
        }
    })


# Convenience type aliases for common response patterns
SuccessResponse = BaseResponse[Dict[str, Any]]
ListSuccessResponse = ListResponse[Dict[str, Any]]
CreatedSuccessResponse = CreatedResponse[Dict[str, Any]]
UpdatedSuccessResponse = UpdatedResponse[Dict[str, Any]]