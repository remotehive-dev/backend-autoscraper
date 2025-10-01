from typing import Dict, Any, Optional, List, Union
from fastapi import HTTPException, status, Depends, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger

from backend.core.clerk_auth import clerk_auth
from backend.core.rbac import Permission, has_permission, get_role_permissions
from backend.core.deps import get_database
from backend.models.mongodb_models import User, UserRole
from backend.database.services import UserService, EmployerService, JobSeekerService

security = HTTPBearer(auto_error=False)

class ClerkMiddleware:
    """Clerk-based authentication middleware for RemoteHive"""
    
    @staticmethod
    async def get_current_user_from_clerk(
        authorization: Optional[str] = Header(None),
        db: AsyncIOMotorDatabase = Depends(get_database)
    ) -> Dict[str, Any]:
        """Get current user from Clerk session token"""
        
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing"
            )
        
        # Extract token from Bearer header
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format"
            )
        
        session_token = authorization.replace("Bearer ", "")
        
        try:
            # Verify token with Clerk
            clerk_user = await clerk_auth.verify_session_token(session_token)
            
            # Check if user exists in local database
            user_service = UserService(db)
            local_user = await user_service.get_user_by_email(clerk_user["email"])
            
            if not local_user:
                # Create local user if doesn't exist
                role = clerk_user["metadata"].get("role", "job_seeker")
                local_user = user_service.create_user(
                    email=clerk_user["email"],
                    first_name=clerk_user["first_name"],
                    last_name=clerk_user["last_name"],
                    phone=clerk_user["phone"],
                    role=role,
                    clerk_user_id=clerk_user["user_id"],
                    is_verified=clerk_user["is_verified"]
                )
            
            # Update local user with Clerk data if needed
            if local_user.clerk_user_id != clerk_user["user_id"]:
                user_service.update_user(
                    local_user.id,
                    clerk_user_id=clerk_user["user_id"],
                    is_verified=clerk_user["is_verified"]
                )
            
            # Return user data in dictionary format
            return {
                "id": str(local_user.id),
                "email": local_user.email,
                "first_name": local_user.first_name,
                "last_name": local_user.last_name,
                "phone": local_user.phone,
                "role": local_user.role.value if hasattr(local_user.role, 'value') else str(local_user.role),
                "is_active": local_user.is_active,
                "is_verified": local_user.is_verified,
                "created_at": local_user.created_at,
                "updated_at": local_user.updated_at,
                "clerk_user_id": local_user.clerk_user_id
            }
            
        except Exception as e:
            logger.error(f"Error authenticating user with Clerk: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
    
    @staticmethod
    def require_permissions(required_permissions: Union[Permission, List[Permission]]):
        """Decorator to require specific permissions with Clerk auth"""
        if isinstance(required_permissions, Permission):
            required_permissions = [required_permissions]
        
        async def permission_checker(
            current_user: Dict[str, Any] = Depends(ClerkMiddleware.get_current_user_from_clerk)
        ) -> Dict[str, Any]:
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
        """Decorator to require specific roles with Clerk auth"""
        if not isinstance(required_roles, list):
            required_roles = [required_roles]
        
        # Convert to string values
        role_strings = []
        for role in required_roles:
            if isinstance(role, UserRole):
                role_strings.append(role.value)
            else:
                role_strings.append(role)
        
        async def role_checker(
            current_user: Dict[str, Any] = Depends(ClerkMiddleware.get_current_user_from_clerk)
        ) -> Dict[str, Any]:
            user_role = current_user.get("role")
            
            if user_role not in role_strings:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required roles: {role_strings}"
                )
            return current_user
        
        return role_checker

# Convenience decorators for Clerk authentication
def clerk_require_employer():
    """Require employer role with Clerk auth"""
    return ClerkMiddleware.require_role(UserRole.EMPLOYER)

def clerk_require_job_seeker():
    """Require job seeker role with Clerk auth"""
    return ClerkMiddleware.require_role(UserRole.JOB_SEEKER)

def clerk_require_admin():
    """Require admin or super admin role with Clerk auth"""
    return ClerkMiddleware.require_role([UserRole.ADMIN, UserRole.SUPER_ADMIN])

def clerk_require_super_admin():
    """Require super admin role with Clerk auth"""
    return ClerkMiddleware.require_role(UserRole.SUPER_ADMIN)

def clerk_require_employer_or_admin():
    """Require employer, admin, or super admin role with Clerk auth"""
    return ClerkMiddleware.require_role([UserRole.EMPLOYER, UserRole.ADMIN, UserRole.SUPER_ADMIN])

# Context-aware authentication for Clerk
class ClerkAuthContext:
    """Clerk authentication context for different user types"""
    
    @staticmethod
    async def get_employer_context(
        current_user: Dict[str, Any] = Depends(clerk_require_employer())
    ):
        """Get employer-specific context with Clerk auth"""
        return {
            "user": current_user,
            "role": "employer",
            "permissions": get_role_permissions("employer")
        }
    
    @staticmethod
    async def get_job_seeker_context(
        current_user: Dict[str, Any] = Depends(clerk_require_job_seeker())
    ):
        """Get job seeker-specific context with Clerk auth"""
        return {
            "user": current_user,
            "role": "job_seeker",
            "permissions": get_role_permissions("job_seeker")
        }
    
    @staticmethod
    async def get_admin_context(
        current_user: Dict[str, Any] = Depends(clerk_require_admin())
    ):
        """Get admin-specific context with Clerk auth"""
        user_role = current_user.get("role")
        return {
            "user": current_user,
            "role": user_role,
            "permissions": get_role_permissions(user_role)
        }