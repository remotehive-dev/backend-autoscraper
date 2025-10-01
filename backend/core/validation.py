from typing import Any, Dict, List, Optional, Union, Type
from pydantic import BaseModel, validator, Field, field_validator
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated
from fastapi import HTTPException, status
import re
import html
from urllib.parse import unquote
from datetime import datetime
from enum import Enum

try:
    from backend.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)


class ValidationError(HTTPException):
    """Custom validation error"""
    
    def __init__(self, detail: str, field: str = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "VALIDATION_ERROR",
                "message": detail,
                "field": field,
                "timestamp": datetime.now().isoformat()
            }
        )


class SecurityValidationError(HTTPException):
    """Security-related validation error"""
    
    def __init__(self, detail: str, violation_type: str = "security_violation"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "SECURITY_VIOLATION",
                "message": detail,
                "type": violation_type,
                "timestamp": datetime.now().isoformat()
            }
        )


class InputType(str, Enum):
    """Input validation types"""
    TEXT = "text"
    EMAIL = "email"
    URL = "url"
    PHONE = "phone"
    FILENAME = "filename"
    JSON = "json"
    SQL_SAFE = "sql_safe"
    HTML_SAFE = "html_safe"
    ALPHANUMERIC = "alphanumeric"
    NUMERIC = "numeric"


class ValidationConfig:
    """Validation configuration and patterns"""
    
    # Email validation pattern (RFC 5322 compliant)
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )
    
    # URL validation pattern
    URL_PATTERN = re.compile(
        r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?$'
    )
    
    # Phone number pattern (international format)
    PHONE_PATTERN = re.compile(
        r'^\+?[1-9]\d{1,14}$'
    )
    
    # Safe filename pattern
    FILENAME_PATTERN = re.compile(
        r'^[a-zA-Z0-9._-]+$'
    )
    
    # Alphanumeric pattern
    ALPHANUMERIC_PATTERN = re.compile(
        r'^[a-zA-Z0-9]+$'
    )
    
    # Numeric pattern
    NUMERIC_PATTERN = re.compile(
        r'^\d+$'
    )
    
    # Dangerous patterns for security validation
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>.*?</iframe>',
        r'<object[^>]*>.*?</object>',
        r'<embed[^>]*>.*?</embed>',
        r'<link[^>]*>',
        r'<meta[^>]*>',
        r'<style[^>]*>.*?</style>',
        r'expression\s*\(',
        r'url\s*\(',
        r'@import',
    ]
    
    SQL_INJECTION_PATTERNS = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)',
        r'(--|#|/\*|\*/)',
        r'(\b(OR|AND)\b.*\b(=|LIKE)\b)',
        r'(\b(CHAR|ASCII|SUBSTRING|LENGTH|USER|DATABASE|VERSION)\b\s*\()',
        r'(\b(WAITFOR|DELAY)\b)',
        r'(\b(CAST|CONVERT|CONCAT)\b\s*\()',
    ]
    
    # Default length limits
    DEFAULT_MAX_LENGTH = {
        InputType.TEXT: 1000,
        InputType.EMAIL: 254,
        InputType.URL: 2048,
        InputType.PHONE: 20,
        InputType.FILENAME: 255,
        InputType.ALPHANUMERIC: 100,
        InputType.NUMERIC: 20
    }


