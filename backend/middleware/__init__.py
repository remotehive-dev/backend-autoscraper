#!/usr/bin/env python3
"""
Middleware package for FastAPI application
"""

from backend.middleware.rate_limiting import (
    RateLimitingMiddleware,
    create_rate_limit_dependency,
    login_rate_limit,
    register_rate_limit,
    password_reset_rate_limit,
    api_rate_limit,
    heavy_api_rate_limit
)

__all__ = [
    "RateLimitingMiddleware",
    "create_rate_limit_dependency",
    "login_rate_limit",
    "register_rate_limit",
    "password_reset_rate_limit",
    "api_rate_limit",
    "heavy_api_rate_limit"
]