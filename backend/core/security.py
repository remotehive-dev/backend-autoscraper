from datetime import datetime, timedelta
from typing import Any, Union, Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.config import settings
from backend.core.password_utils import verify_password, get_password_hash
from backend.database.database import get_mongodb_session
from backend.database.services import UserService
from backend.utils.jwt_auth import get_jwt_manager, TokenExpiredError, TokenInvalidError, JWTError, create_refresh_token
from backend.core.token_blacklist import get_token_blacklist_service
from backend.core.database import get_database

def create_access_token(
    subject: Union[str, Any], 
    expires_delta: timedelta = None,
    additional_claims: Dict[str, Any] = None
) -> str:
    """Create JWT access token using centralized JWT manager"""
    jwt_manager = get_jwt_manager()
    return jwt_manager.create_access_token(
        subject=str(subject),
        expires_delta=expires_delta,
        user_data=additional_claims or {}
    )



async def authenticate_user(email: str, password: str, db: AsyncIOMotorDatabase = Depends(get_mongodb_session)):
    return await UserService.authenticate_user(db, email, password)

async def authenticate_oauth_user(email: str, db: AsyncIOMotorDatabase = Depends(get_mongodb_session)):
    return await UserService.get_user_by_email(db, email)

def create_user_token(user: Dict[str, Any]) -> str:
    """Create access token for user"""
    additional_claims = {
        "email": user["email"],
        "role": user["role"],
        "full_name": user.get("full_name"),
        "oauth_provider": user.get("oauth_provider"),
        "oauth_id": user.get("oauth_id")
    }
    
    return create_access_token(
        subject=user["id"],
        additional_claims=additional_claims
    )

def create_oauth_user_token(user: Dict[str, Any]) -> Dict[str, str]:
    """Create both access and refresh tokens for OAuth user"""
    additional_claims = {
        "email": user["email"],
        "role": user["role"],
        "full_name": user.get("full_name"),
        "oauth_provider": user.get("oauth_provider"),
        "oauth_id": user.get("oauth_id"),
        "profile_picture": user.get("profile_picture")
    }
    
    access_token = create_access_token(
        subject=user["id"],
        additional_claims=additional_claims
    )
    
    refresh_token = create_refresh_token(subject=user["id"])
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

async def blacklist_token(token: str, reason: str = "logout") -> bool:
    """Add token to blacklist using token blacklist service"""
    try:
        db = await get_database()
        blacklist_service = get_token_blacklist_service()
        return await blacklist_service.blacklist_token(db, token, reason)
    except Exception as e:
        # Log error but don't raise to avoid breaking logout flow
        print(f"Error blacklisting token: {e}")
        return False

async def is_token_blacklisted(token: str) -> bool:
    """Check if token is blacklisted using token blacklist service"""
    try:
        db = await get_database()
        blacklist_service = get_token_blacklist_service()
        return await blacklist_service.is_token_blacklisted(db, token)
    except Exception as e:
        # Log error but assume token is not blacklisted to avoid blocking valid users
        print(f"Error checking token blacklist: {e}")
        return False

def validate_token_signature(token: str) -> bool:
    """Validate JWT token signature"""
    try:
        jwt_manager = get_jwt_manager()
        jwt_manager.decode_token(token)
        return True
    except (TokenExpiredError, TokenInvalidError, JWTError):
        return False

def verify_token(token: str) -> bool:
    """Verify if a JWT token is valid"""
    try:
        jwt_manager = get_jwt_manager()
        jwt_manager.decode_token(token)
        return True
    except (TokenExpiredError, TokenInvalidError, JWTError):
        return False

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: AsyncIOMotorDatabase = Depends(get_mongodb_session)):
    """Get current authenticated user from JWT token using centralized JWT manager"""
    try:
        token = credentials.credentials
        
        # Check if token is blacklisted
        if await is_token_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        jwt_manager = get_jwt_manager()
        payload = jwt_manager.decode_token(token)
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except (TokenExpiredError, TokenInvalidError, JWTError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # user_id contains the actual user ID from JWT 'sub' field
    user = await UserService.get_user_by_id(db, user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user

def require_admin(current_user = Depends(get_current_user)):
    """Require admin or super_admin role"""
    # TODO: MongoDB Migration - Update UserRole import to use MongoDB models
    # from backend.database.models import UserRole
    from backend.models.mongodb_models import UserRole
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

def require_super_admin(current_user = Depends(get_current_user)):
    """Require super_admin role"""
    # TODO: MongoDB Migration - Update UserRole import to use MongoDB models
    # from backend.database.models import UserRole
    from backend.models.mongodb_models import UserRole
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user