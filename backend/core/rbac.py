from beanie import Document
from pydantic import Field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Set, List, Optional, Callable, Any
from functools import wraps
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.models.mongodb_models import User, UserRole
from backend.core.security import get_current_user
from beanie import PydanticObjectId
import logging
import uuid

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Permission system
class Permission(Enum):
    # User Management
    CREATE_USER = "create_user"
    READ_USER = "read_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    MANAGE_USER_ROLES = "manage_user_roles"
    
    # Job Management
    CREATE_JOB = "create_job"
    READ_JOB = "read_job"
    UPDATE_JOB = "update_job"
    DELETE_JOB = "delete_job"
    APPROVE_JOB = "approve_job"
    FEATURE_JOB = "feature_job"
    
    # Application Management
    CREATE_APPLICATION = "create_application"
    READ_APPLICATION = "read_application"
    UPDATE_APPLICATION = "update_application"
    DELETE_APPLICATION = "delete_application"
    REVIEW_APPLICATION = "review_application"
    
    # Employer Management
    CREATE_EMPLOYER = "create_employer"
    READ_EMPLOYER = "read_employer"
    UPDATE_EMPLOYER = "update_employer"
    DELETE_EMPLOYER = "delete_employer"
    VERIFY_EMPLOYER = "verify_employer"
    
    # Job Seeker Management
    CREATE_JOB_SEEKER = "create_job_seeker"
    READ_JOB_SEEKER = "read_job_seeker"
    UPDATE_JOB_SEEKER = "update_job_seeker"
    DELETE_JOB_SEEKER = "delete_job_seeker"
    
    # Content Management
    CREATE_CONTENT = "create_content"
    READ_CONTENT = "read_content"
    UPDATE_CONTENT = "update_content"
    DELETE_CONTENT = "delete_content"
    PUBLISH_CONTENT = "publish_content"
    
    # System Management
    MANAGE_SYSTEM_SETTINGS = "manage_system_settings"
    VIEW_ADMIN_LOGS = "view_admin_logs"
    MANAGE_SCRAPER = "manage_scraper"
    VIEW_ANALYTICS = "view_analytics"
    
    # Contact Management
    READ_CONTACT_SUBMISSIONS = "read_contact_submissions"
    UPDATE_CONTACT_SUBMISSIONS = "update_contact_submissions"
    DELETE_CONTACT_SUBMISSIONS = "delete_contact_submissions"
    
    # Review Management
    CREATE_REVIEW = "create_review"
    READ_REVIEW = "read_review"
    UPDATE_REVIEW = "update_review"
    DELETE_REVIEW = "delete_review"
    MODERATE_REVIEW = "moderate_review"
    
    # Ad Management
    CREATE_AD = "create_ad"
    READ_AD = "read_ad"
    UPDATE_AD = "update_ad"
    DELETE_AD = "delete_ad"
    MANAGE_AD_REVENUE = "manage_ad_revenue"

# Role-Permission mapping
ROLE_PERMISSIONS: Dict[str, Set[Permission]] = {
    "job_seeker": {
        Permission.CREATE_JOB_SEEKER,
        Permission.READ_JOB_SEEKER,
        Permission.UPDATE_JOB_SEEKER,
        Permission.READ_JOB,
        Permission.CREATE_APPLICATION,
        Permission.READ_APPLICATION,
        Permission.UPDATE_APPLICATION,
        Permission.CREATE_REVIEW,
        Permission.READ_REVIEW,
        Permission.READ_CONTENT,
    },
    
    "employer": {
        Permission.CREATE_EMPLOYER,
        Permission.READ_EMPLOYER,
        Permission.UPDATE_EMPLOYER,
        Permission.CREATE_JOB,
        Permission.READ_JOB,
        Permission.UPDATE_JOB,
        Permission.DELETE_JOB,
        Permission.READ_APPLICATION,
        Permission.UPDATE_APPLICATION,
        Permission.REVIEW_APPLICATION,
        Permission.READ_JOB_SEEKER,
        Permission.READ_CONTENT,
        Permission.CREATE_REVIEW,
        Permission.READ_REVIEW,
    },
    
    "admin": {
        # User management (limited)
        Permission.READ_USER,
        Permission.UPDATE_USER,
        
        # Job management
        Permission.READ_JOB,
        Permission.UPDATE_JOB,
        Permission.DELETE_JOB,
        Permission.APPROVE_JOB,
        Permission.FEATURE_JOB,
        
        # Application management
        Permission.READ_APPLICATION,
        Permission.UPDATE_APPLICATION,
        Permission.DELETE_APPLICATION,
        Permission.REVIEW_APPLICATION,
        
        # Employer management
        Permission.READ_EMPLOYER,
        Permission.UPDATE_EMPLOYER,
        Permission.VERIFY_EMPLOYER,
        
        # Job seeker management
        Permission.READ_JOB_SEEKER,
        Permission.UPDATE_JOB_SEEKER,
        
        # Content management
        Permission.CREATE_CONTENT,
        Permission.READ_CONTENT,
        Permission.UPDATE_CONTENT,
        Permission.DELETE_CONTENT,
        Permission.PUBLISH_CONTENT,
        
        # Contact management
        Permission.READ_CONTACT_SUBMISSIONS,
        Permission.UPDATE_CONTACT_SUBMISSIONS,
        Permission.DELETE_CONTACT_SUBMISSIONS,
        
        # Review management
        Permission.READ_REVIEW,
        Permission.UPDATE_REVIEW,
        Permission.DELETE_REVIEW,
        Permission.MODERATE_REVIEW,
        
        # Ad management
        Permission.READ_AD,
        Permission.UPDATE_AD,
        
        # Limited system access
        Permission.VIEW_ADMIN_LOGS,
        Permission.VIEW_ANALYTICS,
    },
    
    "super_admin": {
        # All permissions - super admin has access to everything
        *[perm for perm in Permission]
    }
}


