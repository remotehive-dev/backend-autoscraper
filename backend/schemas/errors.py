#!/usr/bin/env python3
"""
Error Schemas for RemoteHive API
Provides standardized error response models and validation error handling
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum

from backend.schemas.base import BaseSchema, APIVersion


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for better classification"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    BUSINESS_LOGIC = "business_logic"
    EXTERNAL_SERVICE = "external_service"
    DATABASE = "database"
    NETWORK = "network"
    SYSTEM = "system"
    RATE_LIMIT = "rate_limit"
    SECURITY = "security"
    CONFIGURATION = "configuration"
    FILE_OPERATION = "file_operation"
    SCRAPING = "scraping"
    TASK_MANAGEMENT = "task_management"


class FieldError(BaseModel):
    """Individual field validation error"""
    field: str = Field(..., description="Field name that caused the error")
    message: str = Field(..., description="Error message for the field")
    code: Optional[str] = Field(None, description="Specific error code for the field")
    value: Optional[Any] = Field(None, description="Invalid value that caused the error")
    constraint: Optional[str] = Field(None, description="Validation constraint that was violated")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "field": "email",
            "message": "Invalid email format",
            "code": "INVALID_EMAIL",
            "value": "invalid-email",
            "constraint": "email_format"
        }
    })


class ErrorContext(BaseModel):
    """Additional context information for errors"""
    request_id: Optional[str] = Field(None, description="Unique request identifier")
    user_id: Optional[str] = Field(None, description="User ID associated with the request")
    endpoint: Optional[str] = Field(None, description="API endpoint that generated the error")
    method: Optional[str] = Field(None, description="HTTP method used")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for distributed tracing")
    session_id: Optional[str] = Field(None, description="Session identifier")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "request_id": "req_123456789",
            "user_id": "user_987654321",
            "endpoint": "/api/v1/jobs",
            "method": "POST",
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0...",
            "correlation_id": "corr_abc123def456",
            "session_id": "sess_xyz789uvw456"
        }
    })


class BaseErrorResponse(BaseSchema):
    """Base error response model"""
    success: bool = Field(False, description="Always false for error responses")
    error_code: str = Field(..., description="Unique error code identifier")
    message: str = Field(..., description="Human-readable error message")
    category: ErrorCategory = Field(..., description="Error category")
    severity: ErrorSeverity = Field(ErrorSeverity.MEDIUM, description="Error severity level")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error occurrence timestamp")
    api_version: APIVersion = Field(APIVersion.V2, description="API version")
    context: Optional[ErrorContext] = Field(None, description="Additional error context")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    help_url: Optional[str] = Field(None, description="URL to documentation or help")
    
    @field_validator('help_url')
    @classmethod
    def validate_help_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('Help URL must be a valid HTTP/HTTPS URL')
        return v
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error_code": "VALIDATION_ERROR",
            "message": "Input validation failed",
            "category": "validation",
            "severity": "medium",
            "timestamp": "2024-01-20T10:30:00Z",
            "api_version": "v2",
            "context": {
                "request_id": "req_123456789",
                "endpoint": "/api/v1/jobs",
                "method": "POST"
            },
            "details": {
                "validation_errors": 3,
                "affected_fields": ["title", "description", "salary"]
            },
            "help_url": "https://docs.remotehive.com/errors/validation"
        }
    })


class ValidationErrorResponse(BaseErrorResponse):
    """Response model for validation errors with detailed field information."""
    error_code: str = Field("VALIDATION_ERROR", description="Validation error code")
    category: ErrorCategory = Field(ErrorCategory.VALIDATION, description="Validation error category")
    field_errors: List[FieldError] = Field(..., description="List of field validation errors")
    total_errors: int = Field(..., description="Total number of validation errors")
    
    # total_errors is calculated in ErrorResponseFactory.create_validation_error
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error_code": "VALIDATION_ERROR",
            "message": "Input validation failed",
            "category": "validation",
            "severity": "medium",
            "timestamp": "2024-01-20T10:30:00Z",
            "api_version": "v2",
            "field_errors": [
                {
                    "field": "email",
                    "message": "Invalid email format",
                    "code": "INVALID_EMAIL",
                    "value": "invalid-email"
                },
                {
                    "field": "password",
                    "message": "Password must be at least 8 characters",
                    "code": "PASSWORD_TOO_SHORT",
                    "constraint": "min_length_8"
                }
            ],
            "total_errors": 2,
            "help_url": "https://docs.remotehive.com/errors/validation"
        }
    })


class AuthenticationErrorResponse(BaseErrorResponse):
    """Authentication error response"""
    error_code: str = Field("AUTHENTICATION_ERROR", description="Authentication error code")
    category: ErrorCategory = Field(ErrorCategory.AUTHENTICATION, description="Authentication error category")
    auth_method: Optional[str] = Field(None, description="Authentication method that failed")
    token_expired: Optional[bool] = Field(None, description="Whether the token has expired")
    login_url: Optional[str] = Field(None, description="URL to login endpoint")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error_code": "TOKEN_EXPIRED",
            "message": "Authentication token has expired",
            "category": "authentication",
            "severity": "medium",
            "timestamp": "2024-01-20T10:30:00Z",
            "api_version": "v2",
            "auth_method": "jwt",
            "token_expired": True,
            "login_url": "/api/v1/auth/login",
            "help_url": "https://docs.remotehive.com/errors/authentication"
        }
    })


class AuthorizationErrorResponse(BaseErrorResponse):
    """Authorization error response"""
    error_code: str = Field("AUTHORIZATION_ERROR", description="Authorization error code")
    category: ErrorCategory = Field(ErrorCategory.AUTHORIZATION, description="Authorization error category")
    required_permissions: Optional[List[str]] = Field(None, description="Required permissions for the operation")
    user_permissions: Optional[List[str]] = Field(None, description="Current user permissions")
    resource_id: Optional[str] = Field(None, description="ID of the resource being accessed")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error_code": "INSUFFICIENT_PERMISSIONS",
            "message": "Insufficient permissions to access this resource",
            "category": "authorization",
            "severity": "medium",
            "timestamp": "2024-01-20T10:30:00Z",
            "api_version": "v2",
            "required_permissions": ["jobs:write", "admin:access"],
            "user_permissions": ["jobs:read", "profile:write"],
            "resource_id": "job_123456789",
            "help_url": "https://docs.remotehive.com/errors/authorization"
        }
    })


class RateLimitErrorResponse(BaseErrorResponse):
    """Rate limit error response"""
    error_code: str = Field("RATE_LIMIT_EXCEEDED", description="Rate limit error code")
    category: ErrorCategory = Field(ErrorCategory.RATE_LIMIT, description="Rate limit error category")
    severity: ErrorSeverity = Field(ErrorSeverity.HIGH, description="Rate limit errors are high severity")
    limit: int = Field(..., description="Rate limit threshold")
    window: int = Field(..., description="Rate limit window in seconds")
    remaining: int = Field(..., description="Remaining requests in current window")
    reset_time: datetime = Field(..., description="When the rate limit resets")
    retry_after: int = Field(..., description="Seconds to wait before retrying")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error_code": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests. Please try again later.",
            "category": "rate_limit",
            "severity": "high",
            "timestamp": "2024-01-20T10:30:00Z",
            "api_version": "v2",
            "limit": 100,
            "window": 60,
            "remaining": 0,
            "reset_time": "2024-01-20T10:31:00Z",
            "retry_after": 60,
            "help_url": "https://docs.remotehive.com/errors/rate-limit"
        }
    })


class BusinessLogicErrorResponse(BaseErrorResponse):
    """Business logic error response"""
    error_code: str = Field(..., description="Business logic error code")
    category: ErrorCategory = Field(ErrorCategory.BUSINESS_LOGIC, description="Business logic error category")
    business_rule: Optional[str] = Field(None, description="Business rule that was violated")
    suggested_action: Optional[str] = Field(None, description="Suggested action to resolve the error")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error_code": "JOB_ALREADY_APPLIED",
            "message": "You have already applied to this job",
            "category": "business_logic",
            "severity": "medium",
            "timestamp": "2024-01-20T10:30:00Z",
            "api_version": "v2",
            "business_rule": "one_application_per_job",
            "suggested_action": "Check your application status or apply to a different job",
            "help_url": "https://docs.remotehive.com/errors/business-logic"
        }
    })


class ExternalServiceErrorResponse(BaseErrorResponse):
    """External service error response"""
    error_code: str = Field(..., description="External service error code")
    category: ErrorCategory = Field(ErrorCategory.EXTERNAL_SERVICE, description="External service error category")
    severity: ErrorSeverity = Field(ErrorSeverity.HIGH, description="External service errors are typically high severity")
    service_name: str = Field(..., description="Name of the external service")
    service_status: Optional[str] = Field(None, description="Current status of the external service")
    retry_possible: bool = Field(True, description="Whether the operation can be retried")
    estimated_recovery: Optional[datetime] = Field(None, description="Estimated recovery time")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error_code": "PAYMENT_SERVICE_UNAVAILABLE",
            "message": "Payment service is temporarily unavailable",
            "category": "external_service",
            "severity": "high",
            "timestamp": "2024-01-20T10:30:00Z",
            "api_version": "v2",
            "service_name": "stripe",
            "service_status": "degraded",
            "retry_possible": True,
            "estimated_recovery": "2024-01-20T11:00:00Z",
            "help_url": "https://docs.remotehive.com/errors/external-services"
        }
    })


class DatabaseErrorResponse(BaseErrorResponse):
    """Database error response"""
    error_code: str = Field(..., description="Database error code")
    category: ErrorCategory = Field(ErrorCategory.DATABASE, description="Database error category")
    severity: ErrorSeverity = Field(ErrorSeverity.CRITICAL, description="Database errors are critical")
    operation: Optional[str] = Field(None, description="Database operation that failed")
    table: Optional[str] = Field(None, description="Database table involved")
    constraint_violated: Optional[str] = Field(None, description="Database constraint that was violated")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error_code": "UNIQUE_CONSTRAINT_VIOLATION",
            "message": "A record with this email already exists",
            "category": "database",
            "severity": "critical",
            "timestamp": "2024-01-20T10:30:00Z",
            "api_version": "v2",
            "operation": "INSERT",
            "table": "users",
            "constraint_violated": "unique_email",
            "help_url": "https://docs.remotehive.com/errors/database"
        }
    })


class SecurityErrorResponse(BaseErrorResponse):
    """Security error response"""
    error_code: str = Field(..., description="Security error code")
    category: ErrorCategory = Field(ErrorCategory.SECURITY, description="Security error category")
    severity: ErrorSeverity = Field(ErrorSeverity.CRITICAL, description="Security errors are critical")
    threat_type: Optional[str] = Field(None, description="Type of security threat detected")
    blocked_action: Optional[str] = Field(None, description="Action that was blocked")
    security_policy: Optional[str] = Field(None, description="Security policy that was triggered")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error_code": "SUSPICIOUS_ACTIVITY_DETECTED",
            "message": "Suspicious activity detected. Request blocked for security.",
            "category": "security",
            "severity": "critical",
            "timestamp": "2024-01-20T10:30:00Z",
            "api_version": "v2",
            "threat_type": "sql_injection",
            "blocked_action": "database_query",
            "security_policy": "input_validation",
            "help_url": "https://docs.remotehive.com/errors/security"
        }
    })


class SystemErrorResponse(BaseErrorResponse):
    """System error response"""
    error_code: str = Field("INTERNAL_SERVER_ERROR", description="System error code")
    category: ErrorCategory = Field(ErrorCategory.SYSTEM, description="System error category")
    severity: ErrorSeverity = Field(ErrorSeverity.CRITICAL, description="System errors are critical")
    component: Optional[str] = Field(None, description="System component that failed")
    error_id: Optional[str] = Field(None, description="Unique error identifier for tracking")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": False,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred",
            "category": "system",
            "severity": "critical",
            "timestamp": "2024-01-20T10:30:00Z",
            "api_version": "v2",
            "component": "job_processor",
            "error_id": "err_abc123def456",
            "help_url": "https://docs.remotehive.com/errors/system"
        }
    })


# Union type for all error responses
ErrorResponse = Union[
    BaseErrorResponse,
    ValidationErrorResponse,
    AuthenticationErrorResponse,
    AuthorizationErrorResponse,
    RateLimitErrorResponse,
    BusinessLogicErrorResponse,
    ExternalServiceErrorResponse,
    DatabaseErrorResponse,
    SecurityErrorResponse,
    SystemErrorResponse
]


class ErrorResponseFactory:
    """Factory for creating standardized error responses"""
    
    @staticmethod
    def create_validation_error(
        field_errors: List[FieldError],
        message: str = "Input validation failed",
        context: Optional[ErrorContext] = None
    ) -> ValidationErrorResponse:
        """Create validation error response"""
        return ValidationErrorResponse(
            message=message,
            field_errors=field_errors,
            total_errors=len(field_errors),
            context=context,
            help_url="https://docs.remotehive.com/errors/validation"
        )
    
    @staticmethod
    def create_authentication_error(
        error_code: str = "AUTHENTICATION_ERROR",
        message: str = "Authentication failed",
        auth_method: Optional[str] = None,
        token_expired: Optional[bool] = None,
        context: Optional[ErrorContext] = None
    ) -> AuthenticationErrorResponse:
        """Create authentication error response"""
        return AuthenticationErrorResponse(
            error_code=error_code,
            message=message,
            auth_method=auth_method,
            token_expired=token_expired,
            context=context,
            login_url="/api/v1/auth/login",
            help_url="https://docs.remotehive.com/errors/authentication"
        )
    
    @staticmethod
    def create_authorization_error(
        error_code: str = "AUTHORIZATION_ERROR",
        message: str = "Insufficient permissions",
        required_permissions: Optional[List[str]] = None,
        user_permissions: Optional[List[str]] = None,
        resource_id: Optional[str] = None,
        context: Optional[ErrorContext] = None
    ) -> AuthorizationErrorResponse:
        """Create authorization error response"""
        return AuthorizationErrorResponse(
            error_code=error_code,
            message=message,
            required_permissions=required_permissions,
            user_permissions=user_permissions,
            resource_id=resource_id,
            context=context,
            help_url="https://docs.remotehive.com/errors/authorization"
        )
    
    @staticmethod
    def create_rate_limit_error(
        limit: int,
        window: int,
        remaining: int,
        reset_time: datetime,
        retry_after: int,
        message: str = "Too many requests",
        context: Optional[ErrorContext] = None
    ) -> RateLimitErrorResponse:
        """Create rate limit error response"""
        return RateLimitErrorResponse(
            message=message,
            limit=limit,
            window=window,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            context=context,
            help_url="https://docs.remotehive.com/errors/rate-limit"
        )
    
    @staticmethod
    def create_business_logic_error(
        error_code: str,
        message: str,
        business_rule: Optional[str] = None,
        suggested_action: Optional[str] = None,
        context: Optional[ErrorContext] = None
    ) -> BusinessLogicErrorResponse:
        """Create business logic error response"""
        return BusinessLogicErrorResponse(
            error_code=error_code,
            message=message,
            business_rule=business_rule,
            suggested_action=suggested_action,
            context=context,
            help_url="https://docs.remotehive.com/errors/business-logic"
        )
    
    @staticmethod
    def create_external_service_error(
        error_code: str,
        message: str,
        service_name: str,
        service_status: Optional[str] = None,
        retry_possible: bool = True,
        estimated_recovery: Optional[datetime] = None,
        context: Optional[ErrorContext] = None
    ) -> ExternalServiceErrorResponse:
        """Create external service error response"""
        return ExternalServiceErrorResponse(
            error_code=error_code,
            message=message,
            service_name=service_name,
            service_status=service_status,
            retry_possible=retry_possible,
            estimated_recovery=estimated_recovery,
            context=context,
            help_url="https://docs.remotehive.com/errors/external-services"
        )
    
    @staticmethod
    def create_security_error(
        error_code: str,
        message: str,
        threat_type: Optional[str] = None,
        blocked_action: Optional[str] = None,
        security_policy: Optional[str] = None,
        context: Optional[ErrorContext] = None
    ) -> SecurityErrorResponse:
        """Create security error response"""
        return SecurityErrorResponse(
            error_code=error_code,
            message=message,
            threat_type=threat_type,
            blocked_action=blocked_action,
            security_policy=security_policy,
            context=context,
            help_url="https://docs.remotehive.com/errors/security"
        )
    
    @staticmethod
    def create_system_error(
        error_code: str = "INTERNAL_SERVER_ERROR",
        message: str = "An internal server error occurred",
        component: Optional[str] = None,
        error_id: Optional[str] = None,
        context: Optional[ErrorContext] = None
    ) -> SystemErrorResponse:
        """Create system error response"""
        return SystemErrorResponse(
            error_code=error_code,
            message=message,
            component=component,
            error_id=error_id,
            context=context,
            help_url="https://docs.remotehive.com/errors/system"
        )