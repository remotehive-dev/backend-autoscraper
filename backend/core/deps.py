from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from bson import ObjectId
from datetime import datetime, timedelta

from backend.core.database import get_db
from backend.models.mongodb_models import User
from backend.core.config import settings
from backend.utils.jwt_auth import get_jwt_manager, TokenExpiredError, TokenInvalidError, JWTError
from backend.core.token_blacklist import is_token_blacklisted

security = HTTPBearer()

async def get_database() -> AsyncIOMotorDatabase:
    """Get MongoDB database"""
    return get_db()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> User:
    """Get current authenticated user using centralized JWT manager"""
    try:
        token = credentials.credentials
        
        # Check if token is blacklisted
        print(f"DEBUG: Checking if token is blacklisted: {token[:50]}...")
        is_blacklisted = await is_token_blacklisted(db, token)
        print(f"DEBUG: Token blacklisted status: {is_blacklisted}")
        if is_blacklisted:
            print(f"DEBUG: Token is blacklisted, raising 401")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        jwt_manager = get_jwt_manager()
        payload = jwt_manager.decode_token(token)
        
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Handle admin user special case
        if user_id_str == "admin-user-id":
            # Create a mock admin user for admin panel authentication
            from backend.models.mongodb_models import UserRole
            admin_user = User(
                id=ObjectId(),  # Generate a temporary ObjectId
                email="admin@remotehive.in",
                first_name="Super",
                last_name="Admin",
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            return admin_user
        
        # Convert string to ObjectId for regular users
        try:
            user_id = ObjectId(user_id_str)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID format",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    except (TokenExpiredError, TokenInvalidError, JWTError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await User.find_one({"_id": user_id})
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user and verify admin role"""
    # Handle both admin and super_admin roles
    if current_user.role not in ["admin", "super_admin"] and current_user.role.value not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user