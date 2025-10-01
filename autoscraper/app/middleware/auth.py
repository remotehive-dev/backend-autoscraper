#!/usr/bin/env python3
"""
JWT Authentication Middleware
Enterprise-grade authentication for autoscraper service
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from app.utils.jwt_auth import get_jwt_manager, JWTError, TokenExpiredError, TokenInvalidError
from config.settings import get_settings

settings = get_settings()


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT Authentication Middleware"""
    
    # Public endpoints that don't require authentication
    PUBLIC_ENDPOINTS = {
        "/",
        "/health",
        "/health/live",
        "/health/ready",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/autoscraper/job-boards"
    }
    
    def __init__(self, app):
        super().__init__(app)
        self.jwt_manager = get_jwt_manager()
    
    async def dispatch(self, request: Request, call_next):
        """Process request and validate JWT token"""
        
        # Skip authentication for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Extract and validate JWT token
        try:
            token = self._extract_token(request)
            if token:
                payload = self._decode_token(token)
                if payload:
                    # Add user info to request state
                    request.state.user = payload
                    request.state.user_id = payload.get("sub")  # JWT standard subject field
                    request.state.user_email = payload.get("email")
                    
                    # Handle both 'role' (singular) and 'roles' (plural) fields
                    role = payload.get("role")
                    roles = payload.get("roles", [])
                    if role and not roles:
                        roles = [role]  # Convert single role to list
                    request.state.user_roles = roles
                    
                    request.state.token_type = payload.get("type")
                    request.state.service_name = payload.get("service")  # For service tokens
                    
                    # Log successful authentication
                    logger.debug(f"Authenticated user/service: {payload.get('sub')} for {request.url.path}")
                else:
                    # Invalid token - let the endpoint dependency handle it
                    request.state.user = None
            else:
                # No token provided - let the endpoint dependency handle it
                request.state.user = None
            
        except Exception as e:
            logger.warning(f"Authentication middleware error: {e}")
            request.state.user = None
        
        return await call_next(request)
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public"""
        # Exact match
        if path in self.PUBLIC_ENDPOINTS:
            return True
        
        # Pattern matching for health checks and metrics
        if path.startswith("/health") or path.startswith("/metrics"):
            return True
        
        # OpenAPI documentation endpoints
        if path in ["/docs", "/redoc", "/openapi.json"]:
            return True
        
        return False
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from request"""
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.split(" ")[1]
        
        # Check cookie (fallback)
        token = request.cookies.get("access_token")
        if token:
            return token
        
        return None
    
    def _decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode and validate JWT token using centralized JWT manager"""
        try:
            payload = self.jwt_manager.decode_token(token)
            
            # For user tokens, validate required fields (flexible for service tokens)
            token_type = payload.get("type")
            if token_type == "access":
                # User access tokens should have subject (user ID)
                if "sub" not in payload:
                    logger.warning("Access token missing subject field")
                    return None
            elif token_type == "service":
                # Service tokens should have service name
                if "service" not in payload:
                    logger.warning("Service token missing service field")
                    return None
            
            return payload
            
        except TokenExpiredError:
            logger.warning("Token has expired")
            return None
        except TokenInvalidError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except JWTError as e:
            logger.warning(f"JWT error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected token decode error: {e}")
            return None
    
    def _unauthorized_response(self, message: str) -> JSONResponse:
        """Return unauthorized response"""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "Unauthorized",
                "detail": message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )


class JWTTokenManager:
    """JWT token management utilities - wrapper around centralized JWT manager"""
    
    def __init__(self):
        self.jwt_manager = get_jwt_manager()
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create JWT access token"""
        # Convert legacy data format to new format
        user_id = data.get("user_id") or data.get("sub")
        if not user_id:
            raise ValueError("Token data must contain user_id or sub")
        
        return self.jwt_manager.create_access_token(
            subject=str(user_id),
            additional_claims={
                k: v for k, v in data.items() 
                if k not in ["user_id", "sub", "exp", "iat", "type"]
            }
        )
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token"""
        try:
            payload = self.jwt_manager.decode_token(token)
            # Convert new format back to legacy format for compatibility
            if "sub" in payload:
                payload["user_id"] = payload["sub"]
            return payload
        except (JWTError, Exception):
            return None
    
    def refresh_token(self, token: str) -> Optional[str]:
        """Refresh JWT token"""
        try:
            payload = self.jwt_manager.decode_token(token)
            if not payload or payload.get("type") != "access":
                return None
            
            # Create new access token with same subject
            user_id = payload.get("sub")
            if not user_id:
                return None
                
            additional_claims = {
                k: v for k, v in payload.items() 
                if k not in ["sub", "exp", "iat", "type"]
            }
            
            return self.jwt_manager.create_access_token(
                subject=user_id,
                additional_claims=additional_claims
            )
        except (JWTError, Exception):
            return None


# Token manager instance
token_manager = JWTTokenManager()


# Dependency functions for FastAPI
async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user from request state (optional - returns None if no user)"""
    try:
        return getattr(request.state, 'user', None)
    except Exception as e:
        logger.warning(f"Optional auth failed: {e}")
        return None


async def require_auth(request: Request) -> Dict[str, Any]:
    """Require authentication - raises HTTPException if no valid user"""
    try:
        user = getattr(request.state, 'user', None)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def require_admin(request: Request) -> Dict[str, Any]:
    """Require admin authentication - raises HTTPException if no valid admin user"""
    try:
        user = await require_auth(request)
        user_roles = getattr(request.state, 'user_roles', [])
        
        # Check if user has admin or super_admin role
        if not any(role.lower() in ['admin', 'super_admin'] for role in user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin authentication failed"
        )


def _extract_token_from_request(request: Request) -> Optional[str]:
    """Extract JWT token from request headers"""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    
    if not auth_header.startswith("Bearer "):
        return None
    
    return auth_header[7:]  # Remove "Bearer " prefix


# Dependency function for getting current user
from fastapi.security import HTTPBearer
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Extract and validate current user from JWT token
    Used as a FastAPI dependency in protected endpoints
    """
    try:
        token = credentials.credentials
        
        # Use the centralized JWT manager to decode token
        jwt_manager = get_jwt_manager()
        payload = jwt_manager.decode_token(token)
        
        # Extract user information
        user_id = payload.get("sub")
        username = payload.get("username")
        email = payload.get("email")
        roles = payload.get("roles", [])
        
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing user ID"
            )
        
        return {
            "user_id": user_id,
            "username": username,
            "email": email,
            "roles": roles,
            "token": token
        }
        
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired"
        )
    except TokenInvalidError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
    except Exception as e:
        logger.error(f"Error validating user token: {e}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )