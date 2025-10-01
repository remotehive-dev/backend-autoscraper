#!/usr/bin/env python3
"""
RemoteHive Error Handling Middleware
Provides comprehensive error handling, logging, and monitoring for FastAPI applications
"""

import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Union
from contextlib import asynccontextmanager

# Core FastAPI imports with fallbacks
try:
    from fastapi import Request, Response, HTTPException
    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError
except ImportError:
    # Fallback for testing without FastAPI
    Request = None
    Response = None
    HTTPException = Exception
    JSONResponse = None
    RequestValidationError = Exception

try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.exceptions import HTTPException as StarletteHTTPException
except ImportError:
    BaseHTTPMiddleware = object
    StarletteHTTPException = Exception

try:
    from pydantic import ValidationError
except ImportError:
    ValidationError = Exception

import asyncio

try:
    from backend.core.logging import get_logger, LogContext, ErrorInfo, LogLevel
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)
    LogContext = None
    ErrorInfo = None
    LogLevel = None

try:
    from backend.core.config import settings
except ImportError:
    # Fallback settings
    class Settings:
        ENVIRONMENT = "development"
    settings = Settings()


class ErrorResponse:
    """Standardized error response format"""
    
    def __init__(self, error: str = None, message: str = None, status_code: int = 500, details: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None):
        """Initialize ErrorResponse for testing purposes"""
        self.error = error
        self.message = message
        self.status_code = status_code
        self.details = details
        self.request_id = request_id
    
    @staticmethod
    def create_error_response(
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
        request_id: Optional[str] = None
    ) -> JSONResponse:
        """Create standardized error response"""
        error_data = {
            "error": {
                "code": error_code,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "request_id": request_id
            }
        }
        
        if details:
            error_data["error"]["details"] = details
        
        # Don't expose internal details in production
        if settings.ENVIRONMENT == "production":
            if "stack_trace" in error_data.get("error", {}).get("details", {}):
                del error_data["error"]["details"]["stack_trace"]
        
        return JSONResponse(
            status_code=status_code,
            content=error_data
        )


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Comprehensive error handling middleware"""
    
    def __init__(self, app, logger_name: str = "error_handler"):
        super().__init__(app)
        self.logger = get_logger(logger_name)
        self.error_counts: Dict[str, int] = {}
    
    async def dispatch(self, request: Request, call_next):
        """Handle request and catch all exceptions"""
        request_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # Set logging context
        self.logger.set_context(
            request_id=request_id,
            method=request.method,
            endpoint=str(request.url.path),
            ip_address=self._get_client_ip(request),
            user_agent=request.headers.get("user-agent", "")
        )
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        try:
            response = await call_next(request)
            
            # Log successful request
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(
                f"Request completed: {request.method} {request.url.path}",
                status_code=response.status_code,
                duration=duration
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as exc:
            return await self._handle_exception(request, exc, request_id, start_time)
        finally:
            self.logger.clear_context()
    
    async def _handle_exception(
        self, 
        request: Request, 
        exc: Exception, 
        request_id: str,
        start_time: datetime
    ) -> JSONResponse:
        """Handle different types of exceptions"""
        duration = (datetime.now() - start_time).total_seconds()
        
        # HTTP exceptions
        if isinstance(exc, HTTPException):
            return await self._handle_http_exception(exc, request_id, duration)
        
        # Starlette HTTP exceptions
        elif isinstance(exc, StarletteHTTPException):
            return await self._handle_starlette_exception(exc, request_id, duration)
        
        # Validation errors
        elif isinstance(exc, (RequestValidationError, ValidationError)):
            return await self._handle_validation_error(exc, request_id, duration)
        
        # Database errors
        elif self._is_database_error(exc):
            return await self._handle_database_error(exc, request_id, duration)
        
        # Authentication/Authorization errors
        elif self._is_auth_error(exc):
            return await self._handle_auth_error(exc, request_id, duration)
        
        # Rate limiting errors
        elif self._is_rate_limit_error(exc):
            return await self._handle_rate_limit_error(exc, request_id, duration)
        
        # Generic server errors
        else:
            return await self._handle_server_error(exc, request_id, duration)
    
    async def _handle_http_exception(
        self, 
        exc: HTTPException, 
        request_id: str,
        duration: float
    ) -> JSONResponse:
        """Handle FastAPI HTTP exceptions"""
        self.logger.warning(
            f"HTTP exception: {exc.status_code} - {exc.detail}",
            status_code=exc.status_code,
            duration=duration
        )
        
        return ErrorResponse.create_error_response(
            error_code=f"HTTP_{exc.status_code}",
            message=exc.detail,
            status_code=exc.status_code,
            request_id=request_id
        )
    
    async def _handle_starlette_exception(
        self, 
        exc: StarletteHTTPException, 
        request_id: str,
        duration: float
    ) -> JSONResponse:
        """Handle Starlette HTTP exceptions"""
        self.logger.warning(
            f"Starlette HTTP exception: {exc.status_code} - {exc.detail}",
            status_code=exc.status_code,
            duration=duration
        )
        
        return ErrorResponse.create_error_response(
            error_code=f"HTTP_{exc.status_code}",
            message=exc.detail,
            status_code=exc.status_code,
            request_id=request_id
        )
    
    async def _handle_validation_error(
        self, 
        exc: Union[RequestValidationError, ValidationError], 
        request_id: str,
        duration: float
    ) -> JSONResponse:
        """Handle validation errors"""
        self._increment_error_count("validation_error")
        
        error_details = []
        if isinstance(exc, RequestValidationError):
            for error in exc.errors():
                error_details.append({
                    "field": " -> ".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"]
                })
        else:
            for error in exc.errors():
                error_details.append({
                    "field": " -> ".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"]
                })
        
        self.logger.warning(
            "Validation error occurred",
            error_details=error_details,
            duration=duration
        )
        
        return ErrorResponse.create_error_response(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            details={"validation_errors": error_details},
            status_code=422,
            request_id=request_id
        )
    
    async def _handle_database_error(
        self, 
        exc: Exception, 
        request_id: str,
        duration: float
    ) -> JSONResponse:
        """Handle database-related errors"""
        self._increment_error_count("database_error")
        
        self.logger.error(
            "Database error occurred",
            error=exc,
            duration=duration
        )
        
        # Don't expose database details in production
        message = "Database operation failed"
        details = None
        
        if settings.ENVIRONMENT != "production":
            details = {
                "error_type": type(exc).__name__,
                "error_message": str(exc)
            }
        
        return ErrorResponse.create_error_response(
            error_code="DATABASE_ERROR",
            message=message,
            details=details,
            status_code=500,
            request_id=request_id
        )
    
    async def _handle_auth_error(
        self, 
        exc: Exception, 
        request_id: str,
        duration: float
    ) -> JSONResponse:
        """Handle authentication/authorization errors"""
        self._increment_error_count("auth_error")
        
        self.logger.warning(
            "Authentication/Authorization error",
            error=exc,
            duration=duration
        )
        
        return ErrorResponse.create_error_response(
            error_code="AUTH_ERROR",
            message="Authentication or authorization failed",
            status_code=401,
            request_id=request_id
        )
    
    async def _handle_rate_limit_error(
        self, 
        exc: Exception, 
        request_id: str,
        duration: float
    ) -> JSONResponse:
        """Handle rate limiting errors"""
        self._increment_error_count("rate_limit_error")
        
        self.logger.warning(
            "Rate limit exceeded",
            error=exc,
            duration=duration
        )
        
        return ErrorResponse.create_error_response(
            error_code="RATE_LIMIT_EXCEEDED",
            message="Rate limit exceeded. Please try again later.",
            status_code=429,
            request_id=request_id
        )
    
    async def _handle_server_error(
        self, 
        exc: Exception, 
        request_id: str,
        duration: float
    ) -> JSONResponse:
        """Handle generic server errors"""
        self._increment_error_count("server_error")
        
        # Get full traceback for detailed logging
        full_traceback = traceback.format_exc()
        
        self.logger.error(
            f"Unhandled server error: {type(exc).__name__}: {str(exc)}",
            error=exc,
            duration=duration,
            error_type=type(exc).__name__,
            error_message=str(exc),
            full_traceback=full_traceback,
            request_id=request_id
        )
        
        # Also print to console for immediate debugging
        print(f"\n=== DETAILED ERROR DEBUG ===")
        print(f"Request ID: {request_id}")
        print(f"Error Type: {type(exc).__name__}")
        print(f"Error Message: {str(exc)}")
        print(f"Full Traceback:\n{full_traceback}")
        print(f"=== END ERROR DEBUG ===\n")
        
        # Don't expose internal error details in production
        message = "Internal server error"
        details = None
        
        if settings.ENVIRONMENT != "production":
            details = {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "stack_trace": full_traceback
            }
        
        return ErrorResponse.create_error_response(
            error_code="INTERNAL_SERVER_ERROR",
            message=message,
            details=details,
            status_code=500,
            request_id=request_id
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to client host
        return request.client.host if request.client else "unknown"
    
    def _is_database_error(self, exc: Exception) -> bool:
        """Check if exception is database-related"""
        db_error_types = [
            "OperationalError",
            "IntegrityError", 
            "DataError",
            "DatabaseError",
            "SQLAlchemyError",
            "DisconnectionError"
        ]
        return type(exc).__name__ in db_error_types
    
    def _is_auth_error(self, exc: Exception) -> bool:
        """Check if exception is authentication-related"""
        auth_error_types = [
            "TokenExpiredError",
            "TokenInvalidError",
            "JWTError",
            "AuthenticationError",
            "PermissionDenied"
        ]
        return type(exc).__name__ in auth_error_types
    
    def _is_rate_limit_error(self, exc: Exception) -> bool:
        """Check if exception is rate limiting-related"""
        rate_limit_types = [
            "RateLimitExceeded",
            "TooManyRequests"
        ]
        return type(exc).__name__ in rate_limit_types
    
    def _increment_error_count(self, error_type: str):
        """Increment error count for monitoring"""
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
    
    def get_error_stats(self) -> Dict[str, int]:
        """Get error statistics"""
        return self.error_counts.copy()


class HealthCheckMiddleware(BaseHTTPMiddleware):
    """Health check and monitoring middleware"""
    
    def __init__(self, app, logger_name: str = "health_check"):
        super().__init__(app)
        self.logger = get_logger(logger_name)
        self.request_count = 0
        self.error_count = 0
        self.start_time = datetime.now()
    
    async def dispatch(self, request: Request, call_next):
        """Monitor request health metrics"""
        self.request_count += 1
        
        try:
            response = await call_next(request)
            
            # Count errors
            if response.status_code >= 400:
                self.error_count += 1
            
            return response
            
        except Exception as exc:
            self.error_count += 1
            raise
    
    def get_health_stats(self) -> Dict[str, Any]:
        """Get health statistics"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
        
        return {
            "uptime_seconds": uptime,
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate_percent": round(error_rate, 2),
            "status": "healthy" if error_rate < 5 else "degraded" if error_rate < 20 else "unhealthy"
        }


# Exception handlers for specific error types
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation exceptions"""
    logger = get_logger("validation_handler")
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    error_details = []
    for error in exc.errors():
        error_details.append({
            "field": " -> ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        "Request validation failed",
        error_details=error_details,
        request_id=request_id
    )
    
    return ErrorResponse.create_error_response(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"validation_errors": error_details},
        status_code=422,
        request_id=request_id
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger = get_logger("http_handler")
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    logger.warning(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        status_code=exc.status_code,
        request_id=request_id
    )
    
    return ErrorResponse.create_error_response(
        error_code=f"HTTP_{exc.status_code}",
        message=exc.detail,
        status_code=exc.status_code,
        request_id=request_id
    )


# Export middleware classes and handlers
__all__ = [
    'ErrorHandlingMiddleware',
    'HealthCheckMiddleware', 
    'ErrorResponse',
    'validation_exception_handler',
    'http_exception_handler'
]