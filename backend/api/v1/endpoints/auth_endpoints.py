from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr
from loguru import logger

print("=== [UPDATED] AUTH_ENDPOINTS MODULE LOADED AT:", datetime.now(), "===")
logger.info("[UPDATED] AUTH_ENDPOINTS MODULE LOADED - ENHANCED LOGGING ACTIVE")

from backend.core.local_auth import (
    authenticate_user, create_access_token, get_current_user,
    create_user, get_password_hash, verify_password
)
from backend.core.auth_middleware import (
    require_super_admin, require_admin, require_employer, require_job_seeker,
    AuthContext, SecurityMiddleware
)
from backend.core.rbac import get_role_permissions, create_user_session, end_user_session
from backend.core.database import get_db
from backend.core.audit_logger import get_audit_logger, AuditEvent
from backend.middleware.rate_limiting import login_rate_limit, register_rate_limit, password_reset_rate_limit
from backend.models.mongodb_models import User, UserRole
from backend.database.mongodb_models import EmailVerificationToken, PasswordResetToken
from backend.database.services import EmployerService, JobSeekerService
from backend.services.lead_service import LeadService
import requests
import json
import uuid

router = APIRouter()
security = HTTPBearer()

@router.get("/test-logging")
async def test_logging_endpoint():
    """Test endpoint to verify logging is working"""
    print("=== [TEST] TEST LOGGING ENDPOINT CALLED ===", flush=True)
    logger.error("=== [TEST] TEST LOGGING ENDPOINT CALLED - ERROR LEVEL ===")
    logger.warning("=== [TEST] TEST LOGGING ENDPOINT CALLED - WARNING LEVEL ===")
    logger.info("=== [TEST] TEST LOGGING ENDPOINT CALLED - INFO LEVEL ===")
    
    # Write to file
    try:
        with open('D:\\Remotehive\\test_endpoint_debug.log', 'a') as f:
            f.write(f"[{datetime.now()}] Test endpoint called\n")
        print("Successfully wrote to test endpoint debug log")
    except Exception as e:
        print(f"Error writing to test endpoint debug log: {e}")
    
    return {"message": "Test logging endpoint called", "timestamp": datetime.now()}

# Request/Response Models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: Dict[str, Any]
    permissions: list
    session_id: str

class PublicRegistrationRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: str  # "job_seeker" or "employer"

class AdminRegistrationRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: str  # "admin" or "super_admin"

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class EmailVerificationRequest(BaseModel):
    token: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str

class PasswordResetResponse(BaseModel):
    message: str
    success: bool = True

class UserProfileResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    permissions: list

# Helper functions
def get_client_info(request: Request) -> Dict[str, str]:
    """Extract client information from request"""
    return {
        "ip_address": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown")
    }

def create_login_response(user: User, access_token: str, expires_in: int, session_id: str) -> LoginResponse:
    """Create standardized login response"""
    user_role = user.role.value if isinstance(user.role, UserRole) else user.role
    permissions = get_role_permissions(user_role)
    
    # Create refresh token
    from backend.utils.jwt_auth import create_refresh_token
    refresh_token = create_refresh_token(str(user.id))
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user={
            "id": str(user.id),  # Convert PydanticObjectId to string
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user_role,
            "is_active": user.is_active,
            "is_verified": user.is_verified
        },
        permissions=[p.value for p in permissions],
        session_id=session_id
    )

# Public Website Authentication Endpoints
@router.post("/public/login", response_model=LoginResponse)
async def public_login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: None = Depends(login_rate_limit)
):
    """Login endpoint for public website (job seekers and employers)"""
    client_info = get_client_info(request)
    
    # Check rate limiting
    if not await SecurityMiddleware.check_rate_limit(
        db, login_data.email, client_info["ip_address"]
    ):
        audit_logger = get_audit_logger()
        await audit_logger.log_login_attempt(
            db, login_data.email, client_info["ip_address"], 
            client_info["user_agent"], False, failure_reason="Rate limit exceeded"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later."
        )
    
    # Authenticate user
    user = await authenticate_user(db, login_data.email, login_data.password)
    if not user:
        audit_logger = get_audit_logger()
        await audit_logger.log_login_attempt(
            db, login_data.email, client_info["ip_address"],
            client_info["user_agent"], False, failure_reason="Invalid credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user role is allowed for public login
    user_role = user.role.value if isinstance(user.role, UserRole) else user.role
    if user_role not in ["job_seeker", "employer"]:
        await SecurityMiddleware.log_login_attempt(
            db, login_data.email, client_info["ip_address"],
            client_info["user_agent"], False, "Invalid role for public login"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Please use the admin panel for administrative access."
        )
    
    # Create access token
    expires_delta = timedelta(days=7) if login_data.remember_me else timedelta(hours=8)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user_role},
        expires_delta=expires_delta
    )
    
    # Create user session
    import secrets
    session_token = await create_user_session(
        str(user.id), client_info["ip_address"], client_info["user_agent"]
    )
    session_id = session_token
    
    # Log successful login
    audit_logger = get_audit_logger()
    await audit_logger.log_login_attempt(
        db, user.email, client_info["ip_address"],
        client_info["user_agent"], True
    )
    
    expires_in = int(expires_delta.total_seconds())
    return create_login_response(user, access_token, expires_in, session_id)

