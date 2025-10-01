#!/usr/bin/env python3
"""
Enhanced Middleware for RemoteHive API
Provides comprehensive request/response processing with security and monitoring
"""

import time
import json
import uuid
import logging
import asyncio
import re
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import httpx

from backend.core.config import get_settings
from backend.core.exceptions import (
    RateLimitExceededException,
    SecurityThreatDetectedException,
    ValidationException
)
from backend.schemas.validation import SecurityValidationMixin
from backend.api.versioning import VersionExtractor, validate_api_version, get_api_version


@dataclass
class RequestMetrics:
    """Metrics for individual requests"""
    request_id: str
    method: str
    path: str
    user_agent: Optional[str]
    ip_address: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status_code: Optional[int] = None
    response_size: Optional[int] = None
    processing_time_ms: Optional[int] = None
    api_version: Optional[str] = None
    user_id: Optional[str] = None
    error_code: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "method": self.method,
            "path": self.path,
            "user_agent": self.user_agent,
            "ip_address": self.ip_address,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status_code": self.status_code,
            "response_size": self.response_size,
            "processing_time_ms": self.processing_time_ms,
            "api_version": self.api_version,
            "user_id": self.user_id,
            "error_code": self.error_code
        }


@dataclass
class RateLimitBucket:
    """Rate limiting bucket for tracking requests"""
    requests: deque = field(default_factory=deque)
    window_size: int = 60  # seconds
    max_requests: int = 100
    
    def add_request(self, timestamp: datetime) -> bool:
        """Add a request and return True if within limits"""
        # Remove old requests outside the window
        cutoff = timestamp - timedelta(seconds=self.window_size)
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
        
        # Check if we're at the limit
        if len(self.requests) >= self.max_requests:
            return False
        
        # Add the new request
        self.requests.append(timestamp)
        return True
    
    def get_remaining(self) -> int:
        """Get remaining requests in current window"""
        return max(0, self.max_requests - len(self.requests))
    
    def get_reset_time(self) -> datetime:
        """Get when the rate limit resets"""
        if not self.requests:
            return datetime.now()
        return self.requests[0] + timedelta(seconds=self.window_size)


