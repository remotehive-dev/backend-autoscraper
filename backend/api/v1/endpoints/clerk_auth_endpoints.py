from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr
from loguru import logger

from backend.core.clerk_auth import clerk_auth
from backend.core.clerk_middleware import (
    ClerkMiddleware, clerk_require_employer, clerk_require_job_seeker,
    ClerkAuthContext
)
from backend.core.database import get_db
# from backend.database.models import User, UserRole  # Using MongoDB models instead
from backend.models.mongodb_models import User, Employer, JobSeeker
from backend.database.services import EmployerService, JobSeekerService  # MongoDB services
from backend.services.lead_service import LeadService

router = APIRouter()

# Request/Response Models
class EmployerSignUpRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    company_name: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None

class JobSeekerSignUpRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    skills: Optional[list] = None
    experience_level: Optional[str] = None

class ClerkAuthResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None
    role: Optional[str] = None
    redirect_url: Optional[str] = None

class ClerkConfigResponse(BaseModel):
    publishable_key: str
    sign_in_url: str
    sign_up_url: str
    after_sign_in_url: str
    after_sign_up_url: str

class ProfileCompletionRequest(BaseModel):
    # Employer fields
    company_name: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    company_description: Optional[str] = None
    website: Optional[str] = None
    
    # Job seeker fields
    skills: Optional[list] = None
    experience_level: Optional[str] = None
    resume_url: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None

# Configuration endpoint
@router.get("/config", response_model=ClerkConfigResponse)
async def get_clerk_config():
    """Get Clerk configuration for frontend"""
    config = clerk_auth.get_frontend_config()
    return ClerkConfigResponse(**config)