@router.post("/public/register", response_model=LoginResponse)
async def public_register(
    registration_data: PublicRegistrationRequest,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: None = Depends(register_rate_limit)
):
    """Registration endpoint for public website (job seekers and employers)"""
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    print(f"=== PUBLIC_REGISTER FUNCTION CALLED FOR: {registration_data.email} === [UPDATED]", flush=True)
    logger.error(f"=== PUBLIC_REGISTER FUNCTION CALLED FOR: {registration_data.email} === [UPDATED]")
    logger.warning(f"=== PUBLIC_REGISTER FUNCTION CALLED FOR: {registration_data.email} === [UPDATED]")
    logger.info(f"=== PUBLIC_REGISTER FUNCTION CALLED FOR: {registration_data.email} === [UPDATED]")
    
    # Also write to file for debugging with absolute path
    try:
        with open('D:\\Remotehive\\registration_debug.log', 'a') as f:
            f.write(f"[{datetime.now()}] PUBLIC_REGISTER called for: {registration_data.email}\n")
        print(f"Successfully wrote to debug log for {registration_data.email}")
    except Exception as e:
        print(f"Error writing to debug log: {e}")
    
    client_info = get_client_info(request)
    
    # Validate role
    if registration_data.role not in ["job_seeker", "employer"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'job_seeker' or 'employer'"
        )
    
    # Check if user already exists
    existing_user = await User.find_one(User.email == registration_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    try:
        user = await create_user(
            db=db,
            email=registration_data.email,
            password=registration_data.password,
            first_name=registration_data.first_name,
            last_name=registration_data.last_name,
            phone=registration_data.phone,
            role=registration_data.role
        )
        
        # Create access token
        access_token = create_access_token(
            data={"sub": str(user.id), "role": registration_data.role},
            expires_delta=timedelta(hours=8)
        )
        print(f"PRINT DEBUG: Access token created successfully for {user.email}")
        
        # Create user session
        session_token = await create_user_session(
            str(user.id), client_info["ip_address"], client_info["user_agent"]
        )
        print(f"PRINT DEBUG: User session created successfully for {user.email}")
        
        # Log successful registration
        audit_logger = get_audit_logger()
        await audit_logger.log_registration(
            db=db,
            user_id=str(user.id),
            email=user.email,
            role=registration_data.role,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"]
        )
        
        import logging
        print(f"PRINT DEBUG: About to start profile creation section for {registration_data.role}")
        logging.debug(f"DEBUG: About to start profile creation section for {registration_data.role}")
        
        # Create role-specific profile
        try:
            import logging
            logging.debug(f"DEBUG: About to create profile for role: {registration_data.role}")
            logging.info(f"Creating profile for role: {registration_data.role}")
            
            if registration_data.role == "employer":
                # Create employer profile with basic information
                employer_data = {
                    "company_name": f"{registration_data.first_name} {registration_data.last_name} Company",
                    "company_email": registration_data.email,  # Required field
                    "company_description": "New employer profile",
                    "industry": "Not specified",
                    "company_size": "startup",
                    "location": "Not specified"
                }
                logging.info(f"Creating employer profile with data: {employer_data}")
                employer_service = EmployerService()
                employer = await employer_service.create_employer(db, employer_data, user.id)
                logging.info(f"Employer profile created successfully: {employer.id}")
                
            elif registration_data.role == "job_seeker":
                # Create job seeker profile with basic information
                job_seeker_data = {
                    "current_title": "Job Seeker",
                    "experience_level": "entry",
                    "skills": [],
                    "preferred_job_types": ["full_time"],
                    "preferred_locations": ["Remote"],
                    "is_actively_looking": True
                }
                logging.info(f"Creating job seeker profile with data: {job_seeker_data}")
                job_seeker = await JobSeekerService.create_job_seeker(db, user.id, job_seeker_data)
                logging.info(f"Job seeker profile created successfully: {job_seeker.id}")
                
        except Exception as profile_error:
            import logging
            logging.error(f"Failed to create {registration_data.role} profile: {str(profile_error)}")
            logging.error(f"Profile error details: {type(profile_error).__name__}: {profile_error}")
            # Continue without failing the registration
        
        # Create lead using LeadService (continue even if this fails)
        try:
            await LeadService.create_lead_from_signup(
                email=registration_data.email,
                name=f"{registration_data.first_name} {registration_data.last_name}",
                role=registration_data.role,
                source="direct_signup",
                metadata={
                    "phone": registration_data.phone,
                    "registration_method": "public_register",
                    "profile_created": True
                }
            )
            import logging
            logging.info(f"Lead created successfully for user: {registration_data.email}")
        except Exception as lead_error:
            import logging
            logging.warning(f"Failed to create lead for user {registration_data.email}: {str(lead_error)}")
            # Continue without failing the registration
        
        # Create real-time notification for admin panel
        try:
            notification_data = {
                "user_id": user.id,
                "full_name": f"{registration_data.first_name} {registration_data.last_name}",
                "email": registration_data.email,
                "role": registration_data.role,
                "registration_source": "website_registration"
            }
            
            # Call the admin panel API to create notification
            notification_api_url = "http://localhost:3000/api/notifications/new-user-registration"
            notification_response = requests.post(notification_api_url, json=notification_data, timeout=5)
            
            if notification_response.status_code != 201:
                import logging
                logging.warning(f"Failed to create admin notification: {notification_response.text}")
                
        except Exception as notification_error:
            import logging
            logging.warning(f"Failed to create admin notification: {str(notification_error)}")
            # Continue without failing the registration
        
        # Send email verification
        try:
            verification_token = create_verification_token(db, user.id)
            user_name = f"{registration_data.first_name} {registration_data.last_name}".strip() or registration_data.email
            send_verification_email(registration_data.email, user_name, verification_token)
            logging.info(f"Verification email sent to: {registration_data.email}")
        except Exception as email_error:
            import logging
            logging.warning(f"Failed to send verification email: {str(email_error)}")
            # Continue without failing the registration
        
        return create_login_response(user, access_token, 28800, session_token)
        
    except HTTPException:
        # Re-raise HTTP exceptions (like validation errors)
        raise
    except Exception as e:
        # Only catch actual errors, not warnings
        import logging
        logging.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

# Admin Panel Authentication Endpoints
@router.post("/admin/login", response_model=LoginResponse)
async def admin_login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Login endpoint for admin panel (admin and super admin)"""
    client_info = get_client_info(request)
    
    # Check rate limiting (stricter for admin)
    if not await SecurityMiddleware.check_rate_limit(
        db, login_data.email, client_info["ip_address"], max_attempts=3, window_minutes=30
    ):
        audit_logger = get_audit_logger()
        await audit_logger.log_login_attempt(
            db, login_data.email, client_info["ip_address"],
            client_info["user_agent"], False, failure_reason="Admin rate limit exceeded"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed admin login attempts. Please try again later."
        )
    
    # Authenticate user
    user = await authenticate_user(db, login_data.email, login_data.password)
    if not user:
        audit_logger = get_audit_logger()
        await audit_logger.log_login_attempt(
            db, login_data.email, client_info["ip_address"],
            client_info["user_agent"], False, failure_reason="Invalid admin credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user role is allowed for admin login
    user_role = user.role.value if isinstance(user.role, UserRole) else user.role
    if user_role not in ["admin", "super_admin"]:
        audit_logger = get_audit_logger()
        await audit_logger.log_permission_denied(
            db, str(user.id), user.email, "admin_login", 
            client_info["ip_address"], client_info["user_agent"], 
            f"User role '{user_role}' not authorized for admin login"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required."
        )
    
    # Store user data in variables to avoid session issues
    user_id = user.id
    user_email = user.email
    user_first_name = user.first_name
    user_last_name = user.last_name
    user_is_active = user.is_active
    user_is_verified = user.is_verified
    
    # Create access token (shorter expiry for admin)
    expires_delta = timedelta(hours=4) if login_data.remember_me else timedelta(hours=2)
    access_token = create_access_token(
        data={"sub": str(user_id), "role": user_role},
        expires_delta=expires_delta
    )
    
    # Create user session
    logger.info(f"About to create user session for user_id: {user_id}")
    logger.info(f"Client info: {client_info}")
    
    try:
        logger.info("Calling create_user_session function")
        session_token = await create_user_session(
            str(user_id), client_info["ip_address"], client_info["user_agent"]
        )
        logger.info(f"Session created successfully")
        session_id = session_token
    except Exception as e:
        logger.error(f"Failed to create user session: {e}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user session"
        )
    
    # Log successful admin login
    audit_logger = get_audit_logger()
    await audit_logger.log_login_attempt(
        db, user_email, client_info["ip_address"],
        client_info["user_agent"], True
    )
    
    expires_in = int(expires_delta.total_seconds())
    
    # Create a user dict for the response instead of using the SQLAlchemy object
    user_dict = {
        "id": str(user_id),
        "email": user_email,
        "first_name": user_first_name,
        "last_name": user_last_name,
        "role": user_role,
        "is_active": user_is_active,
        "is_verified": user_is_verified
    }
    
    permissions = get_role_permissions(user_role)
    
    # Create refresh token
    from backend.utils.jwt_auth import create_refresh_token
    refresh_token = create_refresh_token(str(user_id))
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=user_dict,
        permissions=[p.value for p in permissions],
        session_id=session_id
    )

@router.post("/admin/create-user", response_model=UserProfileResponse)
async def admin_create_user(
    registration_data: AdminRegistrationRequest,
    current_user: Dict[str, Any] = Depends(require_super_admin()),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Create admin user (super admin only)"""
    
    # Validate role
    if registration_data.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'admin' or 'super_admin'"
        )
    
    # Only super admin can create other super admins
    current_user_role = current_user.get("role")
    if registration_data.role == "super_admin" and current_user_role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can create super admin users"
        )
    
    # Check if user already exists
    existing_user = await User.find_one(User.email == registration_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    try:
        user = await create_user(
            db=db,
            email=registration_data.email,
            password=registration_data.password,
            first_name=registration_data.first_name,
            last_name=registration_data.last_name,
            phone=registration_data.phone,
            role=registration_data.role
        )
        
        user_role = user.role.value if isinstance(user.role, UserRole) else user.role
        permissions = get_role_permissions(user_role)
        
        # Log admin action for user creation
        audit_logger = get_audit_logger()
        await audit_logger.log_admin_action(
            admin_user_id=str(current_user.get('id')),
            admin_email=current_user.get('email'),
            action="user_creation",
            target_user_id=str(user.id),
            target_email=user.email,
            details={"role": user_role, "created_by_super_admin": current_user.get('role') == 'super_admin'}
        )
        
        return UserProfileResponse(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            role=user_role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            permissions=[p.value for p in permissions]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"User creation failed: {str(e)}"
        )

# Common Endpoints
@router.post("/logout-session")
async def logout_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Logout endpoint for session-based authentication"""
    try:
        await end_user_session(db, session_id)
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )

@router.get("/test-debug")
async def test_debug():
    """Test endpoint for debugging"""
    print("DEBUG: Test endpoint called")
    return {"message": "Debug test successful", "timestamp": datetime.now()}

@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user profile"""
    try:
        print(f"DEBUG PROFILE: Got current_user: {current_user}")
        print(f"DEBUG PROFILE: User role: {current_user.get('role')}")
        print(f"DEBUG PROFILE: User role type: {type(current_user.get('role'))}")
        
        # Convert UserRole enum to string if needed
        user_role_raw = current_user.get('role')
        user_role = user_role_raw.value if hasattr(user_role_raw, 'value') else str(user_role_raw)
        print(f"DEBUG PROFILE: Processed user_role: {user_role}")
        
        permissions = get_role_permissions(user_role)
        print(f"DEBUG PROFILE: Got permissions: {permissions}")
        
        response = UserProfileResponse(
            id=str(current_user.get('id')),
            email=current_user.get('email'),
            first_name=current_user.get('first_name'),
            last_name=current_user.get('last_name'),
            phone=current_user.get('phone'),
            role=user_role,
            is_active=current_user.get('is_active'),
            is_verified=current_user.get('is_verified'),
            created_at=current_user.get('created_at'),
            permissions=[p.value for p in permissions]
        )
        print(f"DEBUG PROFILE: Created response successfully")
        return response
    except Exception as e:
        print(f"DEBUG PROFILE ERROR: {str(e)}")
        print(f"DEBUG PROFILE ERROR TYPE: {type(e)}")
        import traceback
        print(f"DEBUG PROFILE TRACEBACK: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Profile error: {str(e)}"
        )

@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current authenticated user information (alias for /profile)"""
    try:
        # Convert UserRole enum to string if needed
        user_role_raw = current_user.role
        user_role = user_role_raw.value if hasattr(user_role_raw, 'value') else str(user_role_raw)
        
        permissions = get_role_permissions(user_role)
        
        return UserProfileResponse(
            id=str(current_user.id),
            email=current_user.email,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            phone=current_user.phone,
            role=user_role,
            is_active=current_user.is_active,
            is_verified=current_user.is_verified,
            created_at=current_user.created_at,
            permissions=[p.value for p in permissions]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user info: {str(e)}"
        )

@router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Change user password"""
    
    # Get user from database
    user = await User.find_one(User.id == current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify current password
    if not verify_password(password_data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    try:
        user.password_hash = get_password_hash(password_data.new_password)
        await user.save()
        return {"message": "Password changed successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password change failed: {str(e)}"
        )

# Context endpoints for different user types
@router.get("/context/employer")
async def get_employer_context(
    context = Depends(AuthContext.get_employer_context)
):
    """Get employer-specific context and permissions"""
    return context

@router.get("/context/job-seeker")
async def get_job_seeker_context(
    context = Depends(AuthContext.get_job_seeker_context)
):
    """Get job seeker-specific context and permissions"""
    return context

@router.get("/context/admin")
async def get_admin_context(
    context = Depends(AuthContext.get_admin_context)
):
    """Get admin-specific context and permissions"""
    return context

# ============================================================================
# EMAIL VERIFICATION ENDPOINTS
# ============================================================================

async def create_verification_token(db: AsyncIOMotorDatabase, user_id: str) -> str:
    """Create a new email verification token for a user"""
    # Invalidate any existing tokens for this user
    existing_tokens = await EmailVerificationToken.find(
        EmailVerificationToken.user_id == user_id,
        EmailVerificationToken.is_used == False
    ).to_list()
    
    for token_doc in existing_tokens:
        token_doc.is_used = True
        token_doc.used_at = datetime.utcnow()
        await token_doc.save()
    
    # Create new token
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
    
    verification_token = EmailVerificationToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )
    
    await verification_token.insert()
    
    return token

def send_verification_email(user_email: str, user_name: str, token: str):
    """Send verification email to user"""
    from backend.tasks.email import send_verification_email_task
    
    # Queue the email task
    send_verification_email_task.delay(
        to_email=user_email,
        user_name=user_name,
        verification_token=token
    )

@router.post("/verify-email")
async def verify_email(
    verification_data: EmailVerificationRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Verify user email with token
    """
    try:
        # Find the verification token
        token_record = await EmailVerificationToken.find_one(
            EmailVerificationToken.token == verification_data.token,
            EmailVerificationToken.is_used == False,
            EmailVerificationToken.expires_at > datetime.utcnow()
        )
        
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )
        
        # Get the user
        user = await User.find_one(User.id == token_record.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Mark user as verified
        user.is_verified = True
        await user.save()
        
        # Mark token as used
        token_record.is_used = True
        token_record.used_at = datetime.utcnow()
        await token_record.save()
        
        logger.info(f"Email verified successfully for user: {user.email}")
        
        return {
            "message": "Email verified successfully",
            "user_id": user.id,
            "email": user.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify email"
        )

@router.post("/resend-verification")
async def resend_verification(
    resend_data: ResendVerificationRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Resend verification email
    """
    try:
        # Find the user
        user = await User.find_one(User.email == resend_data.email)
        if not user:
            # Don't reveal if email exists or not for security
            return {"message": "If the email exists, a verification link has been sent"}
        
        # Check if already verified
        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already verified"
            )
        
        # Create new verification token
        token = create_verification_token(db, user.id)
        
        # Send verification email
        user_name = f"{user.first_name} {user.last_name}".strip() or user.email
        send_verification_email(user.email, user_name, token)
        
        logger.info(f"Verification email resent to: {user.email}")
        
        return {"message": "Verification email sent successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resending verification email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email"
        )

# ============================================================================
# PASSWORD RESET ENDPOINTS
# ============================================================================

async def create_password_reset_token(db: AsyncIOMotorDatabase, user_id: str, email: str, ip_address: str = None, user_agent: str = None) -> str:
    """Create a new password reset token for a user"""
    # Invalidate any existing tokens for this user
    existing_tokens = await PasswordResetToken.find(
        PasswordResetToken.user_id == user_id,
        PasswordResetToken.is_used == False
    ).to_list()
    
    for token_doc in existing_tokens:
        token_doc.is_used = True
        token_doc.used_at = datetime.utcnow()
        await token_doc.save()
    
    # Create new token
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
    
    reset_token = PasswordResetToken(
        user_id=user_id,
        email=email,
        token=token,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    await reset_token.insert()
    
    return token

async def send_password_reset_email(user_email: str, user_name: str, token: str, request_info: dict = None):
    """Send password reset email to user"""
    from backend.services.gmail_service import GmailService
    from backend.core.config import settings
    
    try:
        gmail_service = GmailService()
        
        success = await gmail_service.send_password_reset_email(
            to_email=user_email,
            reset_token=token,
            user_type="user"
        )
        
        if success:
            logger.info(f"Password reset email sent successfully via Gmail to: {user_email}")
        else:
            logger.warning(f"Gmail service failed, falling back to task for: {user_email}")
            # Fallback to Celery task if Gmail fails
            from backend.tasks.email import send_password_reset_email_task
            task_result = send_password_reset_email_task.delay(
                to_email=user_email,
                user_name=user_name,
                reset_token=token
            )
            
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")
        # Fallback to regular email service if Gmail fails
        try:
            from backend.tasks.email import send_password_reset_email_task
            send_password_reset_email_task.delay(
                to_email=user_email,
                user_name=user_name,
                reset_token=token
            )
        except Exception as task_error:
            logger.error(f"Failed to queue password reset email task: {str(task_error)}")

@router.post("/request-password-reset")
async def request_password_reset(
    reset_request: PasswordResetRequest,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _: None = Depends(password_reset_rate_limit)
):
    """
    Request password reset for any user type
    """
    try:
        # Find the user by email
        user = await User.find_one(User.email == reset_request.email)
        
        # Always return success message for security (don't reveal if email exists)
        success_message = "If the email exists in our system, a password reset link has been sent"
        
        if not user:
            logger.info(f"Password reset requested for non-existent email: {reset_request.email}")
            return {"message": success_message}
        
        # Get client info for security logging
        client_info = get_client_info(request)
        
        # Create password reset token
        token = await create_password_reset_token(
            db, 
            str(user.id), 
            user.email,
            client_info.get('ip_address'),
            client_info.get('user_agent')
        )
        
        # Send password reset email
        user_name = f"{user.first_name} {user.last_name}".strip() or user.email
        await send_password_reset_email(user.email, user_name, token, client_info)
        
        # Log password reset request
        audit_logger = get_audit_logger()
        await audit_logger.log_password_reset_request(
            user_id=str(user.id),
            email=user.email,
            ip_address=client_info.get('ip_address'),
            user_agent=client_info.get('user_agent')
        )
        
        logger.info(f"Password reset requested for user: {user.email} (Role: {user.role})")
        
        return {"message": success_message}
        
    except Exception as e:
        logger.error(f"Error requesting password reset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process password reset request"
        )

@router.post("/confirm-password-reset")
async def confirm_password_reset(
    reset_data: PasswordResetConfirmRequest,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Confirm password reset with token and set new password
    """
    try:
        # Find the reset token
        token_record = await PasswordResetToken.find_one(
            PasswordResetToken.token == reset_data.token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        )
        
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset token"
            )
        
        # Get the user
        user = await User.find_one(User.id == token_record.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Validate new password (basic validation)
        if len(reset_data.new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # Update user password
        user.password_hash = get_password_hash(reset_data.new_password)
        await user.save()
        
        # Mark token as used
        token_record.is_used = True
        token_record.used_at = datetime.utcnow()
        await token_record.save()
        
        # Get client info for logging
        client_info = get_client_info(request)
        
        # Log successful password reset
        audit_logger = get_audit_logger()
        await audit_logger.log_password_reset_success(
            user_id=str(user.id),
            email=user.email,
            ip_address=client_info.get('ip_address'),
            user_agent=client_info.get('user_agent')
        )
        
        logger.info(f"Password reset completed for user: {user.email} (Role: {user.role}) from IP: {client_info.get('ip_address')}")
        
        return {
            "message": "Password reset successfully",
            "user_id": user.id,
            "email": user.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming password reset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        )

@router.post("/validate-reset-token")
async def validate_reset_token(
    token: str,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Validate if a password reset token is valid and not expired
    """
    try:
        # Find the reset token
        token_record = await PasswordResetToken.find_one(
            PasswordResetToken.token == token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expires_at > datetime.utcnow()
        )
        
        if not token_record:
            return {
                "valid": False,
                "message": "Invalid or expired token"
            }
        
        # Get user info for response
        user = await User.find_one(User.id == token_record.user_id)
        if not user:
            return {
                "valid": False,
                "message": "User not found"
            }
        
        return {
            "valid": True,
            "email": user.email,
            "expires_at": token_record.expires_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error validating reset token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate token"
        )

# ============================================================================
# ADMIN PASSWORD RESET MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/admin/request-password-reset/{user_id}")
async def admin_request_password_reset(
    user_id: str,
    request: Request,
    current_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Admin endpoint to request password reset for any user
    """
    try:
        # Find the user
        user = await User.find_one(User.id == user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get client info for security logging
        client_info = get_client_info(request)
        
        # Create password reset token with longer expiry for admin-initiated resets
        token = await create_password_reset_token(
            db, 
            user.id, 
            user.email,
            client_info.get('ip_address'),
            client_info.get('user_agent')
        )
        
        # Send password reset email
        user_name = f"{user.first_name} {user.last_name}".strip() or user.email
        send_password_reset_email(user.email, user_name, token)
        
        # Log admin action
        audit_logger = get_audit_logger()
        await audit_logger.log_admin_action(
            admin_user_id=str(current_user.get('id')),
            admin_email=current_user.get('email'),
            action="password_reset_request",
            target_user_id=str(user.id),
            target_email=user.email,
            ip_address=client_info.get('ip_address'),
            user_agent=client_info.get('user_agent')
        )
        
        logger.info(f"Admin {current_user.get('email')} requested password reset for user: {user.email} (Role: {user.role})")
        
        return {
            "message": "Password reset email sent successfully",
            "user_email": user.email,
            "user_role": user.role.value if hasattr(user.role, 'value') else user.role
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in admin password reset request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process admin password reset request"
        )

@router.get("/admin/password-reset-tokens")
async def get_password_reset_tokens(
    page: int = 1,
    limit: int = 20,
    user_role: Optional[str] = None,
    status_filter: Optional[str] = None,  # active, expired, used
    current_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Get password reset tokens with filtering and pagination
    """
    try:
        # Build filter conditions
        filter_conditions = []
        
        if status_filter == "active":
            filter_conditions.extend([
                PasswordResetToken.is_used == False,
                PasswordResetToken.expires_at > datetime.utcnow()
            ])
        elif status_filter == "expired":
            filter_conditions.extend([
                PasswordResetToken.is_used == False,
                PasswordResetToken.expires_at <= datetime.utcnow()
            ])
        elif status_filter == "used":
            filter_conditions.append(PasswordResetToken.is_used == True)
        
        # Get tokens with pagination
        skip = (page - 1) * limit
        
        if filter_conditions:
            query = PasswordResetToken.find(*filter_conditions)
        else:
            query = PasswordResetToken.find()
        
        tokens = await query.sort(-PasswordResetToken.created_at).skip(skip).limit(limit).to_list()
        total = await query.count()
        
        # Enrich tokens with user information
        enriched_tokens = []
        for token in tokens:
            user = await User.find_one(User.id == token.user_id)
            token_dict = token.dict()
            token_dict['user_info'] = {
                'email': user.email if user else 'Unknown',
                'name': f"{user.first_name} {user.last_name}".strip() if user else 'Unknown',
                'role': user.role.value if user and hasattr(user.role, 'value') else (user.role if user else 'Unknown')
            } if user else None
            
            # Determine current status
            if token.is_used:
                token_dict['current_status'] = 'used'
            elif token.expires_at <= datetime.utcnow():
                token_dict['current_status'] = 'expired'
            else:
                token_dict['current_status'] = 'active'
            
            enriched_tokens.append(token_dict)
        
        return {
            "tokens": enriched_tokens,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting password reset tokens: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve password reset tokens"
        )

@router.delete("/admin/password-reset-tokens/{token_id}")
async def revoke_password_reset_token(
    token_id: str,
    current_user: dict = Depends(require_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Revoke a password reset token
    """
    try:
        # Find and update the token
        token = await PasswordResetToken.find_one(PasswordResetToken.id == token_id)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found"
            )
        
        # Mark as used/revoked
        token.is_used = True
        token.used_at = datetime.utcnow()
        await token.save()
        
        logger.info(f"Admin {current_user.get('email')} revoked password reset token {token_id}")
        
        return {"message": "Password reset token revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking password reset token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke password reset token"
        )

@router.post("/admin/force-password-reset/{user_id}")
async def admin_force_password_reset(
    user_id: str,
    new_password: str,
    current_user: dict = Depends(require_super_admin),  # Only super admin can force reset
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Admin endpoint to directly reset a user's password without email verification
    """
    try:
        # Find the user
        user = await User.find_one(User.id == user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Validate new password
        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        
        # Update user password
        user.password_hash = get_password_hash(new_password)
        await user.save()
        
        # Invalidate any existing reset tokens for this user
        existing_tokens = await PasswordResetToken.find(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.is_used == False
        ).to_list()
        
        for token in existing_tokens:
            token.is_used = True
            token.used_at = datetime.utcnow()
            await token.save()
        
        logger.info(f"Super admin {current_user.get('email')} force reset password for user: {user.email} (Role: {user.role})")
        
        return {
            "message": "Password reset successfully",
            "user_email": user.email,
            "user_role": user.role.value if hasattr(user.role, 'value') else user.role
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in admin force password reset: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to force reset password"
        )

# ============================================================================
# JWT REFRESH TOKEN ENDPOINT
# ============================================================================

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Refresh JWT access token using refresh token"""
    try:
        # Use the JWT manager to refresh the access token
        from backend.utils.jwt_auth import get_jwt_manager, create_refresh_token
        from backend.core.token_blacklist import blacklist_token
        
        jwt_manager = get_jwt_manager()
        
        # First verify the refresh token is valid
        decoded_token = jwt_manager.decode_token(refresh_data.refresh_token)
        user_id = decoded_token.get('sub')
        
        # Check if refresh token is already blacklisted
        from backend.core.token_blacklist import is_token_blacklisted
        if await is_token_blacklisted(db, refresh_data.refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        # Create new access token
        new_access_token = jwt_manager.refresh_access_token(refresh_data.refresh_token)
        
        # Create a new refresh token
        new_refresh_token = create_refresh_token(user_id)
        
        # Blacklist the old refresh token (refresh token rotation)
        await blacklist_token(db, refresh_data.refresh_token, "refresh_token_used")
        
        # Calculate expiry time
        expires_delta = timedelta(minutes=jwt_manager.config.access_token_expire_minutes)
        expires_in = int(expires_delta.total_seconds())
        
        logger.info("Access token refreshed successfully")
        
        return RefreshTokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=expires_in
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

# ============================================================================
# LOGOUT ENDPOINT
# ============================================================================

class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None

@router.post("/logout")
async def logout(
    logout_data: LogoutRequest,
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Logout user by blacklisting their tokens"""
    try:
        access_token = credentials.credentials
        
        # Import blacklist function
        from backend.core.token_blacklist import blacklist_token
        
        # Blacklist the access token
        await blacklist_token(db, access_token, "logout")
        
        # If refresh token is provided, blacklist it too
        if logout_data.refresh_token:
            await blacklist_token(db, logout_data.refresh_token, "logout")
        
        # Log logout event
        audit_logger = get_audit_logger()
        await audit_logger.log_logout(
            db=db,
            user_id=str(current_user.id),
            email=current_user.email,
            ip_address="127.0.0.1",  # TODO: Get real IP from request
            user_agent="Unknown",    # TODO: Get real user agent from request
            logout_type="manual"
        )
        
        logger.info(f"User {current_user.email} logged out successfully")
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        # Even if blacklisting fails, we should still return success
        # to avoid confusing the user
        return {"message": "Logged out successfully"}

@router.post("/logout-all")
async def logout_all(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Logout user from all devices by blacklisting all their tokens"""
    try:
        # Import blacklist function
        from backend.core.token_blacklist import blacklist_all_user_tokens
        
        user_id = current_user.get('id') or str(current_user.get('_id'))
        
        # Blacklist all tokens for this user
        blacklisted_count = await blacklist_all_user_tokens(db, user_id, "logout_all")
        
        # Log logout all event
        audit_logger = get_audit_logger()
        await audit_logger.log_logout(
            db=db,
            user_id=user_id,
            email=current_user.email,
            ip_address="127.0.0.1",  # TODO: Get real IP from request
            user_agent="Unknown",    # TODO: Get real user agent from request
            logout_type="all_devices"
        )
        
        logger.info(f"User {current_user.email} logged out from all devices ({blacklisted_count} tokens blacklisted)")
        
        return {
            "message": "Logged out from all devices successfully",
            "tokens_revoked": blacklisted_count
        }
        
    except Exception as e:
        logger.error(f"Logout all failed: {str(e)}")
        # Even if blacklisting fails, we should still return success
        return {"message": "Logged out from all devices successfully"}