class SecurityScanner:
    """Advanced security scanning for requests"""
    
    def __init__(self):
        self.threat_patterns = {
            'xss': [
                r'<script[^>]*>.*?</script>',
                r'javascript:',
                r'vbscript:',
                r'on\w+\s*=',
                r'<iframe[^>]*>',
                r'<object[^>]*>',
                r'<embed[^>]*>',
            ],
            'sql_injection': [
                r"[';]\s*(DROP|DELETE|INSERT|UPDATE|CREATE|ALTER|EXEC|EXECUTE)\s+",
                r"UNION\s+SELECT",
                r"'\s*OR\s+'.*?'\s*=\s*'",
                r"'\s*AND\s+'.*?'\s*=\s*'",
                r"--\s*$",
                r"/\*.*?\*/",
            ],
            'path_traversal': [
                r'\.\./.*',
                r'\\\.\.\\.*',
                r'/etc/passwd',
                r'/proc/.*',
                r'\\windows\\system32',
            ],
            'command_injection': [
                r'[;&|`$]\s*(rm|del|format|shutdown|reboot)',
                r'\$\([^)]*\)',
                r'`[^`]*`',
                r'\|\s*(nc|netcat|wget|curl)',
            ],
            'nosql_injection': [
                r'\$where',
                r'\$ne',
                r'\$gt',
                r'\$regex',
                r'\$or',
                r'\$and',
            ]
        }
        
        self.suspicious_headers = {
            'x-forwarded-for': r'^(?!127\.0\.0\.1|localhost)',
            'user-agent': r'(bot|crawler|spider|scraper)',
            'referer': r'(malware|phishing|suspicious)',
        }
    
    def scan_request(self, request: Request, body: bytes) -> List[Dict[str, Any]]:
        """Scan request for security threats"""
        threats = []
        
        # Scan URL and query parameters
        threats.extend(self._scan_url(str(request.url)))
        
        # Scan headers
        threats.extend(self._scan_headers(request.headers))
        
        # Scan body
        if body:
            threats.extend(self._scan_body(body))
        
        return threats
    
    def _scan_url(self, url: str) -> List[Dict[str, Any]]:
        """Scan URL for threats"""
        threats = []
        
        for threat_type, patterns in self.threat_patterns.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    threats.append({
                        'type': threat_type,
                        'location': 'url',
                        'pattern': pattern,
                        'value': url
                    })
        
        return threats
    
    def _scan_headers(self, headers) -> List[Dict[str, Any]]:
        """Scan headers for threats"""
        threats = []
        
        for header_name, header_value in headers.items():
            header_name_lower = header_name.lower()
            
            # Check suspicious header patterns
            if header_name_lower in self.suspicious_headers:
                pattern = self.suspicious_headers[header_name_lower]
                if re.search(pattern, header_value, re.IGNORECASE):
                    threats.append({
                        'type': 'suspicious_header',
                        'location': f'header:{header_name}',
                        'pattern': pattern,
                        'value': header_value
                    })
            
            # Scan header values for injection patterns
            for threat_type, patterns in self.threat_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, header_value, re.IGNORECASE):
                        threats.append({
                            'type': threat_type,
                            'location': f'header:{header_name}',
                            'pattern': pattern,
                            'value': header_value
                        })
        
        return threats
    
    def _scan_body(self, body: bytes) -> List[Dict[str, Any]]:
        """Scan request body for threats"""
        threats = []
        
        try:
            # Try to decode as text
            body_text = body.decode('utf-8', errors='ignore')
            
            # Scan for threat patterns
            for threat_type, patterns in self.threat_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, body_text, re.IGNORECASE):
                        threats.append({
                            'type': threat_type,
                            'location': 'body',
                            'pattern': pattern,
                            'value': body_text[:200]  # Truncate for logging
                        })
            
            # Try to parse as JSON and scan recursively
            try:
                json_data = json.loads(body_text)
                threats.extend(self._scan_json_recursive(json_data))
            except json.JSONDecodeError:
                pass
        
        except UnicodeDecodeError:
            # Binary data - check for suspicious patterns
            if b'<script' in body or b'javascript:' in body:
                threats.append({
                    'type': 'binary_threat',
                    'location': 'body',
                    'pattern': 'suspicious_binary_content',
                    'value': 'Binary data with suspicious patterns'
                })
        
        return threats
    
    def _scan_json_recursive(self, data: Any, path: str = 'root') -> List[Dict[str, Any]]:
        """Recursively scan JSON data for threats"""
        threats = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}"
                threats.extend(self._scan_json_recursive(value, new_path))
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]"
                threats.extend(self._scan_json_recursive(item, new_path))
        
        elif isinstance(data, str):
            # Scan string values
            for threat_type, patterns in self.threat_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, data, re.IGNORECASE):
                        threats.append({
                            'type': threat_type,
                            'location': f'json:{path}',
                            'pattern': pattern,
                            'value': data[:200]  # Truncate for logging
                        })
        
        return threats


