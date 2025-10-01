from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.database.services import JobApplicationService as ApplicationService, JobPostService
from backend.models.mongodb_models import User, JobApplication as Application, JobPost
from backend.core.enums import UserRole, ApplicationStatus

router = APIRouter()

@router.post("/")
async def create_job_application(
    application_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Create a new job application"""
    # Check if user is a job seeker
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    job_post_id = application_data.get("job_post_id")
    if not job_post_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job post ID is required"
        )
    
    # Check if job post exists
    job_post_service = JobPostService(db)
    job_post = job_post_service.get_job_post(job_post_id)
    if not job_post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job post not found"
        )
    
    application_service = ApplicationService(db)
    
    # Check if user already applied for this job
    existing_application = application_service.get_application_by_user_and_job(
        current_user.get("id"), job_post_id
    )
    if existing_application:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already applied for this job"
        )
    
    try:
        # Create application
        app_data = {
            "user_id": current_user.get("id"),
            "job_post_id": job_post_id,
            "cover_letter": application_data.get("cover_letter"),
            "resume_url": application_data.get("resume_url"),
            "status": ApplicationStatus.PENDING
        }
        
        application = application_service.create_application(app_data)
        
        return {
            "id": application.id,
            "job_post_id": application.job_post_id,
            "cover_letter": application.cover_letter,
            "resume_url": application.resume_url,
            "status": application.status.value,
            "applied_at": application.applied_at
        }
        
    except Exception as e:
        logger.error(f"Error creating job application: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job application"
        )

@router.get("/my-applications")
async def get_my_applications(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get current user's job applications"""
    # Check if user is a job seeker
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    application_service = ApplicationService(db)
    applications = application_service.get_applications_by_user(current_user.get("id"))
    
    return [
        {
            "id": app.id,
            "job_post_id": app.job_post_id,
            "job_title": app.job_post.title if app.job_post else None,
            "company_name": app.job_post.employer.company_name if app.job_post and app.job_post.employer else None,
            "cover_letter": app.cover_letter,
            "resume_url": app.resume_url,
            "status": app.status.value,
            "applied_at": app.applied_at,
            "updated_at": app.updated_at
        }
        for app in applications
    ]

@router.get("/received")
async def get_received_applications(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get applications received by employer"""
    # Check if user is an employer
    if current_user.get("role") != "employer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Employer role required."
        )
    
    application_service = ApplicationService(db)
    applications = application_service.get_applications_by_employer(current_user.get("id"))
    
    return [
        {
            "id": app.id,
            "job_post_id": app.job_post_id,
            "job_title": app.job_post.title if app.job_post else None,
            "applicant_name": f"{app.user.first_name} {app.user.last_name}" if app.user else None,
            "applicant_email": app.user.email if app.user else None,
            "cover_letter": app.cover_letter,
            "resume_url": app.resume_url,
            "status": app.status.value,
            "applied_at": app.applied_at,
            "updated_at": app.updated_at
        }
        for app in applications
    ]

@router.patch("/{application_id}/status")
async def update_application_status(
    application_id: int,
    status_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update application status"""
    # Check if user is an employer
    if current_user.get("role") != "employer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Employer role required."
        )
    
    new_status = status_data.get("status")
    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status is required"
        )
    
    # Validate status
    try:
        status_enum = ApplicationStatus(new_status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in ApplicationStatus]}"
        )
    
    application_service = ApplicationService(db)
    application = application_service.get_application(application_id)
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check if the employer owns the job post
    if application.job_post.employer.user_id != current_user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only update applications for your own job posts."
        )
    
    try:
        updated_application = application_service.update_application_status(
            application_id, status_enum
        )
        
        return {
            "id": updated_application.id,
            "job_post_id": updated_application.job_post_id,
            "status": updated_application.status.value,
            "updated_at": updated_application.updated_at
        }
        
    except Exception as e:
        logger.error(f"Error updating application status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update application status"
        )