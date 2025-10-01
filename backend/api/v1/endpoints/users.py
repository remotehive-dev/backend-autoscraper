from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime

from backend.database.database import get_mongodb_session as get_db
from backend.models.mongodb_models import User, UserRole
from backend.database.services import UserService
from backend.core.auth import get_current_user
from backend.core.security import get_password_hash, verify_password
from backend.core.audit_logger import get_audit_logger
from backend.schemas.user import User as UserResponse, UserUpdate, UserPasswordUpdate as PasswordUpdate, UserUpdate as UserUpdateRequest

router = APIRouter()



@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user's profile"""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update current user's profile"""
    try:
        user_service = UserService(db)
        
        # Update user fields using MongoDB service
        update_data = user_update.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        updated_user = await UserService.update_user(db, str(current_user.get('id')), **update_data)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"User profile updated: {updated_user.email}")
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user profile {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

@router.put("/me/password")
async def update_current_user_password(
    password_update: PasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update current user's password"""
    try:
        user_service = UserService(db)
        
        # Verify current password
        if not verify_password(password_update.current_password, current_user.get('hashed_password')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password"
            )
        
        # Update password using MongoDB service
        hashed_password = get_password_hash(password_update.new_password)
        updated_user = await UserService.update_user(
            db,
            str(current_user.get('id')), 
            hashed_password=hashed_password,
            updated_at=datetime.utcnow()
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"Password updated for user: {updated_user.email}")
        return {"message": "Password updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update password for {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )

@router.delete("/me")
async def delete_current_user_account(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Delete current user's account (soft delete)"""
    try:
        user_service = UserService(db)
        
        # Soft delete by deactivating account using MongoDB service
        updated_user = await UserService.update_user(
            db,
            str(current_user.get('id')), 
            is_active=False,
            updated_at=datetime.utcnow()
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"User account deactivated: {updated_user.email}")
        return {"message": "Account deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate account {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate account"
        )

@router.get("/", response_model=List[UserResponse])
async def get_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get list of users (admin only)"""
    try:
        # Check if user has admin privileges
        if current_user.get('role') != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        skip = (page - 1) * per_page
        
        # Get users using MongoDB service
        users = await UserService.get_users(db, skip=skip, limit=per_page, role=role)
        
        logger.info(f"Retrieved {len(users)} users")
        return users
        
    except Exception as e:
        logger.error(f"Failed to get users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )

@router.get("/admin/users", response_model=List[UserResponse])
async def get_admin_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    role: Optional[str] = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of users for admin panel."""
    try:
        # Check if user has admin privileges (allow both admin and super_admin)
        user_role = current_user.get('role')
        if user_role not in ["admin", "super_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        # Get users with filters using MongoDB service
        users = await UserService.get_users(db, skip=skip, limit=limit, role=role)
        
        logger.info(f"Retrieved {len(users)} users for admin panel")
        return users
        
    except Exception as e:
        logger.error(f"Error retrieving admin users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get user by ID (admin only)"""
    try:
        # Check if user has admin privileges
        if current_user.get('role') != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        user = await UserService.get_user_by_id(db, user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user"
        )

@router.put("/{user_id}", response_model=UserResponse)
async def update_user_by_id(
    user_id: str,
    user_update: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update user by ID (admin only)"""
    try:
        # Check if user has admin privileges
        if current_user.get('role') != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        # Check if user exists
        existing_user = await UserService.get_user_by_id(db, user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update user using MongoDB service
        update_data = user_update.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        
        updated_user = await UserService.update_user(db, user_id, **update_data)
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"User {user_id} updated by admin {current_user.get('email')}")
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )

@router.delete("/{user_id}")
async def delete_user_by_id(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Delete user by ID (admin only)"""
    try:
        # Check if user has admin privileges
        if current_user.get('role') != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        # Check if user exists
        existing_user = await UserService.get_user_by_id(db, user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Soft delete by deactivating account using MongoDB service
        updated_user = await UserService.update_user(
            db, 
            user_id, 
            is_active=False,
            updated_at=datetime.utcnow()
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"User {user_id} deactivated by admin {current_user.get('email')}")
        return {"message": "User deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user"
        )

# ============================================================================
# ADMIN ROLE MANAGEMENT ENDPOINTS
# ============================================================================

@router.put("/admin/{user_id}/role")
async def assign_user_role(
    user_id: str,
    role_data: Dict[str, str],
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Assign role to user (admin only)"""
    try:
        # Check if user has admin privileges
        current_user_role = current_user.get('role')
        if current_user_role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN, "admin", "super_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        new_role = role_data.get("role")
        if not new_role or new_role not in ["job_seeker", "employer", "admin", "super_admin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role. Must be one of: job_seeker, employer, admin, super_admin"
            )
        
        # Only super admin can assign super_admin role
        if new_role == "super_admin" and current_user_role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super admin can assign super admin role"
            )
        
        # Check if target user exists
        existing_user = await UserService.get_user_by_id(db, user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update user role
        updated_user = await UserService.update_user(
            db, 
            user_id, 
            role=new_role,
            updated_at=datetime.utcnow()
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Log admin action for role assignment
        audit_logger = get_audit_logger()
        await audit_logger.log_admin_action(
            admin_user_id=str(current_user.get('id')),
            admin_email=current_user.get('email'),
            action="role_assignment",
            target_user_id=user_id,
            target_email=existing_user.email,
            details={"old_role": existing_user.role, "new_role": new_role}
        )
        
        logger.info(f"User {user_id} role changed to {new_role} by admin {current_user.get('email')}")
        return {
            "message": f"User role updated to {new_role}",
            "user_id": user_id,
            "new_role": new_role
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign role to user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign role"
        )

@router.get("/admin/{user_id}/permissions")
async def get_user_permissions(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get user permissions based on role (admin only)"""
    try:
        # Check if user has admin privileges
        if current_user.get('role') not in [UserRole.ADMIN, UserRole.SUPER_ADMIN, "admin", "super_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        
        # Get user
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get role permissions
        from backend.core.rbac import get_role_permissions
        user_role = user.role.value if hasattr(user.role, 'value') else user.role
        permissions = get_role_permissions(user_role)
        
        return {
            "user_id": user_id,
            "role": user_role,
            "permissions": [p.value for p in permissions]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user permissions for {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user permissions"
        )

@router.get("/health")
async def users_health():
    """Health check for users endpoints"""
    return {"status": "healthy", "service": "users"}