class MetricsCollector:
    """Collect and aggregate request metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, RequestMetrics] = {}
        self.aggregated_metrics = {
            'total_requests': 0,
            'requests_by_method': defaultdict(int),
            'requests_by_status': defaultdict(int),
            'requests_by_path': defaultdict(int),
            'average_response_time': 0,
            'error_rate': 0,
            'last_updated': datetime.now()
        }
        self.cleanup_interval = 3600  # 1 hour
        self.last_cleanup = datetime.now()
    
    def start_request(self, request: Request) -> str:
        """Start tracking a request"""
        request_id = str(uuid.uuid4())
        
        metrics = RequestMetrics(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            user_agent=request.headers.get('user-agent'),
            ip_address=self._get_client_ip(request),
            start_time=datetime.now()
        )
        
        self.metrics[request_id] = metrics
        return request_id
    
    def end_request(self, request_id: str, status_code: int, response_size: int = 0, 
                   user_id: str = None, error_code: str = None, api_version: str = None):
        """End tracking a request"""
        if request_id not in self.metrics:
            return
        
        metrics = self.metrics[request_id]
        metrics.end_time = datetime.now()
        metrics.status_code = status_code
        metrics.response_size = response_size
        metrics.user_id = user_id
        metrics.error_code = error_code
        metrics.api_version = api_version
        
        if metrics.start_time and metrics.end_time:
            metrics.processing_time_ms = int(
                (metrics.end_time - metrics.start_time).total_seconds() * 1000
            )
        
        # Update aggregated metrics
        self._update_aggregated_metrics(metrics)
        
        # Cleanup old metrics periodically
        self._cleanup_old_metrics()
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        # Check for forwarded headers
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        # Fallback to client host
        if hasattr(request, 'client') and request.client:
            return request.client.host
        
        return 'unknown'
    
    def _update_aggregated_metrics(self, metrics: RequestMetrics):
        """Update aggregated metrics"""
        self.aggregated_metrics['total_requests'] += 1
        self.aggregated_metrics['requests_by_method'][metrics.method] += 1
        self.aggregated_metrics['requests_by_status'][metrics.status_code] += 1
        self.aggregated_metrics['requests_by_path'][metrics.path] += 1
        
        # Update average response time
        if metrics.processing_time_ms:
            current_avg = self.aggregated_metrics['average_response_time']
            total_requests = self.aggregated_metrics['total_requests']
            
            new_avg = ((current_avg * (total_requests - 1)) + metrics.processing_time_ms) / total_requests
            self.aggregated_metrics['average_response_time'] = new_avg
        
        # Update error rate
        error_count = sum(
            count for status, count in self.aggregated_metrics['requests_by_status'].items()
            if status >= 400
        )
        self.aggregated_metrics['error_rate'] = error_count / self.aggregated_metrics['total_requests']
        
        self.aggregated_metrics['last_updated'] = datetime.now()
    
    def _cleanup_old_metrics(self):
        """Remove old metrics to prevent memory leaks"""
        now = datetime.now()
        if (now - self.last_cleanup).seconds < self.cleanup_interval:
            return
        
        cutoff = now - timedelta(hours=24)  # Keep metrics for 24 hours
        
        old_request_ids = [
            request_id for request_id, metrics in self.metrics.items()
            if metrics.start_time < cutoff
        ]
        
        for request_id in old_request_ids:
            del self.metrics[request_id]
        
        self.last_cleanup = now
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics"""
        return dict(self.aggregated_metrics)
    
    def get_request_metrics(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific request"""
        if request_id in self.metrics:
            return self.metrics[request_id].to_dict()
        return None


class EnhancedMiddleware(BaseHTTPMiddleware):
    """Enhanced middleware with comprehensive request/response processing"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.rate_limiters: Dict[str, RateLimitBucket] = defaultdict(
            lambda: RateLimitBucket(
                max_requests=self.settings.RATE_LIMIT_REQUESTS,
                window_size=self.settings.RATE_LIMIT_WINDOW
            )
        )
        self.security_scanner = SecurityScanner()
        self.metrics_collector = MetricsCollector()
        self.version_extractor = VersionExtractor()
        
        # Configuration
        self.enable_security_scanning = getattr(self.settings, 'ENABLE_SECURITY_SCANNING', True)
        self.enable_rate_limiting = getattr(self.settings, 'ENABLE_RATE_LIMITING', True)
        self.enable_metrics_collection = getattr(self.settings, 'ENABLE_METRICS_COLLECTION', True)
        self.enable_request_logging = getattr(self.settings, 'ENABLE_REQUEST_LOGGING', True)
        
        # Paths to skip middleware processing
        self.skip_paths = {
            '/health',
            '/metrics',
            '/docs',
            '/redoc',
            '/openapi.json'
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Main middleware dispatch method"""
        # Skip processing for certain paths
        if request.url.path in self.skip_paths:
            return await call_next(request)
        
        # Start request tracking
        request_id = None
        if self.enable_metrics_collection:
            request_id = self.metrics_collector.start_request(request)
            request.state.request_id = request_id
        
        start_time = time.time()
        
        try:
            # Pre-processing
            await self._pre_process_request(request)
            
            # Process request
            response = await call_next(request)
            
            # Post-processing
            response = await self._post_process_response(request, response, start_time)
            
            return response
        
        except Exception as e:
            # Handle errors
            return await self._handle_error(request, e, start_time, request_id)
    
    async def _pre_process_request(self, request: Request):
        """Pre-process incoming request"""
        client_ip = self._get_client_ip(request)
        
        # Rate limiting
        if self.enable_rate_limiting:
            await self._check_rate_limit(client_ip)
        
        # API version validation
        try:
            api_version = get_api_version(request)
            request.state.api_version = api_version
        except Exception as e:
            # If version extraction fails, continue without version
            request.state.api_version = None
        
        # Security scanning
        if self.enable_security_scanning:
            await self._scan_request_security(request)
        
        # Request logging
        if self.enable_request_logging:
            self._log_request(request)
    
    async def _post_process_response(self, request: Request, response: Response, start_time: float) -> Response:
        """Post-process outgoing response"""
        processing_time = time.time() - start_time
        
        # Add response headers
        self._add_response_headers(request, response, processing_time)
        
        # Update metrics
        if self.enable_metrics_collection and hasattr(request.state, 'request_id'):
            response_size = len(response.body) if hasattr(response, 'body') else 0
            user_id = getattr(request.state, 'user_id', None)
            api_version = getattr(request.state, 'api_version', None)
            
            self.metrics_collector.end_request(
                request.state.request_id,
                response.status_code,
                response_size,
                user_id,
                api_version=api_version
            )
        
        # Response logging
        if self.enable_request_logging:
            self._log_response(request, response, processing_time)
        
        return response
    
    async def _check_rate_limit(self, client_ip: str):
        """Check rate limiting for client IP"""
        bucket = self.rate_limiters[client_ip]
        
        if not bucket.add_request(datetime.now()):
            remaining = bucket.get_remaining()
            reset_time = bucket.get_reset_time()
            
            raise RateLimitExceededException(
                f"Rate limit exceeded for IP {client_ip}",
                details={
                    'limit': bucket.max_requests,
                    'remaining': remaining,
                    'reset_time': reset_time.isoformat(),
                    'window_size': bucket.window_size
                }
            )
    
    async def _scan_request_security(self, request: Request):
        """Scan request for security threats"""
        # Read request body
        body = b''
        if request.method in ['POST', 'PUT', 'PATCH']:
            body = await request.body()
        
        # Scan for threats
        threats = self.security_scanner.scan_request(request, body)
        
        if threats:
            # Log security threats
            self.logger.warning(
                f"Security threats detected in request from {self._get_client_ip(request)}",
                extra={
                    'threats': threats,
                    'request_path': request.url.path,
                    'request_method': request.method
                }
            )
            
            # Block request if critical threats found
            critical_threats = [t for t in threats if t['type'] in ['sql_injection', 'command_injection']]
            if critical_threats:
                raise SecurityThreatDetectedException(
                    "Critical security threat detected",
                    details={'threats': critical_threats}
                )
    
    def _add_response_headers(self, request: Request, response: Response, processing_time: float):
        """Add standard response headers"""
        # Request ID
        if hasattr(request.state, 'request_id'):
            response.headers['X-Request-ID'] = request.state.request_id
        
        # Processing time
        response.headers['X-Processing-Time'] = f"{processing_time:.3f}s"
        
        # API version
        if hasattr(request.state, 'api_version'):
            response.headers['X-API-Version'] = request.state.api_version
        
        # Rate limit headers
        if self.enable_rate_limiting:
            client_ip = self._get_client_ip(request)
            bucket = self.rate_limiters[client_ip]
            response.headers['X-RateLimit-Limit'] = str(bucket.max_requests)
            response.headers['X-RateLimit-Remaining'] = str(bucket.get_remaining())
            response.headers['X-RateLimit-Reset'] = bucket.get_reset_time().isoformat()
        
        # Security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # CORS headers (if needed)
        if hasattr(self.settings, 'CORS_ORIGINS'):
            origin = request.headers.get('origin')
            if origin and origin in self.settings.CORS_ORIGINS:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    async def _handle_error(self, request: Request, error: Exception, start_time: float, request_id: str = None) -> Response:
        """Handle errors during request processing"""
        processing_time = time.time() - start_time
        
        # Log error
        self.logger.error(
            f"Error processing request: {str(error)}",
            extra={
                'request_id': request_id,
                'request_path': request.url.path,
                'request_method': request.method,
                'processing_time': processing_time,
                'error_type': type(error).__name__
            },
            exc_info=True
        )
        
        # Update metrics
        if self.enable_metrics_collection and request_id:
            status_code = getattr(error, 'status_code', 500)
            error_code = getattr(error, 'error_code', type(error).__name__)
            
            self.metrics_collector.end_request(
                request_id,
                status_code,
                error_code=error_code
            )
        
        # Create error response
        if isinstance(error, HTTPException):
            status_code = error.status_code
            detail = error.detail
        elif isinstance(error, (RateLimitExceededException, SecurityThreatDetectedException, ValidationException)):
            status_code = error.status_code
            detail = {
                'error': error.message,
                'error_code': error.error_code,
                'details': getattr(error, 'details', None)
            }
        else:
            status_code = 500
            detail = {
                'error': 'Internal server error',
                'error_code': 'INTERNAL_ERROR'
            }
        
        response_data = {
            'success': False,
            'status': 'error',
            'message': 'Request processing failed',
            'error': detail,
            'metadata': {
                'request_id': request_id,
                'timestamp': datetime.now().isoformat(),
                'processing_time_ms': int(processing_time * 1000)
            }
        }
        
        response = JSONResponse(
            content=response_data,
            status_code=status_code
        )
        
        # Add standard headers
        self._add_response_headers(request, response, processing_time)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        # Check for forwarded headers
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        # Fallback to client host
        if hasattr(request, 'client') and request.client:
            return request.client.host
        
        return 'unknown'
    
    def _log_request(self, request: Request):
        """Log incoming request"""
        self.logger.info(
            f"{request.method} {request.url.path}",
            extra={
                'request_id': getattr(request.state, 'request_id', None),
                'method': request.method,
                'path': request.url.path,
                'query_params': dict(request.query_params),
                'user_agent': request.headers.get('user-agent'),
                'client_ip': self._get_client_ip(request),
                'api_version': getattr(request.state, 'api_version', None)
            }
        )
    
    def _log_response(self, request: Request, response: Response, processing_time: float):
        """Log outgoing response"""
        self.logger.info(
            f"{request.method} {request.url.path} - {response.status_code}",
            extra={
                'request_id': getattr(request.state, 'request_id', None),
                'method': request.method,
                'path': request.url.path,
                'status_code': response.status_code,
                'processing_time': processing_time,
                'response_size': len(response.body) if hasattr(response, 'body') else 0
            }
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self.metrics_collector.get_metrics_summary()
    
    def get_request_metrics(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for specific request"""
        return self.metrics_collector.get_request_metrics(request_id)