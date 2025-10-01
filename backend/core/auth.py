from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
from loguru import logger

from backend.core.config import settings
from backend.models.mongodb_models import User
from backend.utils.jwt_auth import get_jwt_manager, JWTError, TokenExpiredError, TokenInvalidError
from motor.motor_asyncio import AsyncIOMotorDatabase

security = HTTPBearer()

def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token using centralized JWT manager"""
    try:
        jwt_manager = get_jwt_manager()
        payload = jwt_manager.decode_token(token)
        
        # Extract user information from JWT payload
        sub: str = payload.get("sub")  # JWT standard subject field
        email: str = payload.get("email") or sub  # Use sub as email if email field is not present
        
        if sub is None:
            logger.warning("Token missing subject field")
            return None
            
        return {
            "sub": sub,  # Include the subject field
            "user_id": payload.get("user_id"),  # May be present in additional claims
            "email": email,
            "role": payload.get("role", "JOB_SEEKER"),
            "token_type": payload.get("type"),
            "service_name": payload.get("service")  # For service tokens
        }
        
    except (TokenExpiredError, TokenInvalidError, JWTError) as e:
        logger.warning(f"JWT verification failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}")
        return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    token_data = verify_token(token)
    
    logger.info(f"Token data: {token_data}")
    
    if token_data is None:
        logger.error("Token verification failed - token_data is None")
        raise credentials_exception
    
    # Get user from database
    try:
        user_identifier = token_data.get('sub') or token_data.get('user_id')
        email_field = token_data.get('email')
        
        logger.info(f"User identifier from token: {user_identifier}")
        logger.info(f"Email field from token: {email_field}")
        
        user = None
        
        # Handle admin user special case
        if user_identifier == "admin-user-id":
            logger.info("Handling admin user special case")
            return {
                "id": "admin-user-id",
                "email": "admin@remotehive.in",
                "full_name": "Super Admin",
                "role": "super_admin",
                "is_active": True,
                "is_verified": True,
                "created_at": None,
                "updated_at": None,
                "last_login": None,
                "phone": None
            }
        
        # First try: use sub or user_id field
        if user_identifier:
            try:
                from bson import ObjectId
                logger.info(f"Trying to get user by ID: {user_identifier}")
                # Convert string to ObjectId if it's a valid ObjectId string
                if isinstance(user_identifier, str) and ObjectId.is_valid(user_identifier):
                    user_identifier = ObjectId(user_identifier)
                user = await User.get(user_identifier)
                logger.info(f"Found user by ID: {user.email if user else 'None'}")
            except Exception as e:
                logger.info(f"ID lookup failed: {e}")
        
        # Second try: check if email field contains a user ID (24-char hex string)
        if not user and email_field:
            # Check if email field looks like a MongoDB ObjectId (24 hex chars)
            if len(email_field) == 24 and all(c in '0123456789abcdef' for c in email_field.lower()):
                try:
                    logger.info(f"Email field looks like ObjectId, trying as user ID: {email_field}")
                    user = await User.get(email_field)
                    logger.info(f"Found user by ObjectId in email field: {user.email if user else 'None'}")
                except Exception as e:
                    logger.info(f"ObjectId lookup failed: {e}")
            
            # Third try: use email field as actual email
            if not user:
                logger.info(f"Trying email field as actual email: {email_field}")
                user = await User.find_one(User.email == email_field)
                logger.info(f"Found user by email: {user.email if user else 'None'}")
        
        if not user:
            raise credentials_exception
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )
        
        # Convert MongoDB model to dict
        return {
            "id": user.id,
            "email": user.email,
            "full_name": f"{user.first_name} {user.last_name}".strip(),
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "last_login": getattr(user, 'last_login', None),
            "phone": user.phone
        }
        
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise credentials_exception

async def get_current_active_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current active user"""
    if not current_user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

def require_roles(allowed_roles: List[str]):
    """Decorator to require specific roles"""
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_active_user)) -> Dict[str, Any]:
        user_role = current_user.get("role", "JOB_SEEKER")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker

# Role-based dependencies
get_super_admin = require_roles(["super_admin"])
get_admin = require_roles(["super_admin", "admin"])
get_current_admin_user = require_roles(["super_admin", "admin"])  # Alias for backward compatibility
get_employer = require_roles(["super_admin", "admin", "employer"])
get_job_seeker_only = require_roles(["job_seeker"])
get_job_seeker = require_roles(["super_admin", "admin", "employer", "job_seeker"])