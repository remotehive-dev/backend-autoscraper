#!/usr/bin/env python3
"""
Validation Middleware for RemoteHive API
Provides comprehensive input validation, sanitization, and security checks
"""

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, ValidationError as PydanticValidationError
import json
import re
import time
from datetime import datetime
from loguru import logger
from fastapi.encoders import jsonable_encoder

from backend.core.config import settings
from backend.core.exceptions import ValidationError, RateLimitError
from backend.schemas.base import ErrorResponse, ValidationErrorResponse


class ValidationConfig:
    """Configuration for validation middleware"""
    
    # Request size limits
    MAX_REQUEST_SIZE = getattr(settings, 'MAX_REQUEST_SIZE', 10 * 1024 * 1024)  # 10MB
    MAX_JSON_DEPTH = getattr(settings, 'MAX_JSON_DEPTH', 10)
    MAX_FIELD_LENGTH = getattr(settings, 'MAX_FIELD_LENGTH', 10000)
    MAX_ARRAY_LENGTH = getattr(settings, 'MAX_ARRAY_LENGTH', 1000)
    
    # Security patterns
    SUSPICIOUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',  # JavaScript protocol
        r'vbscript:',  # VBScript protocol
        r'on\w+\s*=',  # Event handlers
        r'\beval\s*\(',  # eval() calls
        r'\bexec\s*\(',  # exec() calls
        r'\\x[0-9a-fA-F]{2}',  # Hex encoded characters
        r'\\u[0-9a-fA-F]{4}',  # Unicode encoded characters
        r'\\[0-7]{1,3}',  # Octal encoded characters
        r'\.\.[\\/]',  # Path traversal
        r'[\'"]\s*;\s*\w+',  # SQL injection patterns
        r'\bunion\s+select\b',  # SQL UNION
        r'\bselect\s+.*\bfrom\b',  # SQL SELECT
        r'\binsert\s+into\b',  # SQL INSERT
        r'\bupdate\s+.*\bset\b',  # SQL UPDATE
        r'\bdelete\s+from\b',  # SQL DELETE
        r'\bdrop\s+table\b',  # SQL DROP
        r'\bor\s+1\s*=\s*1\b',  # SQL injection
        r'\band\s+1\s*=\s*1\b',  # SQL injection
    ]
    
    # Allowed content types
    ALLOWED_CONTENT_TYPES = [
        'application/json',
        'application/x-www-form-urlencoded',
        'multipart/form-data',
        'text/plain'
    ]
    
    # Rate limiting (requests per minute)
    RATE_LIMIT_REQUESTS = getattr(settings, 'RATE_LIMIT_REQUESTS', 100)
    RATE_LIMIT_WINDOW = getattr(settings, 'RATE_LIMIT_WINDOW', 60)  # seconds


