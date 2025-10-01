#!/usr/bin/env python3
"""
Rate Limiting Middleware
Enterprise-grade rate limiting for autoscraper service
"""

import time
import redis
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from config.settings import get_settings

settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based rate limiting middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.enabled = settings.RATE_LIMIT_ENABLED
        self.requests_per_window = settings.RATE_LIMIT_REQUESTS_PER_WINDOW
        self.window_seconds = settings.RATE_LIMIT_WINDOW_SECONDS
        
        # Initialize Redis connection
        if self.enabled:
            try:
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Rate limiting enabled with Redis backend")
            except Exception as e:
                logger.warning(f"Redis connection failed, disabling rate limiting: {e}")
                self.enabled = False
                self.redis_client = None
        else:
            self.redis_client = None
            logger.info("Rate limiting disabled")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting"""
        
        if not self.enabled or not self.redis_client:
            return await call_next(request)
        
        # Skip rate limiting for health checks and metrics
        if self._is_exempt_endpoint(request.url.path):
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        try:
            # Check rate limit
            if not await self._check_rate_limit(client_id):
                return self._rate_limit_exceeded_response(client_id)
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            remaining = await self._get_remaining_requests(client_id)
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_window)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Window"] = str(self.window_seconds)
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # Continue without rate limiting on error
            return await call_next(request)
    
    def _is_exempt_endpoint(self, path: str) -> bool:
        """Check if endpoint is exempt from rate limiting"""
        exempt_paths = [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json"
        ]
        
        for exempt_path in exempt_paths:
            if path.startswith(exempt_path):
                return True
        
        return False
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Try to get user ID from request state (set by auth middleware)
        if hasattr(request.state, 'user_id') and request.state.user_id:
            return f"user:{request.state.user_id}"
        
        # Fallback to IP address
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers (behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        return request.client.host if request.client else "unknown"
    
    async def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client is within rate limit"""
        try:
            current_time = int(time.time())
            window_start = current_time - self.window_seconds
            
            # Redis key for this client's requests
            key = f"rate_limit:{client_id}"
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, self.window_seconds + 1)
            
            results = pipe.execute()
            current_requests = results[1]  # Count result
            
            # Check if limit exceeded
            return current_requests < self.requests_per_window
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Allow request on error
            return True
    
    async def _get_remaining_requests(self, client_id: str) -> int:
        """Get remaining requests for client"""
        try:
            current_time = int(time.time())
            window_start = current_time - self.window_seconds
            
            key = f"rate_limit:{client_id}"
            
            # Count current requests in window
            current_requests = self.redis_client.zcount(key, window_start, current_time)
            
            return max(0, self.requests_per_window - current_requests)
            
        except Exception as e:
            logger.error(f"Get remaining requests error: {e}")
            return self.requests_per_window
    
    def _rate_limit_exceeded_response(self, client_id: str) -> JSONResponse:
        """Return rate limit exceeded response"""
        logger.warning(f"Rate limit exceeded for client: {client_id}")
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "detail": f"Too many requests. Limit: {self.requests_per_window} requests per {self.window_seconds} seconds",
                "retry_after": self.window_seconds
            },
            headers={
                "Retry-After": str(self.window_seconds),
                "X-RateLimit-Limit": str(self.requests_per_window),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Window": str(self.window_seconds)
            }
        )


class RateLimitManager:
    """Rate limit management utilities"""
    
    def __init__(self):
        self.redis_client = None
        if settings.RATE_LIMIT_ENABLED:
            try:
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True
                )
            except Exception as e:
                logger.error(f"Failed to initialize rate limit manager: {e}")
    
    async def reset_client_limit(self, client_id: str) -> bool:
        """Reset rate limit for specific client"""
        if not self.redis_client:
            return False
        
        try:
            key = f"rate_limit:{client_id}"
            self.redis_client.delete(key)
            logger.info(f"Reset rate limit for client: {client_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to reset rate limit for {client_id}: {e}")
            return False
    
    async def get_client_stats(self, client_id: str) -> Dict[str, Any]:
        """Get rate limit stats for client"""
        if not self.redis_client:
            return {}
        
        try:
            current_time = int(time.time())
            window_start = current_time - settings.RATE_LIMIT_WINDOW
            
            key = f"rate_limit:{client_id}"
            
            current_requests = self.redis_client.zcount(key, window_start, current_time)
            remaining = max(0, settings.RATE_LIMIT_REQUESTS - current_requests)
            
            return {
                "client_id": client_id,
                "current_requests": current_requests,
                "remaining_requests": remaining,
                "limit": settings.RATE_LIMIT_REQUESTS,
                "window_seconds": settings.RATE_LIMIT_WINDOW,
                "reset_time": current_time + settings.RATE_LIMIT_WINDOW
            }
        except Exception as e:
            logger.error(f"Failed to get client stats for {client_id}: {e}")
            return {}


# Rate limit manager instance
rate_limit_manager = RateLimitManager()