class RBACManager:
    """Role-Based Access Control Manager"""
    
    def __init__(self):
        self._role_hierarchy = {
            UserRole.SUPER_ADMIN: 5,
            UserRole.ADMIN: 4,
            UserRole.EMPLOYER: 3,
            UserRole.FREELANCER: 2,
            UserRole.JOB_SEEKER: 1,
            UserRole.NEWSLETTER_SUBSCRIBER: 0
        }
    
    def get_role_level(self, role: UserRole) -> int:
        """Get numeric level for role hierarchy"""
        return self._role_hierarchy.get(role, 0)
    
    def has_higher_or_equal_role(self, user_role: UserRole, required_role: UserRole) -> bool:
        """Check if user role has higher or equal level than required role"""
        return self.get_role_level(user_role) >= self.get_role_level(required_role)
    
    async def get_user_permissions(self, user: User) -> List[Permission]:
        """Get all permissions for a user based on their role"""
        try:
            # Get role permissions
            role_permissions = await RolePermission.find(
                RolePermission.role == user.role,
                RolePermission.is_active == True
            ).to_list()
            
            # Get permission details
            permission_ids = [rp.permission_id for rp in role_permissions]
            permissions = await Permission.find(
                Permission.id.in_(permission_ids),
                Permission.is_active == True
            ).to_list()
            
            return permissions
        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return []
    
    async def has_permission(self, user: User, resource: str, action: str) -> bool:
        """Check if user has specific permission"""
        try:
            # Super admin has all permissions
            if user.role == UserRole.SUPER_ADMIN:
                return True
            
            # Get user permissions
            permissions = await self.get_user_permissions(user)
            
            # Check if user has the specific permission
            for permission in permissions:
                if permission.resource == resource and permission.action == action:
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False
    
    async def check_resource_ownership(self, user: User, resource_user_id: PydanticObjectId) -> bool:
        """Check if user owns the resource or has admin privileges"""
        # Admin and super admin can access any resource
        if user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            return True
        
        # User can access their own resources
        return user.id == resource_user_id


# Global RBAC manager instance
rbac_manager = RBACManager()


def require_role(required_role: UserRole):
    """Decorator to require specific role or higher"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from kwargs or dependencies
            current_user = kwargs.get('current_user')
            if not current_user:
                # Try to get from function signature
                for arg in args:
                    if isinstance(arg, User):
                        current_user = arg
                        break
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not rbac_manager.has_higher_or_equal_role(current_user.role, required_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient privileges. Required role: {required_role.value}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(resource: str, action: str):
    """Decorator to require specific permission"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from kwargs or dependencies
            current_user = kwargs.get('current_user')
            if not current_user:
                # Try to get from function signature
                for arg in args:
                    if isinstance(arg, User):
                        current_user = arg
                        break
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            has_perm = await rbac_manager.has_permission(current_user, resource, action)
            if not has_perm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions for {action} on {resource}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_ownership_or_admin():
    """Decorator to require resource ownership or admin privileges"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            resource_user_id = kwargs.get('user_id') or kwargs.get('resource_user_id')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not resource_user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Resource user ID required"
                )
            
            has_access = await rbac_manager.check_resource_ownership(current_user, resource_user_id)
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You can only access your own resources."
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Dependency functions for FastAPI
async def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin or super admin user"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


async def require_super_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require super admin user"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin privileges required"
        )
    return current_user


async def require_employer_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require employer, admin, or super admin user"""
    if current_user.role not in [UserRole.EMPLOYER, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employer privileges required"
        )
    return current_user


async def require_freelancer_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require freelancer, admin, or super admin user"""
    if current_user.role not in [UserRole.FREELANCER, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Freelancer privileges required"
        )
    return current_user


# Utility functions for backward compatibility
def has_permission(user_role: str, permission: Permission) -> bool:
    """Check if a role has a specific permission"""
    permissions_set = ROLE_PERMISSIONS.get(user_role, set())
    return permission in permissions_set


def get_role_permissions(role: str) -> List[Permission]:
    """Get all permissions for a role"""
    permissions_set = ROLE_PERMISSIONS.get(role, set())
    return list(permissions_set)


async def create_user_session(user_id: str, ip_address: str, user_agent: str) -> str:
    """Create a new user session"""
    from backend.database.mongodb_models import UserSession
    from datetime import datetime, timedelta
    import uuid
    
    session_token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=24)  # Session expires in 24 hours
    
    session = UserSession(
        user_id=user_id,
        session_token=session_token,
        ip_address=ip_address,
        user_agent=user_agent,
        is_active=True,
        expires_at=expires_at
    )
    
    await session.insert()
    return session_token


async def end_user_session(session_token: str) -> bool:
    """End a user session"""
    from backend.database.mongodb_models import UserSession
    
    session = await UserSession.find_one(UserSession.session_token == session_token)
    if session:
        session.is_active = False
        session.ended_at = datetime.utcnow()
        await session.save()
        return True
    return False