class InputValidator:
    """Enhanced input validation utilities"""
    
    def __init__(self):
        self.logger = get_logger("validation")
    
    def validate_input(
        self, 
        value: Any, 
        input_type: InputType, 
        max_length: Optional[int] = None,
        min_length: Optional[int] = None,
        required: bool = True,
        allow_empty: bool = False,
        custom_pattern: Optional[str] = None
    ) -> str:
        """Comprehensive input validation"""
        
        # Handle None/empty values
        if value is None:
            if required:
                raise ValidationError("Field is required")
            return "" if allow_empty else None
        
        # Convert to string
        str_value = str(value).strip()
        
        # Check empty string
        if not str_value:
            if required and not allow_empty:
                raise ValidationError("Field cannot be empty")
            return "" if allow_empty else None
        
        # Length validation
        max_len = max_length or ValidationConfig.DEFAULT_MAX_LENGTH.get(input_type, 1000)
        if len(str_value) > max_len:
            raise ValidationError(f"Input too long (max {max_len} characters)")
        
        if min_length and len(str_value) < min_length:
            raise ValidationError(f"Input too short (min {min_length} characters)")
        
        # Security validation
        self._validate_security(str_value)
        
        # Type-specific validation
        validated_value = self._validate_by_type(str_value, input_type, custom_pattern)
        
        return validated_value
    
    def _validate_security(self, value: str):
        """Security validation to prevent attacks"""
        
        # Check for XSS patterns
        for pattern in ValidationConfig.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE | re.DOTALL):
                self.logger.warning(f"XSS attempt detected: {pattern}")
                raise SecurityValidationError(
                    "Potentially malicious content detected",
                    "xss_attempt"
                )
        
        # Check for SQL injection patterns
        for pattern in ValidationConfig.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                self.logger.warning(f"SQL injection attempt detected: {pattern}")
                raise SecurityValidationError(
                    "Potentially malicious SQL content detected",
                    "sql_injection"
                )
        
        # Check for path traversal
        if re.search(r'\.\.[\/\\]', value):
            self.logger.warning("Path traversal attempt detected")
            raise SecurityValidationError(
                "Path traversal attempt detected",
                "path_traversal"
            )
        
        # Check for command injection
        if re.search(r'[;&|`$(){}\[\]<>]', value):
            self.logger.warning("Command injection attempt detected")
            raise SecurityValidationError(
                "Potentially dangerous characters detected",
                "command_injection"
            )
    
    def _validate_by_type(self, value: str, input_type: InputType, custom_pattern: Optional[str] = None) -> str:
        """Type-specific validation"""
        
        if custom_pattern:
            if not re.match(custom_pattern, value):
                raise ValidationError(f"Input does not match required pattern")
            return value
        
        if input_type == InputType.EMAIL:
            if not ValidationConfig.EMAIL_PATTERN.match(value):
                raise ValidationError("Invalid email format")
            return value.lower()
        
        elif input_type == InputType.URL:
            if not ValidationConfig.URL_PATTERN.match(value):
                raise ValidationError("Invalid URL format")
            return value
        
        elif input_type == InputType.PHONE:
            # Remove common separators
            clean_phone = re.sub(r'[\s\-\(\)]', '', value)
            if not ValidationConfig.PHONE_PATTERN.match(clean_phone):
                raise ValidationError("Invalid phone number format")
            return clean_phone
        
        elif input_type == InputType.FILENAME:
            if not ValidationConfig.FILENAME_PATTERN.match(value):
                raise ValidationError("Invalid filename format")
            return value
        
        elif input_type == InputType.ALPHANUMERIC:
            if not ValidationConfig.ALPHANUMERIC_PATTERN.match(value):
                raise ValidationError("Input must be alphanumeric")
            return value
        
        elif input_type == InputType.NUMERIC:
            if not ValidationConfig.NUMERIC_PATTERN.match(value):
                raise ValidationError("Input must be numeric")
            return value
        
        elif input_type == InputType.HTML_SAFE:
            # HTML escape for safe display
            return html.escape(value, quote=True)
        
        elif input_type == InputType.SQL_SAFE:
            # Additional SQL safety (beyond security validation)
            # Remove or escape SQL metacharacters
            safe_value = value.replace("'", "''").replace('"', '""')
            return safe_value
        
        elif input_type == InputType.JSON:
            try:
                import json
                # Validate JSON format
                json.loads(value)
                return value
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format")
        
        else:  # InputType.TEXT or default
            # Basic text sanitization
            # URL decode
            decoded = unquote(value)
            # Remove null bytes
            cleaned = decoded.replace('\x00', '')
            # Normalize whitespace
            normalized = re.sub(r'\s+', ' ', cleaned).strip()
            return normalized
    
    def sanitize_dict(self, data: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
        """Recursively sanitize dictionary data"""
        if max_depth <= 0:
            return {}
        
        sanitized = {}
        for key, value in data.items():
            # Sanitize key
            try:
                clean_key = self.validate_input(
                    key, 
                    InputType.TEXT, 
                    max_length=100, 
                    required=True
                )
            except (ValidationError, SecurityValidationError):
                # Skip invalid keys
                continue
            
            # Sanitize value based on type
            if isinstance(value, str):
                try:
                    sanitized[clean_key] = self.validate_input(
                        value, 
                        InputType.TEXT, 
                        required=False
                    )
                except (ValidationError, SecurityValidationError):
                    # Skip invalid values
                    continue
            elif isinstance(value, dict):
                sanitized[clean_key] = self.sanitize_dict(value, max_depth - 1)
            elif isinstance(value, list):
                sanitized_list = []
                for item in value[:100]:  # Limit list size
                    if isinstance(item, str):
                        try:
                            sanitized_item = self.validate_input(
                                item, 
                                InputType.TEXT, 
                                required=False
                            )
                            if sanitized_item is not None:
                                sanitized_list.append(sanitized_item)
                        except (ValidationError, SecurityValidationError):
                            continue
                    else:
                        sanitized_list.append(item)
                sanitized[clean_key] = sanitized_list
            else:
                sanitized[clean_key] = value
        
        return sanitized


class SecureBaseModel(BaseModel):
    """Base model with enhanced security validation"""
    
    class Config:
        # Validate assignment to prevent injection after creation
        validate_assignment = True
        # Use enum values for better validation
        use_enum_values = True
        # Allow population by field name
        allow_population_by_field_name = True
        # Forbid extra fields to prevent injection
        extra = "forbid"
    
    def __init__(self, **data):
        # Sanitize input data before validation
        validator = InputValidator()
        sanitized_data = validator.sanitize_dict(data)
        super().__init__(**sanitized_data)


# Validation decorators
def validate_field(input_type: InputType, **validation_kwargs):
    """Decorator for field validation"""
    def decorator(func):
        def wrapper(cls, value):
            validator = InputValidator()
            validated_value = validator.validate_input(value, input_type, **validation_kwargs)
            return func(cls, validated_value) if func else validated_value
        return wrapper
    return decorator


# Common validation schemas - Updated for Pydantic v2
def validate_email(value):
    """Email validation function"""
    validator = InputValidator()
    return validator.validate_input(value, InputType.EMAIL)

def validate_url(value):
    """URL validation function"""
    validator = InputValidator()
    return validator.validate_input(value, InputType.URL)

def validate_phone(value):
    """Phone validation function"""
    validator = InputValidator()
    return validator.validate_input(value, InputType.PHONE)

def validate_safe_text(value):
    """Safe text validation function"""
    validator = InputValidator()
    return validator.validate_input(value, InputType.HTML_SAFE)

# Type aliases for validated fields
EmailField = Annotated[str, BeforeValidator(validate_email)]
URLField = Annotated[str, BeforeValidator(validate_url)]
PhoneField = Annotated[str, BeforeValidator(validate_phone)]
SafeTextField = Annotated[str, BeforeValidator(validate_safe_text)]


# Export main classes and functions
__all__ = [
    'InputValidator',
    'ValidationError',
    'SecurityValidationError',
    'InputType',
    'SecureBaseModel',
    'EmailField',
    'URLField', 
    'PhoneField',
    'SafeTextField',
    'validate_field'
]