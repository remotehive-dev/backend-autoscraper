#!/usr/bin/env python3
"""
Rate Limiting Middleware for FastAPI
Provides rate limiting functionality for authentication endpoints
"""

import time
from typing import Callable, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from backend.core.rate_limiter import get_rate_limiter, RATE_LIMITS


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware that applies different limits based on endpoint patterns
    """
    
    def __init__(self, app, enable_rate_limiting: bool = True):
        super().__init__(app)
        self.enable_rate_limiting = enable_rate_limiting
        self.rate_limiter = get_rate_limiter()
        
        # Define endpoint patterns and their rate limit types
        self.endpoint_patterns = {
            "/api/v1/auth/login": "login",
            "/api/v1/auth/public/login": "login",
            "/api/v1/auth/admin/login": "login",
            "/api/v1/auth/register": "register",
            "/api/v1/auth/public/register": "register",
            "/api/v1/auth/password-reset": "password_reset",
            "/api/v1/auth/password-reset-confirm": "password_reset",
        }
    
    def get_client_identifier(self, request: Request) -> str:
        """
        Get a unique identifier for the client
        Uses IP address as primary identifier
        """
        # Try to get real IP from headers (in case of proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        return client_ip
    
    def get_endpoint_type(self, path: str) -> str:
        """
        Determine the rate limit type based on the endpoint path
        """
        # Check exact matches first
        if path in self.endpoint_patterns:
            return self.endpoint_patterns[path]
        
        # Check for pattern matches
        for pattern, limit_type in self.endpoint_patterns.items():
            if path.startswith(pattern.rstrip("*")):
                return limit_type
        
        # Default to general API limits
        return "api_general"
    
    def create_rate_limit_response(self, client_id: str, endpoint_type: str) -> JSONResponse:
        """
        Create a rate limit exceeded response with helpful headers
        """
        config = RATE_LIMITS.get(endpoint_type, RATE_LIMITS["api_general"])
        
        # Get rate limit info
        remaining = self.rate_limiter.get_remaining_requests(
            client_id, 
            config["max_requests"], 
            config["window_seconds"]
        )
        
        reset_time = self.rate_limiter.get_reset_time(
            client_id, 
            config["window_seconds"]
        )
        
        headers = {
            "X-RateLimit-Limit": str(config["max_requests"]),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Window": str(config["window_seconds"]),
        }
        
        if reset_time:
            headers["X-RateLimit-Reset"] = str(int(reset_time.timestamp()))
        
        # Check if client is blocked
        block_expiry = self.rate_limiter.get_block_expiry(client_id)
        if block_expiry:
            headers["Retry-After"] = str(int((block_expiry.timestamp() - time.time())))
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "Rate limit exceeded. Too many requests.",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "retry_after": headers.get("Retry-After"),
                "limit_info": {
                    "max_requests": config["max_requests"],
                    "window_seconds": config["window_seconds"],
                    "remaining": remaining
                }
            },
            headers=headers
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process the request and apply rate limiting
        """
        # Skip rate limiting if disabled
        if not self.enable_rate_limiting:
            return await call_next(request)
        
        # Skip rate limiting for certain paths (health checks, docs, etc.)
        skip_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/metrics",
            "/favicon.ico"
        ]
        
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)
        
        # Get client identifier and endpoint type
        client_id = self.get_client_identifier(request)
        endpoint_type = self.get_endpoint_type(request.url.path)
        
        # Check rate limit
        config = RATE_LIMITS.get(endpoint_type, RATE_LIMITS["api_general"])
        
        is_allowed = self.rate_limiter.is_allowed(
            client_id=client_id,
            max_requests=config["max_requests"],
            window_seconds=config["window_seconds"],
            block_duration_seconds=config["block_duration_seconds"]
        )
        
        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for client {client_id} on endpoint {request.url.path} "
                f"(type: {endpoint_type})"
            )
            return self.create_rate_limit_response(client_id, endpoint_type)
        
        # Process the request
        response = await call_next(request)
        
        # Add rate limit headers to successful responses
        if response.status_code < 400:
            remaining = self.rate_limiter.get_remaining_requests(
                client_id, 
                config["max_requests"], 
                config["window_seconds"]
            )
            
            reset_time = self.rate_limiter.get_reset_time(
                client_id, 
                config["window_seconds"]
            )
            
            response.headers["X-RateLimit-Limit"] = str(config["max_requests"])
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Window"] = str(config["window_seconds"])
            
            if reset_time:
                response.headers["X-RateLimit-Reset"] = str(int(reset_time.timestamp()))
        
        return response


def create_rate_limit_dependency(endpoint_type: str = "api_general"):
    """
    Create a FastAPI dependency for rate limiting specific endpoints
    
    Args:
        endpoint_type: Type of endpoint for rate limiting configuration
    
    Returns:
        FastAPI dependency function
    """
    async def rate_limit_dependency(request: Request):
        rate_limiter = get_rate_limiter()
        
        # Get client identifier
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limit
        config = RATE_LIMITS.get(endpoint_type, RATE_LIMITS["api_general"])
        
        is_allowed = rate_limiter.is_allowed(
            client_id=client_ip,
            max_requests=config["max_requests"],
            window_seconds=config["window_seconds"],
            block_duration_seconds=config["block_duration_seconds"]
        )
        
        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for client {client_ip} on endpoint {request.url.path} "
                f"(type: {endpoint_type})"
            )
            
            # Get additional info for error response
            remaining = rate_limiter.get_remaining_requests(
                client_ip, 
                config["max_requests"], 
                config["window_seconds"]
            )
            
            block_expiry = rate_limiter.get_block_expiry(client_ip)
            retry_after = None
            if block_expiry:
                retry_after = int((block_expiry.timestamp() - time.time()))
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "message": "Rate limit exceeded. Too many requests.",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": retry_after,
                    "limit_info": {
                        "max_requests": config["max_requests"],
                        "window_seconds": config["window_seconds"],
                        "remaining": remaining
                    }
                },
                headers={
                    "Retry-After": str(retry_after) if retry_after else "300"
                }
            )
        
        return True
    
    return rate_limit_dependency


# Pre-configured dependencies for common endpoints
login_rate_limit = create_rate_limit_dependency("login")
register_rate_limit = create_rate_limit_dependency("register")
password_reset_rate_limit = create_rate_limit_dependency("password_reset")
api_rate_limit = create_rate_limit_dependency("api_general")
heavy_api_rate_limit = create_rate_limit_dependency("api_heavy")