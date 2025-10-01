#!/usr/bin/env python3
"""
Validation Schemas for RemoteHive API
Provides comprehensive input validation with security focus
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Dict, Any, List, Optional, Union, Pattern, ClassVar
from datetime import datetime, date
from enum import Enum
import re
import html
import urllib.parse
from decimal import Decimal

from backend.schemas.base import BaseSchema, ValidationPatterns


class ValidationSeverity(str, Enum):
    """Validation error severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationRule(BaseModel):
    """Individual validation rule"""
    field: str = Field(..., description="Field name being validated")
    rule: str = Field(..., description="Validation rule name")
    severity: ValidationSeverity = Field(..., description="Severity of validation failure")
    message: str = Field(..., description="Validation error message")
    value: Optional[Any] = Field(None, description="Value that failed validation")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "field": "email",
            "rule": "email_format",
            "severity": "error",
            "message": "Invalid email format",
            "value": "invalid-email"
        }
    })


class ValidationResult(BaseModel):
    """Result of validation process"""
    is_valid: bool = Field(..., description="Whether validation passed")
    errors: List[ValidationRule] = Field(default_factory=list, description="Validation errors")
    warnings: List[ValidationRule] = Field(default_factory=list, description="Validation warnings")
    sanitized_data: Optional[Dict[str, Any]] = Field(None, description="Sanitized input data")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "is_valid": False,
            "errors": [
                {
                    "field": "email",
                    "rule": "email_format",
                    "severity": "error",
                    "message": "Invalid email format",
                    "value": "invalid-email"
                }
            ],
            "warnings": [],
            "sanitized_data": {
                "email": "user@example.com",
                "name": "John Doe"
            }
        }
    })


class SecurityValidationMixin:
    """Mixin for security-focused validation methods"""
    
    @staticmethod
    def sanitize_html(value: str) -> str:
        """Sanitize HTML content to prevent XSS"""
        if not isinstance(value, str):
            return value
        
        # HTML escape
        sanitized = html.escape(value)
        
        # Remove potentially dangerous patterns
        dangerous_patterns = [
            r'javascript:',
            r'vbscript:',
            r'data:',
            r'<script[^>]*>.*?</script>',
            r'<iframe[^>]*>.*?</iframe>',
            r'<object[^>]*>.*?</object>',
            r'<embed[^>]*>.*?</embed>',
            r'on\w+\s*=',  # Event handlers
        ]
        
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        return sanitized.strip()
    
    @staticmethod
    def sanitize_sql(value: str) -> str:
        """Sanitize input to prevent SQL injection"""
        if not isinstance(value, str):
            return value
        
        # Remove SQL injection patterns
        sql_patterns = [
            r"[';]\s*(DROP|DELETE|INSERT|UPDATE|CREATE|ALTER|EXEC|EXECUTE)\s+",
            r"UNION\s+SELECT",
            r"--\s*$",
            r"/\*.*?\*/",
            r"'\s*OR\s+'.*?'\s*=\s*'",
            r"'\s*AND\s+'.*?'\s*=\s*'",
        ]
        
        sanitized = value
        for pattern in sql_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        return sanitized.strip()
    
    @staticmethod
    def sanitize_path(value: str) -> str:
        """Sanitize file paths to prevent directory traversal"""
        if not isinstance(value, str):
            return value
        
        # Remove path traversal patterns
        sanitized = value.replace('..', '').replace('//', '/')
        sanitized = re.sub(r'[<>:"|?*]', '', sanitized)  # Remove invalid filename chars
        
        return sanitized.strip('/')
    
    @staticmethod
    def validate_url_safety(url: str) -> bool:
        """Validate URL for safety (no malicious schemes)"""
        if not isinstance(url, str):
            return False
        
        try:
            parsed = urllib.parse.urlparse(url)
            safe_schemes = ['http', 'https', 'ftp', 'ftps']
            return parsed.scheme.lower() in safe_schemes
        except Exception:
            return False


class SecureStringField(BaseModel):
    """String field with security validation"""
    value: str = Field(..., min_length=1, max_length=1000)
    
    @field_validator('value')
    @classmethod
    def sanitize_value(cls, v):
        if not isinstance(v, str):
            raise ValueError("Value must be a string")
        
        # Apply security sanitization
        sanitized = SecurityValidationMixin.sanitize_html(v)
        sanitized = SecurityValidationMixin.sanitize_sql(sanitized)
        
        if not sanitized:
            raise ValueError("Value cannot be empty after sanitization")
        
        return sanitized


class SecureEmailField(BaseModel):
    """Email field with enhanced validation"""
    email: str = Field(..., pattern=ValidationPatterns.EMAIL)
    
    @field_validator('email')
    @classmethod
    def validate_email_security(cls, v):
        # Basic format validation is handled by regex
        # Additional security checks
        if len(v) > 254:  # RFC 5321 limit
            raise ValueError("Email address too long")
        
        local, domain = v.rsplit('@', 1)
        
        # Local part validation
        if len(local) > 64:  # RFC 5321 limit
            raise ValueError("Email local part too long")
        
        # Domain validation
        if len(domain) > 253:  # RFC 1035 limit
            raise ValueError("Email domain too long")
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'[<>"\\]',  # Dangerous characters
            r'\.\.+',     # Multiple consecutive dots
            r'^\.',       # Starting with dot
            r'\.$',       # Ending with dot
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, v):
                raise ValueError("Email contains suspicious patterns")
        
        return v.lower().strip()


class SecurePasswordField(BaseModel):
    """Password field with strength validation"""
    password: str = Field(..., min_length=8, max_length=128)
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        if len(v) > 128:
            raise ValueError("Password must not exceed 128 characters")
        
        # Check for required character types
        has_upper = bool(re.search(r'[A-Z]', v))
        has_lower = bool(re.search(r'[a-z]', v))
        has_digit = bool(re.search(r'\d', v))
        has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', v))
        
        strength_score = sum([has_upper, has_lower, has_digit, has_special])
        
        if strength_score < 3:
            raise ValueError(
                "Password must contain at least 3 of: uppercase, lowercase, digits, special characters"
            )
        
        # Check for common weak patterns
        weak_patterns = [
            r'(.)\1{2,}',      # Repeated characters (3+)
            r'123456',          # Sequential numbers
            r'abcdef',          # Sequential letters
            r'qwerty',          # Keyboard patterns
            r'password',        # Common words
            r'admin',
            r'user',
        ]
        
        for pattern in weak_patterns:
            if re.search(pattern, v.lower()):
                raise ValueError(f"Password contains weak pattern: {pattern}")
        
        return v


class SecureURLField(BaseModel):
    """URL field with security validation"""
    url: str = Field(..., pattern=ValidationPatterns.URL)
    
    @field_validator('url')
    @classmethod
    def validate_url_security(cls, v):
        if not SecurityValidationMixin.validate_url_safety(v):
            raise ValueError("URL scheme not allowed")
        
        # Check URL length
        if len(v) > 2048:  # Common browser limit
            raise ValueError("URL too long")
        
        # Check for suspicious patterns
        suspicious_patterns = [
            r'javascript:',
            r'vbscript:',
            r'data:',
            r'file:',
            r'ftp://.*@',  # FTP with credentials
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, v.lower()):
                raise ValueError(f"URL contains suspicious pattern: {pattern}")
        
        return v


class SecureFilePathField(BaseModel):
    """File path field with security validation"""
    path: str = Field(..., min_length=1, max_length=255)
    
    @field_validator('path')
    @classmethod
    def validate_path_security(cls, v):
        # Sanitize path
        sanitized = SecurityValidationMixin.sanitize_path(v)
        
        if not sanitized:
            raise ValueError("Path cannot be empty after sanitization")
        
        # Check for dangerous patterns
        dangerous_patterns = [
            r'\.\.',           # Directory traversal
            r'/etc/',          # System directories
            r'/proc/',
            r'/sys/',
            r'\\\\',         # UNC paths
            r'^[a-zA-Z]:',     # Windows drive letters
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sanitized):
                raise ValueError(f"Path contains dangerous pattern: {pattern}")
        
        return sanitized


class NumericRangeValidator(BaseModel):
    """Validator for numeric ranges with bounds checking"""
    value: Union[int, float, Decimal]
    min_value: Optional[Union[int, float, Decimal]] = None
    max_value: Optional[Union[int, float, Decimal]] = None
    
    @model_validator(mode='before')
    @classmethod
    def validate_range(cls, values):
        value = values.get('value')
        min_val = values.get('min_value')
        max_val = values.get('max_value')
        
        if min_val is not None and value < min_val:
            raise ValueError(f"Value {value} is below minimum {min_val}")
        
        if max_val is not None and value > max_val:
            raise ValueError(f"Value {value} is above maximum {max_val}")
        
        return values


class DateRangeValidator(BaseModel):
    """Validator for date ranges"""
    start_date: date
    end_date: date
    
    @model_validator(mode='before')
    @classmethod
    def validate_date_range(cls, values):
        start = values.get('start_date')
        end = values.get('end_date')
        
        if start and end and start > end:
            raise ValueError("Start date must be before or equal to end date")
        
        # Check for reasonable date ranges
        if start and start < date(1900, 1, 1):
            raise ValueError("Start date too far in the past")
        
        if end and end > date(2100, 12, 31):
            raise ValueError("End date too far in the future")
        
        return values


class FileUploadValidator(BaseModel):
    """Validator for file uploads with security checks"""
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=100)
    file_size: int = Field(..., gt=0)
    
    # Allowed file types and sizes
    ALLOWED_EXTENSIONS: ClassVar[Dict[str, List[str]]] = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
        'document': ['.pdf', '.doc', '.docx', '.txt', '.rtf'],
        'spreadsheet': ['.xls', '.xlsx', '.csv'],
        'archive': ['.zip', '.tar', '.gz']
    }
    
    ALLOWED_MIME_TYPES: ClassVar[set] = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'application/pdf', 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain', 'text/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/zip', 'application/x-tar', 'application/gzip'
    }
    
    MAX_FILE_SIZE: ClassVar[int] = 10 * 1024 * 1024  # 10MB
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        # Sanitize filename
        sanitized = SecurityValidationMixin.sanitize_path(v)
        
        if not sanitized:
            raise ValueError("Invalid filename")
        
        # Check extension
        extension = '.' + sanitized.lower().split('.')[-1] if '.' in sanitized else ''
        
        allowed_extensions = []
        for ext_list in cls.ALLOWED_EXTENSIONS.values():
            allowed_extensions.extend(ext_list)
        
        if extension not in allowed_extensions:
            raise ValueError(f"File extension {extension} not allowed")
        
        # Check for dangerous filenames
        dangerous_names = [
            'con', 'prn', 'aux', 'nul',  # Windows reserved names
            'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
            'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
        ]
        
        name_without_ext = sanitized.lower().split('.')[0]
        if name_without_ext in dangerous_names:
            raise ValueError(f"Filename {name_without_ext} is reserved")
        
        return sanitized
    
    @field_validator('content_type')
    @classmethod
    def validate_content_type(cls, v):
        if v not in cls.ALLOWED_MIME_TYPES:
            raise ValueError(f"Content type {v} not allowed")
        return v
    
    @field_validator('file_size')
    @classmethod
    def validate_file_size(cls, v):
        if v > cls.MAX_FILE_SIZE:
            raise ValueError(f"File size {v} exceeds maximum {cls.MAX_FILE_SIZE}")
        return v