class SecurityValidator:
    """Security validation utilities"""
    
    @staticmethod
    def detect_xss(text: str) -> bool:
        """Detect potential XSS attacks"""
        if not isinstance(text, str):
            return False
        
        # Check for script tags and event handlers
        xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>.*?</iframe>',
            r'<object[^>]*>.*?</object>',
            r'<embed[^>]*>.*?</embed>'
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
                return True
        
        return False
    
    @staticmethod
    def detect_sql_injection(text: str) -> bool:
        """Detect potential SQL injection attacks"""
        if not isinstance(text, str):
            return False
        
        # Common SQL injection patterns
        sql_patterns = [
            r'\bunion\s+select\b',
            r'\bselect\s+.*\bfrom\b',
            r'\binsert\s+into\b',
            r'\bupdate\s+.*\bset\b',
            r'\bdelete\s+from\b',
            r'\bdrop\s+table\b',
            r'\bor\s+1\s*=\s*1\b',
            r'\band\s+1\s*=\s*1\b',
            r'[\'"]\s*;\s*\w+',
            r'--\s*$',
            r'/\*.*\*/'
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    @staticmethod
    def detect_path_traversal(text: str) -> bool:
        """Detect path traversal attempts"""
        if not isinstance(text, str):
            return False
        
        # Path traversal patterns
        traversal_patterns = [
            r'\.\.[\\/]',
            r'[\\/]\.\.[\\/]',
            r'\.\.\\',
            r'\.\./',
            r'%2e%2e%2f',
            r'%2e%2e%5c',
            r'..%2f',
            r'..%5c'
        ]
        
        for pattern in traversal_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    @staticmethod
    def detect_command_injection(text: str) -> bool:
        """Detect command injection attempts"""
        if not isinstance(text, str):
            return False
        
        # Command injection patterns - more specific to avoid false positives
        command_patterns = [
            r'[;&|`]\s*\w+',  # Command separators followed by commands
            r'\$\([^)]*\)',  # Command substitution
            r'`[^`]+`',  # Backtick execution with content
            r'\beval\s*\(',
            r'\bexec\s*\(',
            r'\bsystem\s*\(',
            r'\bshell_exec\s*\(',
            r'\bpassthru\s*\(',
            r'\|\s*\w+',  # Pipe to commands
            r';\s*\w+',   # Semicolon followed by commands
        ]
        
        for pattern in command_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize input text"""
        if not isinstance(text, str):
            return text
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Remove control characters except newline and tab
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove potentially dangerous HTML tags
        dangerous_tags = ['script', 'iframe', 'object', 'embed', 'form', 'input', 'meta', 'link']
        for tag in dangerous_tags:
            text = re.sub(f'<{tag}[^>]*>.*?</{tag}>', '', text, flags=re.IGNORECASE | re.DOTALL)
            text = re.sub(f'<{tag}[^>]*/?>', '', text, flags=re.IGNORECASE)
        
        return text


class RequestValidator:
    """Request validation utilities"""
    
    @staticmethod
    def validate_content_type(request: Request) -> bool:
        """Validate request content type"""
        content_type = request.headers.get('content-type', '').lower()
        
        # Extract base content type (ignore charset, boundary, etc.)
        base_content_type = content_type.split(';')[0].strip()
        
        return base_content_type in ValidationConfig.ALLOWED_CONTENT_TYPES
    
    @staticmethod
    def validate_request_size(content_length: int) -> bool:
        """Validate request size"""
        return content_length <= ValidationConfig.MAX_REQUEST_SIZE
    
    @staticmethod
    def validate_json_depth(data: Any, max_depth: int = ValidationConfig.MAX_JSON_DEPTH, current_depth: int = 0) -> bool:
        """Validate JSON nesting depth"""
        if current_depth > max_depth:
            return False
        
        if isinstance(data, dict):
            for value in data.values():
                if not RequestValidator.validate_json_depth(value, max_depth, current_depth + 1):
                    return False
        elif isinstance(data, list):
            for item in data:
                if not RequestValidator.validate_json_depth(item, max_depth, current_depth + 1):
                    return False
        
        return True
    
    @staticmethod
    def validate_field_lengths(data: Any) -> List[str]:
        """Validate field lengths and return list of violations"""
        violations = []
        
        def check_field(obj: Any, path: str = ""):
            if isinstance(obj, str):
                if len(obj) > ValidationConfig.MAX_FIELD_LENGTH:
                    violations.append(f"Field '{path}' exceeds maximum length of {ValidationConfig.MAX_FIELD_LENGTH}")
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    check_field(value, new_path)
            elif isinstance(obj, list):
                if len(obj) > ValidationConfig.MAX_ARRAY_LENGTH:
                    violations.append(f"Array '{path}' exceeds maximum length of {ValidationConfig.MAX_ARRAY_LENGTH}")
                for i, item in enumerate(obj):
                    new_path = f"{path}[{i}]" if path else f"[{i}]"
                    check_field(item, new_path)
        
        check_field(data)
        return violations
    
    @staticmethod
    def scan_for_threats(data: Any) -> List[Dict[str, str]]:
        """Scan data for security threats"""
        threats = []
        
        # Fields that should be excluded from certain security checks
        password_fields = {'password', 'passwd', 'pwd', 'pass', 'secret', 'token'}
        
        def scan_value(obj: Any, path: str = ""):
            if isinstance(obj, str):
                field_name = path.split('.')[-1].lower() if '.' in path else path.lower()
                
                # Check for XSS
                if SecurityValidator.detect_xss(obj):
                    threats.append({
                        "type": "XSS",
                        "field": path,
                        "description": "Potential cross-site scripting attack detected"
                    })
                
                # Check for SQL injection
                if SecurityValidator.detect_sql_injection(obj):
                    threats.append({
                        "type": "SQL_INJECTION",
                        "field": path,
                        "description": "Potential SQL injection attack detected"
                    })
                
                # Check for path traversal
                if SecurityValidator.detect_path_traversal(obj):
                    threats.append({
                        "type": "PATH_TRAVERSAL",
                        "field": path,
                        "description": "Potential path traversal attack detected"
                    })
                
                # Check for command injection (skip password fields)
                if field_name not in password_fields and SecurityValidator.detect_command_injection(obj):
                    threats.append({
                        "type": "COMMAND_INJECTION",
                        "field": path,
                        "description": "Potential command injection attack detected"
                    })
            
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    scan_value(value, new_path)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_path = f"{path}[{i}]" if path else f"[{i}]"
                    scan_value(item, new_path)
        
        scan_value(data)
        return threats


class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.requests = {}  # {client_ip: [(timestamp, count), ...]}
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed based on rate limit"""
        now = time.time()
        window_start = now - ValidationConfig.RATE_LIMIT_WINDOW
        
        # Clean old entries
        if client_ip in self.requests:
            self.requests[client_ip] = [
                (timestamp, count) for timestamp, count in self.requests[client_ip]
                if timestamp > window_start
            ]
        else:
            self.requests[client_ip] = []
        
        # Count requests in current window
        total_requests = sum(count for _, count in self.requests[client_ip])
        
        if total_requests >= ValidationConfig.RATE_LIMIT_REQUESTS:
            return False
        
        # Add current request
        self.requests[client_ip].append((now, 1))
        return True
    
    def get_remaining_requests(self, client_ip: str) -> int:
        """Get remaining requests for client"""
        now = time.time()
        window_start = now - ValidationConfig.RATE_LIMIT_WINDOW
        
        if client_ip not in self.requests:
            return ValidationConfig.RATE_LIMIT_REQUESTS
        
        # Count requests in current window
        current_requests = sum(
            count for timestamp, count in self.requests[client_ip]
            if timestamp > window_start
        )
        
        return max(0, ValidationConfig.RATE_LIMIT_REQUESTS - current_requests)


class ValidationMiddleware(BaseHTTPMiddleware):
    """Comprehensive validation middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = RateLimiter()
        self.security_validator = SecurityValidator()
        self.request_validator = RequestValidator()
    
    async def dispatch(self, request: Request, call_next):
        """Process request through validation pipeline"""
        start_time = time.time()
        
        try:
            # Get client IP
            client_ip = self.get_client_ip(request)
            
            # Rate limiting check
            if getattr(settings, 'RATE_LIMIT_ENABLED', True):
                if not self.rate_limiter.is_allowed(client_ip):
                    return self.create_rate_limit_response(client_ip)
            
            # Content type validation
            if request.method in ['POST', 'PUT', 'PATCH']:
                if not self.request_validator.validate_content_type(request):
                    return self.create_error_response(
                        "INVALID_CONTENT_TYPE",
                        "Unsupported content type",
                        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
                    )
            
            # Request size validation
            content_length = int(request.headers.get('content-length', 0))
            if not self.request_validator.validate_request_size(content_length):
                return self.create_error_response(
                    "REQUEST_TOO_LARGE",
                    f"Request size exceeds maximum of {ValidationConfig.MAX_REQUEST_SIZE} bytes",
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                )
            
            # Body validation for JSON requests
            if request.method in ['POST', 'PUT', 'PATCH'] and content_length > 0:
                validation_result = await self.validate_request_body(request)
                if validation_result:
                    return validation_result
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            self.add_security_headers(response)
            
            # Log request metrics
            processing_time = time.time() - start_time
            logger.info(
                f"Request processed: {request.method} {request.url.path} "
                f"- {response.status_code} - {processing_time:.3f}s"
            )
            
            return response
        
        except Exception as e:
            logger.error(f"Validation middleware error: {str(e)}")
            return self.create_error_response(
                "INTERNAL_ERROR",
                "Internal server error during validation",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else 'unknown'
    
    async def validate_request_body(self, request: Request) -> Optional[Response]:
        """Validate request body"""
        try:
            # Read body
            body = await request.body()
            if not body:
                return None
            
            # Parse JSON if applicable
            content_type = request.headers.get('content-type', '').lower()
            if 'application/json' in content_type:
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    return self.create_error_response(
                        "INVALID_JSON",
                        "Invalid JSON format",
                        status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate JSON depth
                if not self.request_validator.validate_json_depth(data):
                    return self.create_error_response(
                        "JSON_TOO_DEEP",
                        f"JSON nesting exceeds maximum depth of {ValidationConfig.MAX_JSON_DEPTH}",
                        status.HTTP_400_BAD_REQUEST
                    )
                
                # Validate field lengths
                length_violations = self.request_validator.validate_field_lengths(data)
                if length_violations:
                    return self.create_validation_error_response(length_violations)
                
                # Security threat scanning
                if getattr(settings, 'BLOCK_SUSPICIOUS_REQUESTS', True):
                    threats = self.request_validator.scan_for_threats(data)
                    if threats:
                        logger.warning(f"Security threats detected: {threats}")
                        return self.create_security_error_response(threats)
            
            return None
        
        except Exception as e:
            logger.error(f"Body validation error: {str(e)}")
            return self.create_error_response(
                "VALIDATION_ERROR",
                "Error during request validation",
                status.HTTP_400_BAD_REQUEST
            )
    
    def create_error_response(self, error_code: str, message: str, status_code: int) -> JSONResponse:
        """Create standardized error response"""
        error_response = ErrorResponse(
            error_code=error_code,
            message=message,
            timestamp=datetime.now()
        )
        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder(error_response.dict())
        )
    
    def create_validation_error_response(self, violations: List[str]) -> JSONResponse:
        """Create validation error response"""
        field_errors = [{
            "field": "request",
            "message": violation
        } for violation in violations]
        
        error_response = ValidationErrorResponse(
            message="Request validation failed",
            field_errors=field_errors,
            timestamp=datetime.now()
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(error_response.dict())
        )
    
    def create_security_error_response(self, threats: List[Dict[str, str]]) -> JSONResponse:
        """Create security error response"""
        error_response = ErrorResponse(
            error_code="SECURITY_THREAT_DETECTED",
            message="Request contains potential security threats",
            details={"threats": threats},
            timestamp=datetime.now()
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=jsonable_encoder(error_response.dict())
        )
    
    def create_rate_limit_response(self, client_ip: str) -> JSONResponse:
        """Create rate limit error response"""
        remaining = self.rate_limiter.get_remaining_requests(client_ip)
        
        error_response = ErrorResponse(
            error_code="RATE_LIMIT_EXCEEDED",
            message="Too many requests",
            details={
                "limit": ValidationConfig.RATE_LIMIT_REQUESTS,
                "window": ValidationConfig.RATE_LIMIT_WINDOW,
                "remaining": remaining
            },
            timestamp=datetime.now()
        )
        
        response = JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=jsonable_encoder(error_response.dict())
        )
        
        response.headers["X-RateLimit-Limit"] = str(ValidationConfig.RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + ValidationConfig.RATE_LIMIT_WINDOW))
        response.headers["Retry-After"] = str(ValidationConfig.RATE_LIMIT_WINDOW)
        
        return response
    
    def add_security_headers(self, response: Response):
        """Add security headers to response"""
        if getattr(settings, 'SECURITY_HEADERS_ENABLED', True):
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
            
            if getattr(settings, 'CSP_ENABLED', True):
                csp_policy = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data: https:; "
                    "font-src 'self'; "
                    "connect-src 'self'; "
                    "frame-ancestors 'none';"
                )
                response.headers["Content-Security-Policy"] = csp_policy