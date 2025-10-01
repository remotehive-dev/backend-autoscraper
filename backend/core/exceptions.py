#!/usr/bin/env python3
"""
RemoteHive Custom Exceptions
Defines custom exception classes for better error handling and categorization
"""

from typing import Optional, Dict, Any, List
from datetime import datetime


class RemoteHiveException(Exception):
    """Base exception class for RemoteHive applications"""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.status_code = status_code
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "status_code": self.status_code,
            "timestamp": self.timestamp.isoformat(),
            "exception_type": self.__class__.__name__
        }


# Authentication and Authorization Exceptions
class AuthenticationError(RemoteHiveException):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, status_code=401, **kwargs)


class TokenExpiredError(AuthenticationError):
    """Raised when JWT token has expired"""
    
    def __init__(self, message: str = "Token has expired", **kwargs):
        super().__init__(message, **kwargs)


class TokenInvalidError(AuthenticationError):
    """Raised when JWT token is invalid"""
    
    def __init__(self, message: str = "Invalid token", **kwargs):
        super().__init__(message, **kwargs)


class AuthorizationError(RemoteHiveException):
    """Raised when user lacks required permissions"""
    
    def __init__(self, message: str = "Insufficient permissions", **kwargs):
        super().__init__(message, status_code=403, **kwargs)


class PermissionDeniedError(AuthorizationError):
    """Raised when specific permission is denied"""
    
    def __init__(self, permission: str, resource: Optional[str] = None, **kwargs):
        message = f"Permission '{permission}' denied"
        if resource:
            message += f" for resource '{resource}'"
        
        details = {"permission": permission}
        if resource:
            details["resource"] = resource
        
        super().__init__(message, details=details, **kwargs)


# Database Exceptions
class DatabaseError(RemoteHiveException):
    """Base class for database-related errors"""
    
    def __init__(self, message: str, operation: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if operation:
            details['operation'] = operation
        kwargs['details'] = details
        super().__init__(message, status_code=500, **kwargs)


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails"""
    
    def __init__(self, message: str = "Database connection failed", **kwargs):
        super().__init__(message, operation="connection", **kwargs)


class DatabaseIntegrityError(DatabaseError):
    """Raised when database integrity constraint is violated"""
    
    def __init__(self, message: str, constraint: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if constraint:
            details['constraint'] = constraint
        kwargs['details'] = details
        super().__init__(message, operation="integrity_check", **kwargs)


class RecordNotFoundError(DatabaseError):
    """Raised when a database record is not found"""
    
    def __init__(self, resource: str, identifier: Any, **kwargs):
        message = f"{resource} with identifier '{identifier}' not found"
        details = {
            "resource": resource,
            "identifier": str(identifier)
        }
        super().__init__(message, operation="select", details=details, status_code=404, **kwargs)


class DuplicateRecordError(DatabaseError):
    """Raised when attempting to create a duplicate record"""
    
    def __init__(self, resource: str, field: str, value: Any, **kwargs):
        message = f"{resource} with {field} '{value}' already exists"
        details = {
            "resource": resource,
            "field": field,
            "value": str(value)
        }
        super().__init__(message, operation="insert", details=details, status_code=409, **kwargs)


# Validation Exceptions
class ValidationError(RemoteHiveException):
    """Raised when data validation fails"""
    
    def __init__(
        self, 
        message: str = "Validation failed", 
        field_errors: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if field_errors:
            details['field_errors'] = field_errors
        kwargs['details'] = details
        super().__init__(message, status_code=422, **kwargs)


class RequiredFieldError(ValidationError):
    """Raised when a required field is missing"""
    
    def __init__(self, field: str, **kwargs):
        message = f"Required field '{field}' is missing"
        field_errors = [{
            "field": field,
            "message": "This field is required",
            "type": "missing"
        }]
        super().__init__(message, field_errors=field_errors, **kwargs)


class InvalidFormatError(ValidationError):
    """Raised when field format is invalid"""
    
    def __init__(self, field: str, expected_format: str, **kwargs):
        message = f"Field '{field}' has invalid format. Expected: {expected_format}"
        field_errors = [{
            "field": field,
            "message": f"Invalid format. Expected: {expected_format}",
            "type": "format"
        }]
        super().__init__(message, field_errors=field_errors, **kwargs)


# Business Logic Exceptions
class BusinessLogicError(RemoteHiveException):
    """Raised when business logic rules are violated"""
    
    def __init__(self, message: str, rule: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if rule:
            details['rule'] = rule
        kwargs['details'] = details
        super().__init__(message, status_code=400, **kwargs)


class InsufficientResourcesError(BusinessLogicError):
    """Raised when insufficient resources are available"""
    
    def __init__(self, resource: str, required: Any, available: Any, **kwargs):
        message = f"Insufficient {resource}. Required: {required}, Available: {available}"
        details = {
            "resource": resource,
            "required": str(required),
            "available": str(available)
        }
        super().__init__(message, details=details, **kwargs)


class InvalidStateError(BusinessLogicError):
    """Raised when operation is invalid for current state"""
    
    def __init__(self, current_state: str, operation: str, **kwargs):
        message = f"Cannot perform '{operation}' in current state '{current_state}'"
        details = {
            "current_state": current_state,
            "operation": operation
        }
        super().__init__(message, details=details, **kwargs)


# External Service Exceptions
class ExternalServiceError(RemoteHiveException):
    """Raised when external service call fails"""
    
    def __init__(self, service: str, message: str = "External service error", **kwargs):
        details = kwargs.get('details', {})
        details['service'] = service
        kwargs['details'] = details
        super().__init__(message, status_code=502, **kwargs)


class ServiceUnavailableError(ExternalServiceError):
    """Raised when external service is unavailable"""
    
    def __init__(self, service: str, **kwargs):
        message = f"Service '{service}' is currently unavailable"
        super().__init__(service, message, status_code=503, **kwargs)


class ServiceTimeoutError(ExternalServiceError):
    """Raised when external service call times out"""
    
    def __init__(self, service: str, timeout: float, **kwargs):
        message = f"Service '{service}' timed out after {timeout} seconds"
        details = kwargs.get('details', {})
        details['timeout'] = timeout
        kwargs['details'] = details
        super().__init__(service, message, **kwargs)


# Rate Limiting Exceptions
class RateLimitError(RemoteHiveException):
    """Raised when rate limit is exceeded"""
    
    def __init__(
        self, 
        message: str = "Rate limit exceeded", 
        limit: Optional[int] = None,
        window: Optional[int] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if limit:
            details['limit'] = limit
        if window:
            details['window'] = window
        if retry_after:
            details['retry_after'] = retry_after
        kwargs['details'] = details
        super().__init__(message, status_code=429, **kwargs)


class TooManyRequestsError(RateLimitError):
    """Raised when too many requests are made"""
    
    def __init__(self, requests: int, limit: int, window: int, **kwargs):
        message = f"Too many requests: {requests}/{limit} in {window} seconds"
        super().__init__(message, limit=limit, window=window, **kwargs)


# Configuration Exceptions
class ConfigurationError(RemoteHiveException):
    """Raised when configuration is invalid or missing"""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if config_key:
            details['config_key'] = config_key
        kwargs['details'] = details
        super().__init__(message, status_code=500, **kwargs)


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing"""
    
    def __init__(self, config_key: str, **kwargs):
        message = f"Missing required configuration: {config_key}"
        super().__init__(message, config_key=config_key, **kwargs)


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration value is invalid"""
    
    def __init__(self, config_key: str, value: Any, reason: str, **kwargs):
        message = f"Invalid configuration '{config_key}' = '{value}': {reason}"
        details = kwargs.get('details', {})
        details.update({
            'value': str(value),
            'reason': reason
        })
        kwargs['details'] = details
        super().__init__(message, config_key=config_key, **kwargs)


# File and I/O Exceptions
class FileOperationError(RemoteHiveException):
    """Raised when file operation fails"""
    
    def __init__(self, operation: str, filepath: str, message: str, **kwargs):
        full_message = f"File {operation} failed for '{filepath}': {message}"
        details = {
            "operation": operation,
            "filepath": filepath,
            "original_message": message
        }
        super().__init__(full_message, details=details, **kwargs)


class FileNotFoundError(FileOperationError):
    """Raised when file is not found"""
    
    def __init__(self, filepath: str, **kwargs):
        super().__init__("read", filepath, "File not found", status_code=404, **kwargs)


class FilePermissionError(FileOperationError):
    """Raised when file permission is denied"""
    
    def __init__(self, operation: str, filepath: str, **kwargs):
        super().__init__(operation, filepath, "Permission denied", status_code=403, **kwargs)


# Web Scraping Exceptions
class ScrapingError(RemoteHiveException):
    """Base class for web scraping errors"""
    
    def __init__(self, url: str, message: str, **kwargs):
        details = kwargs.get('details', {})
        details['url'] = url
        kwargs['details'] = details
        super().__init__(message, **kwargs)


class PageLoadError(ScrapingError):
    """Raised when page fails to load"""
    
    def __init__(self, url: str, status_code: Optional[int] = None, **kwargs):
        message = f"Failed to load page: {url}"
        if status_code:
            message += f" (HTTP {status_code})"
        
        details = kwargs.get('details', {})
        if status_code:
            details['http_status'] = status_code
        kwargs['details'] = details
        
        super().__init__(url, message, **kwargs)


class ElementNotFoundError(ScrapingError):
    """Raised when required element is not found on page"""
    
    def __init__(self, url: str, selector: str, **kwargs):
        message = f"Element not found: {selector}"
        details = kwargs.get('details', {})
        details['selector'] = selector
        kwargs['details'] = details
        super().__init__(url, message, **kwargs)


class AntiScrapingDetectedError(ScrapingError):
    """Raised when anti-scraping measures are detected"""
    
    def __init__(self, url: str, detection_type: str, **kwargs):
        message = f"Anti-scraping detected: {detection_type}"
        details = kwargs.get('details', {})
        details['detection_type'] = detection_type
        kwargs['details'] = details
        super().__init__(url, message, **kwargs)


# Task and Queue Exceptions
class TaskError(RemoteHiveException):
    """Base class for task-related errors"""
    
    def __init__(self, task_id: str, message: str, **kwargs):
        details = kwargs.get('details', {})
        details['task_id'] = task_id
        kwargs['details'] = details
        super().__init__(message, **kwargs)


class TaskNotFoundError(TaskError):
    """Raised when task is not found"""
    
    def __init__(self, task_id: str, **kwargs):
        message = f"Task not found: {task_id}"
        super().__init__(task_id, message, status_code=404, **kwargs)


class TaskExecutionError(TaskError):
    """Raised when task execution fails"""
    
    def __init__(self, task_id: str, error_message: str, **kwargs):
        message = f"Task execution failed: {error_message}"
        details = kwargs.get('details', {})
        details['error_message'] = error_message
        kwargs['details'] = details
        super().__init__(task_id, message, **kwargs)


class QueueFullError(RemoteHiveException):
    """Raised when queue is full"""
    
    def __init__(self, queue_name: str, max_size: int, **kwargs):
        message = f"Queue '{queue_name}' is full (max size: {max_size})"
        details = {
            "queue_name": queue_name,
            "max_size": max_size
        }
        super().__init__(message, details=details, status_code=503, **kwargs)


# Security Exceptions
class SecurityThreatDetectedException(RemoteHiveException):
    """Raised when a security threat is detected"""
    
    def __init__(self, threat_type: str, message: str = "Security threat detected", **kwargs):
        details = kwargs.get('details', {})
        details['threat_type'] = threat_type
        kwargs['details'] = details
        super().__init__(message, status_code=403, **kwargs)


# Aliases for backward compatibility
RateLimitExceededException = RateLimitError
ValidationException = ValidationError


# Export all exception classes
__all__ = [
    # Base
    'RemoteHiveException',
    
    # Authentication/Authorization
    'AuthenticationError',
    'TokenExpiredError', 
    'TokenInvalidError',
    'AuthorizationError',
    'PermissionDeniedError',
    
    # Database
    'DatabaseError',
    'DatabaseConnectionError',
    'DatabaseIntegrityError',
    'RecordNotFoundError',
    'DuplicateRecordError',
    
    # Validation
    'ValidationError',
    'RequiredFieldError',
    'InvalidFormatError',
    
    # Business Logic
    'BusinessLogicError',
    'InsufficientResourcesError',
    'InvalidStateError',
    
    # External Services
    'ExternalServiceError',
    'ServiceUnavailableError',
    'ServiceTimeoutError',
    
    # Rate Limiting
    'RateLimitError',
    'TooManyRequestsError',
    
    # Configuration
    'ConfigurationError',
    'MissingConfigurationError',
    'InvalidConfigurationError',
    
    # File Operations
    'FileOperationError',
    'FileNotFoundError',
    'FilePermissionError',
    
    # Web Scraping
    'ScrapingError',
    'PageLoadError',
    'ElementNotFoundError',
    'AntiScrapingDetectedError',
    
    # Tasks and Queues
    'TaskError',
    'TaskNotFoundError',
    'TaskExecutionError',
    'QueueFullError',
    
    # Security
    'SecurityThreatDetectedException',
    
    # Aliases
    'RateLimitExceededException',
    'ValidationException'
]