class BulkOperationValidator(BaseModel):
    """Validator for bulk operations with limits"""
    items: List[Dict[str, Any]] = Field(..., min_length=1, max_length=1000)
    operation: str = Field(..., pattern=r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    
    @field_validator('items')
    @classmethod
    def validate_items(cls, v):
        if len(v) > 1000:
            raise ValueError("Too many items in bulk operation (max 1000)")
        
        # Validate each item has required structure
        for i, item in enumerate(v):
            if not isinstance(item, dict):
                raise ValueError(f"Item {i} must be a dictionary")
            
            # Check for suspicious content in each item
            for key, value in item.items():
                if isinstance(value, str):
                    # Apply basic sanitization
                    sanitized = SecurityValidationMixin.sanitize_html(value)
                    sanitized = SecurityValidationMixin.sanitize_sql(sanitized)
                    item[key] = sanitized
        
        return v
    
    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        allowed_operations = [
            'create', 'update', 'delete', 'import', 'export',
            'activate', 'deactivate', 'approve', 'reject'
        ]
        
        if v not in allowed_operations:
            raise ValueError(f"Operation {v} not allowed")
        
        return v


class SearchQueryValidator(BaseModel):
    """Validator for search queries with security checks"""
    query: str = Field(..., min_length=1, max_length=500)
    filters: Optional[Dict[str, Any]] = Field(None, max_length=20)
    
    @field_validator('query')
    @classmethod
    def validate_search_query(cls, v):
        # Sanitize query
        sanitized = SecurityValidationMixin.sanitize_html(v)
        sanitized = SecurityValidationMixin.sanitize_sql(sanitized)
        
        if not sanitized:
            raise ValueError("Search query cannot be empty after sanitization")
        
        # Check for injection patterns
        injection_patterns = [
            r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]',  # Control characters
            r'<script[^>]*>',
            r'javascript:',
            r'vbscript:',
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                raise ValueError("Search query contains suspicious patterns")
        
        return sanitized
    
    @field_validator('filters')
    @classmethod
    def validate_filters(cls, v):
        if not v:
            return v
        
        # Sanitize filter values
        for key, value in v.items():
            if isinstance(value, str):
                v[key] = SecurityValidationMixin.sanitize_html(value)
        
        return v


class APIKeyValidator(BaseModel):
    """Validator for API keys with format checking"""
    api_key: str = Field(..., min_length=32, max_length=128)
    
    @field_validator('api_key')
    @classmethod
    def validate_api_key_format(cls, v):
        # API key should be alphanumeric with possible hyphens/underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("API key contains invalid characters")
        
        # Check for minimum entropy (basic check)
        unique_chars = len(set(v))
        if unique_chars < 8:
            raise ValueError("API key has insufficient entropy")
        
        return v


class IPAddressValidator(BaseModel):
    """Validator for IP addresses"""
    ip_address: str = Field(..., min_length=7, max_length=45)  # IPv4: 7-15, IPv6: up to 45
    
    @field_validator('ip_address')
    @classmethod
    def validate_ip_format(cls, v):
        import ipaddress
        
        try:
            # This will validate both IPv4 and IPv6
            ip = ipaddress.ip_address(v)
            
            # Check for private/reserved addresses if needed
            if ip.is_private:
                # You might want to allow or disallow private IPs based on context
                pass
            
            if ip.is_loopback:
                # You might want to allow or disallow loopback IPs based on context
                pass
            
            return str(ip)
        
        except ValueError:
            raise ValueError("Invalid IP address format")


class CronExpressionValidator(BaseModel):
    """Validator for cron expressions"""
    cron_expression: str = Field(..., min_length=9, max_length=100)
    
    @field_validator('cron_expression')
    @classmethod
    def validate_cron_format(cls, v):
        # Basic cron validation (5 or 6 fields)
        parts = v.split()
        
        if len(parts) not in [5, 6]:
            raise ValueError("Cron expression must have 5 or 6 fields")
        
        # Validate each field format
        field_patterns = [
            r'^(\*|\d+(-\d+)?(,\d+(-\d+)?)*|\*/\d+)$',  # minute
            r'^(\*|\d+(-\d+)?(,\d+(-\d+)?)*|\*/\d+)$',  # hour
            r'^(\*|\d+(-\d+)?(,\d+(-\d+)?)*|\*/\d+)$',  # day
            r'^(\*|\d+(-\d+)?(,\d+(-\d+)?)*|\*/\d+)$',  # month
            r'^(\*|\d+(-\d+)?(,\d+(-\d+)?)*|\*/\d+)$',  # day of week
        ]
        
        if len(parts) == 6:
            # Add year field pattern
            field_patterns.append(r'^(\*|\d+(-\d+)?(,\d+(-\d+)?)*|\*/\d+)$')
        
        for i, (part, pattern) in enumerate(zip(parts, field_patterns)):
            if not re.match(pattern, part):
                raise ValueError(f"Invalid cron field {i+1}: {part}")
        
        return v