# Employer signup endpoint
@router.post("/employer/signup", response_model=ClerkAuthResponse)
async def employer_signup(
    signup_data: EmployerSignUpRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Employer signup with Clerk authentication"""
    logger.info(f"Employer signup attempt for: {signup_data.email}")
    
    try:
        # Create user in Clerk
        clerk_user = await clerk_auth.create_user(
            email=signup_data.email,
            password=signup_data.password,
            first_name=signup_data.first_name,
            last_name=signup_data.last_name,
            phone=signup_data.phone,
            role="employer"
        )
        
        # Create local user record
        user_service = UserService(db)
        user_data = {
            "email": signup_data.email,
            "first_name": signup_data.first_name,
            "last_name": signup_data.last_name,
            "phone": signup_data.phone,
            "role": UserRole.EMPLOYER,
            "clerk_user_id": clerk_user["id"],
            "is_verified": False
        }
        local_user = user_service.create_user(user_data)
        
        # Create employer profile
        employer_data = {
            "company_name": signup_data.company_name or f"{signup_data.first_name} {signup_data.last_name} Company",
            "company_size": signup_data.company_size,
            "industry": signup_data.industry,
            "company_email": signup_data.email,
            "company_description": "New employer profile"
        }
        employer_service = EmployerService()
        employer_profile = await employer_service.create_employer(db, employer_data, local_user.id)
        
        # Create lead for new employer
        try:
            await LeadService.create_lead_from_signup(
                email=signup_data.email,
                name=f"{signup_data.first_name} {signup_data.last_name}",
                role="employer",
                source="clerk_auth",
                metadata={
                    "company_name": signup_data.company_name,
                    "company_size": signup_data.company_size,
                    "industry": signup_data.industry,
                    "clerk_user_id": clerk_user["id"]
                }
            )
        except Exception as e:
            logger.warning(f"Failed to create lead for employer {signup_data.email}: {e}")
        
        logger.info(f"Employer signup successful for: {signup_data.email}")
        
        return ClerkAuthResponse(
            success=True,
            message="Employer account created successfully. Please verify your email.",
            user_id=str(local_user.id),
            role="employer",
            redirect_url="/employer/dashboard"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during employer signup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create employer account"
        )

# Job seeker signup endpoint
@router.post("/job-seeker/signup", response_model=ClerkAuthResponse)
async def job_seeker_signup(
    signup_data: JobSeekerSignUpRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Job seeker signup with Clerk authentication"""
    logger.info(f"Job seeker signup attempt for: {signup_data.email}")
    
    try:
        # Create user in Clerk
        clerk_user = await clerk_auth.create_user(
            email=signup_data.email,
            password=signup_data.password,
            first_name=signup_data.first_name,
            last_name=signup_data.last_name,
            phone=signup_data.phone,
            role="job_seeker"
        )
        
        # Create local user record
        user_service = UserService(db)
        user_data = {
            "email": signup_data.email,
            "first_name": signup_data.first_name,
            "last_name": signup_data.last_name,
            "phone": signup_data.phone,
            "role": UserRole.JOB_SEEKER,
            "clerk_user_id": clerk_user["id"],
            "is_verified": False
        }
        local_user = user_service.create_user(user_data)
        
        # Create job seeker profile
        job_seeker_data = {
            "skills": signup_data.skills or [],
            "experience_level": signup_data.experience_level or "entry",
            "current_title": "Job Seeker",
            "is_actively_looking": True
        }
        job_seeker_profile = await JobSeekerService.create_job_seeker(db, local_user.id, job_seeker_data)
        
        # Create lead for new job seeker
        try:
            await LeadService.create_lead_from_signup(
                email=signup_data.email,
                name=f"{signup_data.first_name} {signup_data.last_name}",
                role="job_seeker",
                source="clerk_auth",
                metadata={
                    "skills": signup_data.skills or [],
                    "experience_level": signup_data.experience_level,
                    "clerk_user_id": clerk_user["id"]
                }
            )
        except Exception as e:
            logger.warning(f"Failed to create lead for job seeker {signup_data.email}: {e}")
        
        logger.info(f"Job seeker signup successful for: {signup_data.email}")
        
        return ClerkAuthResponse(
            success=True,
            message="Job seeker account created successfully. Please verify your email.",
            user_id=str(local_user.id),
            role="job_seeker",
            redirect_url="/job-seeker/dashboard"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during job seeker signup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job seeker account"
        )

# Profile completion endpoint for employers
@router.post("/employer/complete-profile", response_model=ClerkAuthResponse)
async def complete_employer_profile(
    profile_data: ProfileCompletionRequest,
    current_user: Dict[str, Any] = Depends(clerk_require_employer()),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Complete employer profile after signup"""
    try:
        employer_service = EmployerService()
        employer_profile = await employer_service.get_employer_by_user_id(db, current_user["id"])
        
        if not employer_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Employer profile not found"
            )
        
        # Update employer profile
        update_data = {}
        if profile_data.company_name:
            update_data["company_name"] = profile_data.company_name
        if profile_data.company_size:
            update_data["company_size"] = profile_data.company_size
        if profile_data.industry:
            update_data["industry"] = profile_data.industry
        if profile_data.company_description:
            update_data["company_description"] = profile_data.company_description
        if profile_data.website:
            update_data["website"] = profile_data.website
        
        await employer_service.update_employer(db, employer_profile.id, update_data)
        
        return ClerkAuthResponse(
            success=True,
            message="Employer profile completed successfully",
            user_id=current_user["id"],
            role="employer",
            redirect_url="/employer/dashboard"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing employer profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete employer profile"
        )

# Profile completion endpoint for job seekers
@router.post("/job-seeker/complete-profile", response_model=ClerkAuthResponse)
async def complete_job_seeker_profile(
    profile_data: ProfileCompletionRequest,
    current_user: Dict[str, Any] = Depends(clerk_require_job_seeker()),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Complete job seeker profile after signup"""
    try:
        job_seeker_profile = await JobSeekerService.get_job_seeker_by_user_id(db, current_user["id"])
        
        if not job_seeker_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Update job seeker profile
        update_data = {}
        if profile_data.skills:
            update_data["skills"] = profile_data.skills
        if profile_data.experience_level:
            update_data["experience_level"] = profile_data.experience_level
        if profile_data.resume_url:
            update_data["resume_url"] = profile_data.resume_url
        if profile_data.bio:
            update_data["bio"] = profile_data.bio
        if profile_data.location:
            update_data["location"] = profile_data.location
        
        job_seeker_service.update_job_seeker_profile(job_seeker_profile.id, **update_data)
        
        return ClerkAuthResponse(
            success=True,
            message="Job seeker profile completed successfully",
            user_id=current_user["id"],
            role="job_seeker",
            redirect_url="/job-seeker/dashboard"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing job seeker profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete job seeker profile"
        )

# Sync user with backend and create lead for employers
@router.post("/sync-user", response_model=ClerkAuthResponse)
async def sync_user_with_backend(
    sync_data: dict,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Sync Clerk user with backend and create lead for employers"""
    try:
        clerk_user_id = sync_data.get("clerk_user_id")
        email = sync_data.get("email")
        first_name = sync_data.get("first_name")
        last_name = sync_data.get("last_name")
        role = sync_data.get("role", "job_seeker")
        
        if not all([clerk_user_id, email, first_name, last_name]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required user data"
            )
        
        # Check if user already exists
        user_service = UserService(db)
        existing_user = await user_service.get_user_by_email(email)
        
        if not existing_user:
            # Create local user record
            user_data = {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "role": UserRole.EMPLOYER if role == "employer" else UserRole.JOB_SEEKER,
                "clerk_user_id": clerk_user_id,
                "is_verified": True
            }
            local_user = user_service.create_user(user_data)
            
            # Create profile based on role
            if role == "employer":
                employer_data = {
                    "company_name": f"{first_name} {last_name} Company",
                    "company_email": email,
                    "company_description": "New employer profile",
                    "industry": "Not specified",
                    "company_size": "startup"
                }
                await EmployerService.create_employer(db, local_user.id, employer_data)
                
                # Create lead for employer
                try:
                    import requests
                    lead_data = {
                        "user_id": local_user.id,
                        "full_name": f"{first_name} {last_name}",
                        "email": email,
                        "role": "employer",
                        "registration_source": "clerk_registration"
                    }
                    
                    admin_api_url = "http://localhost:3000/api/leads/create-from-registration"
                    response = requests.post(admin_api_url, json=lead_data, timeout=5)
                    
                    if response.status_code != 201:
                        logger.warning(f"Failed to create lead: {response.text}")
                        
                except Exception as lead_error:
                    logger.warning(f"Failed to create lead: {str(lead_error)}")
                    
            elif role == "job_seeker":
                job_seeker_data = {
                    "current_title": "Job Seeker",
                    "experience_level": "entry",
                    "skills": [],
                    "is_actively_looking": True
                }
                await JobSeekerService.create_job_seeker(db, local_user.id, job_seeker_data)
        
        return ClerkAuthResponse(
            success=True,
            message="User synced successfully",
            user_id=str(existing_user.id if existing_user else local_user.id),
            role=role,
            redirect_url=f"/{role}/dashboard" if role in ["employer", "job_seeker"] else "/dashboard"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync user with backend"
        )

# Get current user profile
@router.get("/profile")
async def get_current_user_profile(
    current_user: Dict[str, Any] = Depends(ClerkMiddleware.get_current_user_from_clerk),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get current user profile data"""
    try:
        user_role = current_user.get("role")
        
        if user_role == "employer":
            employer_service = EmployerService()
            employer_profile = await employer_service.get_employer_by_user_id(db, current_user["id"])
            return {
                "user": current_user,
                "profile": employer_profile.__dict__ if employer_profile else None,
                "profile_type": "employer"
            }
        elif user_role == "job_seeker":
            job_seeker_service = JobSeekerService(db)
            job_seeker_profile = job_seeker_service.get_job_seeker_by_user_id(current_user["id"])
            return {
                "user": current_user,
                "profile": job_seeker_profile.__dict__ if job_seeker_profile else None,
                "profile_type": "job_seeker"
            }
        else:
            return {
                "user": current_user,
                "profile": None,
                "profile_type": user_role
            }
            
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )