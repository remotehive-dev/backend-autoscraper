from datetime import datetime, timedelta
from typing import List, Optional, Union, Callable, Dict, Any
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from functools import wraps

from backend.core.local_auth import get_current_user, verify_token
from backend.core.rbac import Permission, has_permission, get_role_permissions
from backend.core.database import get_db
from backend.models.mongodb_models import User, UserRole

security = HTTPBearer()

class AuthMiddleware:
    """Enhanced authentication middleware with RBAC support"""
    
    @staticmethod
    def require_permissions(required_permissions: Union[Permission, List[Permission]]):
        """Decorator to require specific permissions"""
        if isinstance(required_permissions, Permission):
            required_permissions = [required_permissions]
        
        def permission_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
            user_role = current_user.get("role")
            
            # Check if user has any of the required permissions
            has_access = any(
                has_permission(user_role, perm) for perm in required_permissions
            )
            
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {[p.value for p in required_permissions]}"
                )
            return current_user
        
        return permission_checker
    
    @staticmethod
    def require_role(required_roles: Union[str, UserRole, List[Union[str, UserRole]]]):
        """Decorator to require specific roles"""
        if not isinstance(required_roles, list):
            required_roles = [required_roles]
        
        # Convert to string values
        role_strings = []
        for role in required_roles:
            if isinstance(role, UserRole):
                role_strings.append(role.value)
            else:
                role_strings.append(role)
        
        def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
            user_role = current_user.get("role")
            
            if user_role not in role_strings:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required roles: {role_strings}"
                )
            return current_user
        
        return role_checker
    
    @staticmethod
    def require_admin_or_owner(resource_user_id_field: str = "user_id"):
        """Decorator to require admin role or resource ownership"""
        def admin_or_owner_checker(
            request: Request,
            current_user: Dict[str, Any] = Depends(get_current_user)
        ) -> Dict[str, Any]:
            user_role = current_user.get("role")
            
            # Admin and super_admin can access anything
            if user_role in ["admin", "super_admin"]:
                return current_user
            
            # Check if user owns the resource
            resource_user_id = None
            
            # Try to get user_id from path parameters
            if hasattr(request, 'path_params') and resource_user_id_field in request.path_params:
                resource_user_id = request.path_params[resource_user_id_field]
            
            # Try to get user_id from query parameters
            elif hasattr(request, 'query_params') and resource_user_id_field in request.query_params:
                resource_user_id = request.query_params[resource_user_id_field]
            
            if resource_user_id and resource_user_id == current_user.get("id"):
                return current_user
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Admin role or resource ownership required."
            )
        
        return admin_or_owner_checker

# Convenience decorators for common role requirements
def require_super_admin():
    """Require super admin role"""
    return AuthMiddleware.require_role(UserRole.SUPER_ADMIN)

def require_admin():
    """Require admin or super admin role"""
    return AuthMiddleware.require_role([UserRole.ADMIN, UserRole.SUPER_ADMIN])

def require_employer():
    """Require employer role"""
    return AuthMiddleware.require_role(UserRole.EMPLOYER)

def require_job_seeker():
    """Require job seeker role"""
    return AuthMiddleware.require_role(UserRole.JOB_SEEKER)

def require_employer_or_admin():
    """Require employer, admin, or super admin role"""
    return AuthMiddleware.require_role([UserRole.EMPLOYER, UserRole.ADMIN, UserRole.SUPER_ADMIN])

# Permission-based decorators
def require_user_management():
    """Require user management permissions"""
    return AuthMiddleware.require_permissions([
        Permission.CREATE_USER,
        Permission.READ_USER,
        Permission.UPDATE_USER,
        Permission.DELETE_USER
    ])

def require_job_management():
    """Require job management permissions"""
    return AuthMiddleware.require_permissions([
        Permission.CREATE_JOB,
        Permission.READ_JOB,
        Permission.UPDATE_JOB,
        Permission.DELETE_JOB
    ])

def require_content_management():
    """Require content management permissions"""
    return AuthMiddleware.require_permissions([
        Permission.CREATE_CONTENT,
        Permission.READ_CONTENT,
        Permission.UPDATE_CONTENT,
        Permission.DELETE_CONTENT
    ])

def require_system_management():
    """Require system management permissions"""
    return AuthMiddleware.require_permissions([
        Permission.MANAGE_SYSTEM_SETTINGS,
        Permission.VIEW_ADMIN_LOGS,
        Permission.MANAGE_SCRAPER
    ])

# Context-aware authentication
class AuthContext:
    """Authentication context for different user types"""
    
    @staticmethod
    def get_employer_context(current_user: Dict[str, Any] = Depends(require_employer())):
        """Get employer-specific context"""
        return {
            "user": current_user,
            "role": "employer",
            "permissions": get_role_permissions("employer")
        }
    
    @staticmethod
    def get_job_seeker_context(current_user: Dict[str, Any] = Depends(require_job_seeker())):
        """Get job seeker-specific context"""
        return {
            "user": current_user,
            "role": "job_seeker",
            "permissions": get_role_permissions("job_seeker")
        }
    
    @staticmethod
    def get_admin_context(current_user: Dict[str, Any] = Depends(require_admin())):
        """Get admin-specific context"""
        user_role = current_user.get("role")
        return {
            "user": current_user,
            "role": user_role,
            "permissions": get_role_permissions(user_role)
        }

# Rate limiting and security
class SecurityMiddleware:
    """Security middleware for rate limiting and monitoring"""
    
    @staticmethod
    async def log_login_attempt(db: AsyncIOMotorDatabase, email: str, ip_address: str, user_agent: str, success: bool, failure_reason: str = None):
        """Log login attempt for security monitoring"""
        from backend.database.mongodb_models import LoginAttempt
        
        attempt = LoginAttempt(
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason
        )
        
        await attempt.insert()
    
    @staticmethod
    async def check_rate_limit(db: AsyncIOMotorDatabase, email: str, ip_address: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
        """Check if login attempts exceed rate limit"""
        from backend.database.mongodb_models import LoginAttempt
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
        
        recent_attempts = await LoginAttempt.find({
            "email": email,
            "ip_address": ip_address,
            "attempted_at": {"$gt": cutoff_time},
            "success": False
        }).count()
        
        return recent_attempts < max_attempts