#!/usr/bin/env python3
"""
Rate Limiter Implementation
Provides rate limiting functionality for API endpoints
"""

import time
from typing import Dict, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta
from loguru import logger


class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        # Store request timestamps for each client
        self._requests: Dict[str, deque] = defaultdict(deque)
        self._blocked_until: Dict[str, datetime] = {}
    
    def is_allowed(
        self, 
        client_id: str, 
        max_requests: int = 100, 
        window_seconds: int = 3600,
        block_duration_seconds: int = 300
    ) -> bool:
        """
        Check if a request is allowed for the given client
        
        Args:
            client_id: Unique identifier for the client (IP, user ID, etc.)
            max_requests: Maximum number of requests allowed in the window
            window_seconds: Time window in seconds
            block_duration_seconds: How long to block after exceeding limit
        
        Returns:
            True if request is allowed, False otherwise
        """
        now = datetime.utcnow()
        
        # Check if client is currently blocked
        if client_id in self._blocked_until:
            if now < self._blocked_until[client_id]:
                return False
            else:
                # Block period expired, remove from blocked list
                del self._blocked_until[client_id]
        
        # Get request history for this client
        requests = self._requests[client_id]
        
        # Remove old requests outside the window
        cutoff_time = now - timedelta(seconds=window_seconds)
        while requests and requests[0] < cutoff_time:
            requests.popleft()
        
        # Check if we're within the limit
        if len(requests) >= max_requests:
            # Block the client
            self._blocked_until[client_id] = now + timedelta(seconds=block_duration_seconds)
            logger.warning(f"Rate limit exceeded for client {client_id}. Blocked until {self._blocked_until[client_id]}")
            return False
        
        # Add current request
        requests.append(now)
        return True
    
    def get_remaining_requests(
        self, 
        client_id: str, 
        max_requests: int = 100, 
        window_seconds: int = 3600
    ) -> int:
        """
        Get the number of remaining requests for a client
        
        Args:
            client_id: Unique identifier for the client
            max_requests: Maximum number of requests allowed in the window
            window_seconds: Time window in seconds
        
        Returns:
            Number of remaining requests
        """
        now = datetime.utcnow()
        requests = self._requests[client_id]
        
        # Remove old requests outside the window
        cutoff_time = now - timedelta(seconds=window_seconds)
        while requests and requests[0] < cutoff_time:
            requests.popleft()
        
        return max(0, max_requests - len(requests))
    
    def get_reset_time(
        self, 
        client_id: str, 
        window_seconds: int = 3600
    ) -> Optional[datetime]:
        """
        Get when the rate limit will reset for a client
        
        Args:
            client_id: Unique identifier for the client
            window_seconds: Time window in seconds
        
        Returns:
            DateTime when the limit resets, or None if no requests
        """
        requests = self._requests[client_id]
        if not requests:
            return None
        
        # The limit resets when the oldest request expires
        return requests[0] + timedelta(seconds=window_seconds)
    
    def is_blocked(self, client_id: str) -> bool:
        """
        Check if a client is currently blocked
        
        Args:
            client_id: Unique identifier for the client
        
        Returns:
            True if client is blocked, False otherwise
        """
        if client_id not in self._blocked_until:
            return False
        
        now = datetime.utcnow()
        if now >= self._blocked_until[client_id]:
            # Block period expired
            del self._blocked_until[client_id]
            return False
        
        return True
    
    def get_block_expiry(self, client_id: str) -> Optional[datetime]:
        """
        Get when a client's block will expire
        
        Args:
            client_id: Unique identifier for the client
        
        Returns:
            DateTime when block expires, or None if not blocked
        """
        return self._blocked_until.get(client_id)
    
    def clear_client(self, client_id: str) -> None:
        """
        Clear all rate limiting data for a client
        
        Args:
            client_id: Unique identifier for the client
        """
        if client_id in self._requests:
            del self._requests[client_id]
        if client_id in self._blocked_until:
            del self._blocked_until[client_id]
    
    def clear_all(self) -> None:
        """
        Clear all rate limiting data
        """
        self._requests.clear()
        self._blocked_until.clear()


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# Rate limiting configurations for different endpoints
RATE_LIMITS = {
    "login": {"max_requests": 5, "window_seconds": 300, "block_duration_seconds": 900},  # 5 attempts per 5 minutes
    "register": {"max_requests": 3, "window_seconds": 3600, "block_duration_seconds": 3600},  # 3 attempts per hour
    "password_reset": {"max_requests": 3, "window_seconds": 3600, "block_duration_seconds": 3600},  # 3 attempts per hour
    "api_general": {"max_requests": 1000, "window_seconds": 3600, "block_duration_seconds": 300},  # 1000 requests per hour
    "api_heavy": {"max_requests": 100, "window_seconds": 3600, "block_duration_seconds": 600},  # 100 requests per hour for heavy operations
}


def check_rate_limit(client_id: str, endpoint_type: str = "api_general") -> bool:
    """
    Convenience function to check rate limit for an endpoint
    
    Args:
        client_id: Unique identifier for the client
        endpoint_type: Type of endpoint (login, register, etc.)
    
    Returns:
        True if request is allowed, False otherwise
    """
    rate_limiter = get_rate_limiter()
    config = RATE_LIMITS.get(endpoint_type, RATE_LIMITS["api_general"])
    
    return rate_limiter.is_allowed(
        client_id=client_id,
        max_requests=config["max_requests"],
        window_seconds=config["window_seconds"],
        block_duration_seconds=config["block_duration_seconds"]
    )