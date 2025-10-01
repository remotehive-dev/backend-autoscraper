from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union, Set
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import re
import html
import json
import time
from collections import defaultdict
from urllib.parse import unquote

try:
    from backend.core.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

try:
    from backend.core.config import settings
except ImportError:
    class Settings:
        ENVIRONMENT = "development"
        SECURITY_HEADERS_ENABLED = True
        RATE_LIMIT_REQUESTS = 100
        RATE_LIMIT_WINDOW = 60
        MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB
    settings = Settings()


class SecurityConfig:
    """Security configuration settings"""
    
    # XSS Protection patterns
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
    
    # SQL Injection patterns
    SQL_INJECTION_PATTERNS = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b)',
        r'(--|#|/\*|\*/)',
        r'(\b(OR|AND)\b.*\b(=|LIKE)\b)',
        r'(\b(CHAR|ASCII|SUBSTRING|LENGTH|USER|DATABASE|VERSION)\b\s*\()',
        r'(\b(WAITFOR|DELAY)\b)',
        r'(\b(CAST|CONVERT|CONCAT)\b\s*\()',
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r'\.\./+',
        r'\.\.\\+',
        r'%2e%2e%2f',
        r'%2e%2e\\',
        r'\\\.\.\\',
        r'/\.\./',
    ]
    
    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r'[;&|`$(){}\[\]<>]',
        r'\b(cat|ls|pwd|whoami|id|uname|ps|netstat|ifconfig|ping|wget|curl|nc|telnet|ssh|ftp)\b',
        r'(\||&&|;|`|\$\(|\${)',
    ]
    
    # Dangerous file extensions
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', '.jar',
        '.php', '.asp', '.aspx', '.jsp', '.py', '.rb', '.pl', '.sh', '.ps1'
    }
    
    # Security headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' https:; connect-src 'self' https:; frame-ancestors 'none';"
    }


class InputSanitizer:
    """Input sanitization and validation utilities"""
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input for XSS and other attacks"""
        if not isinstance(value, str):
            return str(value)
        
        # Truncate if too long
        if len(value) > max_length:
            value = value[:max_length]
        
        # URL decode
        value = unquote(value)
        
        # HTML escape
        value = html.escape(value, quote=True)
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Normalize whitespace
        value = re.sub(r'\s+', ' ', value).strip()
        
        return value
    
    @staticmethod
    def detect_xss(value: str) -> bool:
        """Detect potential XSS attacks"""
        if not isinstance(value, str):
            return False
        
        value_lower = value.lower()
        for pattern in SecurityConfig.XSS_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE | re.DOTALL):
                return True
        return False
    
    @staticmethod
    def detect_sql_injection(value: str) -> bool:
        """Detect potential SQL injection attacks"""
        if not isinstance(value, str):
            return False
        
        value_lower = value.lower()
        for pattern in SecurityConfig.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False
    
    @staticmethod
    def detect_path_traversal(value: str) -> bool:
        """Detect potential path traversal attacks"""
        if not isinstance(value, str):
            return False
        
        value_lower = value.lower()
        for pattern in SecurityConfig.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False
    
    @staticmethod
    def detect_command_injection(value: str) -> bool:
        """Detect potential command injection attacks"""
        if not isinstance(value, str):
            return False
        
        for pattern in SecurityConfig.COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage"""
        if not isinstance(filename, str):
            return "unknown"
        
        # Remove path components
        filename = filename.split('/')[-1].split('\\')[-1]
        
        # Remove dangerous characters
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250] + ('.' + ext if ext else '')
        
        return filename
    
    @staticmethod
    def validate_file_extension(filename: str) -> bool:
        """Validate file extension is safe"""
        if not isinstance(filename, str):
            return False
        
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        return f'.{ext}' not in SecurityConfig.DANGEROUS_EXTENSIONS
    
    @staticmethod
    def sanitize_dict(data: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
        """Recursively sanitize dictionary data"""
        if max_depth <= 0:
            return {}
        
        sanitized = {}
        for key, value in data.items():
            # Sanitize key
            clean_key = InputSanitizer.sanitize_string(str(key), 100)
            
            # Sanitize value based on type
            if isinstance(value, str):
                sanitized[clean_key] = InputSanitizer.sanitize_string(value)
            elif isinstance(value, dict):
                sanitized[clean_key] = InputSanitizer.sanitize_dict(value, max_depth - 1)
            elif isinstance(value, list):
                sanitized[clean_key] = [
                    InputSanitizer.sanitize_string(str(item)) if isinstance(item, str) else item
                    for item in value[:100]  # Limit list size
                ]
            else:
                sanitized[clean_key] = value
        
        return sanitized


class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.blocked_ips: Dict[str, float] = {}
    
    def is_allowed(self, client_ip: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
        """Check if request is allowed based on rate limiting"""
        current_time = time.time()
        
        # Check if IP is temporarily blocked
        if client_ip in self.blocked_ips:
            if current_time < self.blocked_ips[client_ip]:
                return False
            else:
                del self.blocked_ips[client_ip]
        
        # Clean old requests
        cutoff_time = current_time - window_seconds
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if req_time > cutoff_time
        ]
        
        # Check rate limit
        if len(self.requests[client_ip]) >= max_requests:
            # Block IP for 5 minutes
            self.blocked_ips[client_ip] = current_time + 300
            return False
        
        # Add current request
        self.requests[client_ip].append(current_time)
        return True
    
    def cleanup(self):
        """Clean up old entries"""
        current_time = time.time()
        cutoff_time = current_time - 3600  # 1 hour
        
        # Clean requests
        for ip in list(self.requests.keys()):
            self.requests[ip] = [
                req_time for req_time in self.requests[ip]
                if req_time > cutoff_time
            ]
            if not self.requests[ip]:
                del self.requests[ip]
        
        # Clean blocked IPs
        for ip in list(self.blocked_ips.keys()):
            if current_time >= self.blocked_ips[ip]:
                del self.blocked_ips[ip]


class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware"""
    
    def __init__(self, app: ASGIApp, logger_name: str = "security"):
        super().__init__(app)
        self.logger = get_logger(logger_name)
        self.rate_limiter = RateLimiter()
        self.sanitizer = InputSanitizer()
        
        # Security statistics
        self.security_stats = {
            'blocked_requests': 0,
            'xss_attempts': 0,
            'sql_injection_attempts': 0,
            'path_traversal_attempts': 0,
            'command_injection_attempts': 0,
            'rate_limit_violations': 0,
            'oversized_requests': 0
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process request through security filters"""
        client_ip = self._get_client_ip(request)
        
        try:
            # 1. Rate limiting
            if not self._check_rate_limit(request, client_ip):
                return self._create_security_response(
                    "Rate limit exceeded", 
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    client_ip,
                    "rate_limit_violation"
                )
            
            # 2. Request size validation
            if not await self._validate_request_size(request):
                return self._create_security_response(
                    "Request too large",
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    client_ip,
                    "oversized_request"
                )
            
            # 3. Input validation and sanitization
            security_violation = await self._validate_and_sanitize_input(request)
            if security_violation:
                return self._create_security_response(
                    f"Security violation detected: {security_violation}",
                    status.HTTP_400_BAD_REQUEST,
                    client_ip,
                    security_violation
                )
            
            # 4. Process request
            response = await call_next(request)
            
            # 5. Add security headers
            self._add_security_headers(response)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Security middleware error: {e}", client_ip=client_ip)
            return self._create_security_response(
                "Security processing error",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                client_ip,
                "processing_error"
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to client host
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    def _check_rate_limit(self, request: Request, client_ip: str) -> bool:
        """Check rate limiting"""
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]:
            return True
        
        max_requests = getattr(settings, 'RATE_LIMIT_REQUESTS', 100)
        window_seconds = getattr(settings, 'RATE_LIMIT_WINDOW', 60)
        
        allowed = self.rate_limiter.is_allowed(client_ip, max_requests, window_seconds)
        
        if not allowed:
            self.security_stats['rate_limit_violations'] += 1
            self.logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        
        return allowed
    
    async def _validate_request_size(self, request: Request) -> bool:
        """Validate request size"""
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                max_size = getattr(settings, 'MAX_REQUEST_SIZE', 10 * 1024 * 1024)
                
                if size > max_size:
                    self.security_stats['oversized_requests'] += 1
                    return False
            except ValueError:
                return False
        
        return True
    
    async def _validate_and_sanitize_input(self, request: Request) -> Optional[str]:
        """Validate and sanitize request input"""
        try:
            # Check URL path
            if self.sanitizer.detect_path_traversal(request.url.path):
                self.security_stats['path_traversal_attempts'] += 1
                return "path_traversal"
            
            # Check query parameters
            for key, value in request.query_params.items():
                if self.sanitizer.detect_xss(value):
                    self.security_stats['xss_attempts'] += 1
                    return "xss_attempt"
                
                if self.sanitizer.detect_sql_injection(value):
                    self.security_stats['sql_injection_attempts'] += 1
                    return "sql_injection"
                
                if self.sanitizer.detect_command_injection(value):
                    self.security_stats['command_injection_attempts'] += 1
                    return "command_injection"
            
            # Skip body validation to avoid consuming request.body()
            # Body validation should be done at the endpoint level
            # to avoid conflicts with FastAPI's request parsing
            
            return None
            
        except Exception as e:
            self.logger.error(f"Input validation error: {e}")
            return None
    
    def _add_security_headers(self, response: Response):
        """Add security headers to response"""
        if not getattr(settings, 'SECURITY_HEADERS_ENABLED', True):
            return
        
        for header, value in SecurityConfig.SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # Add cache control for sensitive endpoints
        if hasattr(response, 'headers'):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
    
    def _create_security_response(
        self, 
        message: str, 
        status_code: int, 
        client_ip: str, 
        violation_type: str
    ) -> JSONResponse:
        """Create standardized security violation response"""
        self.security_stats['blocked_requests'] += 1
        
        self.logger.warning(
            f"Security violation: {violation_type}",
            client_ip=client_ip,
            details=message
        )
        
        error_data = {
            "error": {
                "code": "SECURITY_VIOLATION",
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "type": violation_type
            }
        }
        
        response = JSONResponse(
            status_code=status_code,
            content=error_data
        )
        
        # Add security headers even to error responses
        self._add_security_headers(response)
        
        return response
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics"""
        # Cleanup rate limiter periodically
        self.rate_limiter.cleanup()
        
        return {
            "security_stats": self.security_stats.copy(),
            "rate_limiter_stats": {
                "active_ips": len(self.rate_limiter.requests),
                "blocked_ips": len(self.rate_limiter.blocked_ips)
            }
        }


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """CSRF Protection Middleware"""
    
    def __init__(self, app: ASGIApp, secret_key: str = None):
        super().__init__(app)
        self.secret_key = secret_key or getattr(settings, 'SECRET_KEY', 'default-secret')
        self.logger = get_logger("csrf")
    
    async def dispatch(self, request: Request, call_next):
        """Check CSRF token for state-changing requests"""
        # Skip CSRF for safe methods and API endpoints
        if request.method in ["GET", "HEAD", "OPTIONS"] or request.url.path.startswith("/api/") or request.url.path.startswith("/auth/"):
            return await call_next(request)
        
        # Check CSRF token
        csrf_token = request.headers.get("X-CSRF-Token") or request.cookies.get("csrf_token")
        
        if not csrf_token or not self._validate_csrf_token(csrf_token):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": {
                        "code": "CSRF_TOKEN_MISSING",
                        "message": "CSRF token missing or invalid"
                    }
                }
            )
        
        return await call_next(request)
    
    def _validate_csrf_token(self, token: str) -> bool:
        """Validate CSRF token (simplified implementation)"""
        # In a real implementation, you'd use cryptographic validation
        # This is a simplified version for demonstration
        return len(token) >= 32 and token.isalnum()


# Export middleware classes
__all__ = [
    'SecurityMiddleware',
    'CSRFProtectionMiddleware', 
    'InputSanitizer',
    'RateLimiter',
    'SecurityConfig'
]