from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
import json

from backend.database.database import get_mongodb_session as get_db
from backend.core.auth import get_current_user, get_admin
from backend.database.services import JobSeekerService, UserService, JobPostService
from backend.models.mongodb_models import (
    User, JobSeeker, UserRole, JobPost, JobApplication,
    SavedJob, AutoApplySettings
    # Interview model not available in MongoDB structure
)
from backend.schemas.job_seeker import (
    JobSeeker as JobSeekerSchema,
    JobSeekerCreate,
    JobSeekerUpdate,
    JobSeekerProfile,
    JobSeekerList,
    JobSeekerStats,
    JobSeekerDashboardStats,
    JobRecommendation,
    ProfileStrength
)
from backend.schemas.saved_job import SavedJobResponse as SavedJob
from backend.schemas.auto_apply import AutoApplySettingsResponse as AutoApplySettings
from backend.schemas.interview import InterviewResponse as Interview
from backend.schemas.saved_job import SavedJobCreate, SavedJobResponse, SavedJobList
from backend.schemas.interview import InterviewResponse, InterviewList, InterviewStats
from backend.schemas.auto_apply import AutoApplySettingsResponse, AutoApplySettingsUpdate, AutoApplyStats
from backend.services.ai_service import ai_service

router = APIRouter()

@router.get("/profile", response_model=JobSeekerProfile)
async def get_job_seeker_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get current job seeker's profile"""
    # Check if user is a job seeker
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    job_seeker = await JobSeekerService.get_job_seeker_by_user_id(db, str(current_user['id']))
    
    if not job_seeker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job seeker profile not found"
        )
    
    # Create profile with user info
    profile_data = {
        "id": str(job_seeker.id),
        "user_id": str(job_seeker.user_id),
        "skills": job_seeker.skills,
        "experience_level": job_seeker.experience_level,
        "preferred_locations": job_seeker.preferred_locations,
        "resume_url": job_seeker.resume_url,
        "portfolio_url": job_seeker.portfolio_url,
        "linkedin_url": job_seeker.linkedin_url,
        "github_url": job_seeker.github_url,
        "bio": job_seeker.bio,
        "is_actively_looking": job_seeker.is_actively_looking,
        "salary_expectation_min": job_seeker.salary_expectation_min,
        "salary_expectation_max": job_seeker.salary_expectation_max,
        "availability_date": job_seeker.availability_date,
        "created_at": job_seeker.created_at,
        "updated_at": job_seeker.updated_at,
        "user": {
            "id": str(current_user.get("id")) if current_user.get("id") else None,
            "email": current_user.get("email"),
            "first_name": current_user.get("full_name", "").split(" ")[0] if current_user.get("full_name") else "",
            "last_name": " ".join(current_user.get("full_name", "").split(" ")[1:]) if current_user.get("full_name") and len(current_user.get("full_name", "").split(" ")) > 1 else "",
            "is_active": current_user.get("is_active"),
            "is_verified": current_user.get("is_verified")
        }
    }
    return JobSeekerProfile(**profile_data)

@router.get("/dashboard-stats", response_model=JobSeekerDashboardStats)
async def get_dashboard_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get dashboard statistics for job seeker"""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    try:
        # Get job seeker profile
        job_seeker = await JobSeeker.find_one(JobSeeker.user_id == str(current_user.get("id")))
        if not job_seeker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Convert job seeker ID to string for MongoDB queries
        job_seeker_id_str = str(job_seeker.id)
        
        # Get real statistics from database
        applications_sent = await db.job_applications.count_documents(
            {"job_seeker_id": job_seeker_id_str}
        )
        
        # saved_jobs and interviews collections don't exist in MongoDB yet
        saved_jobs_count = 0
        interview_requests = 0
        
        # Calculate response rate
        total_applications = applications_sent
        responses = await db.job_applications.count_documents({
            "job_seeker_id": job_seeker_id_str,
            "status": {"$in": ["interview_scheduled", "offer_received", "rejected"]}
        })
        
        response_rate = responses / total_applications if total_applications > 0 else 0.0
        
        # Get last activity (most recent application)
        last_application = await db.job_applications.find_one(
            {"job_seeker_id": job_seeker_id_str},
            sort=[("applied_at", -1)]
        )
        
        # Set last activity based on most recent application
        if last_application:
            last_activity = last_application["applied_at"]
        else:
            last_activity = datetime.now() - timedelta(days=30)
        
        stats = JobSeekerDashboardStats(
            applications_sent=applications_sent,
            saved_jobs=saved_jobs_count,
            profile_views=getattr(job_seeker, 'profile_views', 0) or 0,
            interview_requests=interview_requests,
            response_rate=response_rate,
            last_activity=last_activity
        )
        return stats
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard statistics"
        )

@router.get("/recommendations")
async def get_job_recommendations(
    limit: int = Query(10, ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get job recommendations for job seeker"""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    try:
        # Get job seeker profile
        job_seeker = await JobSeeker.find_one(JobSeeker.user_id == str(current_user.get("id")))
        if not job_seeker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Get job recommendations using AI service
        recommendations = await ai_service.get_job_recommendations(
            job_seeker_id=str(job_seeker.id),
            db=db,
            limit=limit
        )
        
        return {"recommendations": recommendations}
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job recommendations"
        )

@router.get("/saved-jobs", response_model=SavedJobList)
async def get_saved_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get saved jobs for the current user"""
    # Verify user is a job seeker
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only job seekers can access saved jobs"
        )
    
    try:
        # Get job seeker profile
        job_seeker = await JobSeeker.find_one(JobSeeker.user_id == str(current_user.get("id")))
        if not job_seeker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Get saved jobs with pagination
        saved_jobs = await SavedJob.find(
            SavedJob.job_seeker_id == str(job_seeker.id)
        ).skip(skip).limit(limit).to_list()
        
        # Get total count
        total = await SavedJob.find(
            SavedJob.job_seeker_id == str(job_seeker.id)
        ).count()
        
        # Build response with job post details
        saved_jobs_data = []
        for saved_job in saved_jobs:
            job_post = await JobPost.find_one(JobPost.id == saved_job.job_post_id)
            if job_post:
                saved_jobs_data.append({
                    "id": str(saved_job.id),
                    "job_post_id": saved_job.job_post_id,
                    "saved_at": saved_job.saved_at,
                    "notes": saved_job.notes,
                    "job_post": {
                        "id": str(job_post.id),
                        "title": job_post.title,
                        "company": job_post.company,
                        "location": job_post.location,
                        "salary_min": job_post.salary_min,
                        "salary_max": job_post.salary_max,
                        "job_type": job_post.job_type,
                        "posted_at": job_post.posted_at
                    }
                })
        
        return SavedJobList(
            saved_jobs=saved_jobs_data,
            total=total,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error getting saved jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve saved jobs"
        )

@router.post("/saved-jobs", response_model=SavedJobResponse)
async def save_job(
    saved_job_data: SavedJobCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Save a job for the current user"""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only job seekers can save jobs"
        )
    
    try:
        # Get job seeker profile
        job_seeker = await JobSeeker.find_one(JobSeeker.user_id == str(current_user.get("id")))
        if not job_seeker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Check if job post exists
        job_post = await JobPost.find_one(JobPost.id == saved_job_data.job_post_id)
        if not job_post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job post not found"
            )
        
        # Check if already saved
        existing_saved = await SavedJob.find_one(
            SavedJob.job_seeker_id == str(job_seeker.id),
            SavedJob.job_post_id == saved_job_data.job_post_id
        )
        
        if existing_saved:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job already saved"
            )
        
        # Create saved job
        saved_job = SavedJob(
            job_seeker_id=str(job_seeker.id),
            job_post_id=saved_job_data.job_post_id,
            notes=saved_job_data.notes,
            saved_at=datetime.now()
        )
        
        await saved_job.insert()
        
        return SavedJobResponse(
            id=str(saved_job.id),
            job_post_id=saved_job.job_post_id,
            saved_at=saved_job.saved_at,
            notes=saved_job.notes,
            job_post={
                "id": str(job_post.id),
                "title": job_post.title,
                "company": job_post.company,
                "location": job_post.location,
                "salary_min": job_post.salary_min,
                "salary_max": job_post.salary_max,
                "job_type": job_post.job_type,
                "posted_at": job_post.posted_at
            }
        )
    except Exception as e:
        logger.error(f"Error saving job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save job"
        )

@router.delete("/saved-jobs/{saved_job_id}")
async def unsave_job(
    saved_job_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Remove a saved job"""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only job seekers can unsave jobs"
        )
    
    try:
        # Get job seeker profile
        job_seeker = await JobSeeker.find_one(JobSeeker.user_id == str(current_user.get("id")))
        if not job_seeker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Find and delete saved job
        saved_job = await SavedJob.find_one(
            SavedJob.id == saved_job_id,
            SavedJob.job_seeker_id == str(job_seeker.id)
        )
        
        if not saved_job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved job not found"
            )
        
        await saved_job.delete()
        
        return {"message": "Job unsaved successfully"}
    except Exception as e:
        logger.error(f"Error unsaving job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unsave job"
        )

@router.get("/auto-apply-settings", response_model=AutoApplySettingsResponse)
async def get_auto_apply_settings(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get auto-apply settings for job seeker"""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    try:
        # Get job seeker profile
        job_seeker = await JobSeeker.find_one(JobSeeker.user_id == str(current_user.get("id")))
        if not job_seeker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Get auto-apply settings
        settings = await AutoApplySettings.find_one(
            AutoApplySettings.job_seeker_id == str(job_seeker.id)
        )
        
        if not settings:
            # Create default settings if none exist
            settings = AutoApplySettings(
                job_seeker_id=str(job_seeker.id),
                enabled=False,
                max_applications_per_day=5,
                keywords=[],
                excluded_companies=[],
                salary_min=None,
                location_preferences=[],
                job_types=[],
                experience_level=None
            )
            await settings.insert()
        
        return AutoApplySettingsResponse(
            id=str(settings.id),
            enabled=settings.enabled,
            max_applications_per_day=settings.max_applications_per_day,
            keywords=settings.keywords or [],
            excluded_companies=settings.excluded_companies or [],
            salary_min=settings.salary_min,
            location_preferences=settings.location_preferences or [],
            job_types=settings.job_types or [],
            experience_level=settings.experience_level,
            created_at=settings.created_at,
            updated_at=settings.updated_at
        )
    except Exception as e:
        logger.error(f"Error getting auto-apply settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve auto-apply settings"
        )

@router.put("/auto-apply-settings", response_model=AutoApplySettingsResponse)
async def update_auto_apply_settings(
    settings_update: AutoApplySettingsUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update auto-apply settings for job seeker"""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    try:
        # Get job seeker profile
        job_seeker = await JobSeeker.find_one(JobSeeker.user_id == str(current_user.get("id")))
        if not job_seeker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Get existing settings
        settings = await AutoApplySettings.find_one(
            AutoApplySettings.job_seeker_id == job_seeker.id
        )
        
        if not settings:
            # Create new settings if none exist
            settings = AutoApplySettings(job_seeker_id=str(job_seeker.id))
            await settings.insert()
        
        # Update settings
        update_data = settings_update.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.now()
        await settings.update({"$set": update_data})
        # Refresh the settings object
        settings = await AutoApplySettings.find_one(AutoApplySettings.id == settings.id)
        
        return AutoApplySettingsResponse(
            id=str(settings.id),
            enabled=settings.enabled,
            max_applications_per_day=settings.max_applications_per_day,
            keywords=settings.keywords or [],
            excluded_companies=settings.excluded_companies or [],
            salary_min=settings.salary_min,
            location_preferences=settings.location_preferences or [],
            job_types=settings.job_types or [],
            experience_level=settings.experience_level,
            created_at=settings.created_at,
            updated_at=settings.updated_at
        )
    except Exception as e:
        logger.error(f"Error updating auto-apply settings: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update auto-apply settings"
        )

@router.get("/profile-strength")
async def get_profile_strength(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get profile strength analysis for job seeker"""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    try:
        # Get job seeker profile
        job_seeker = await JobSeeker.find_one(JobSeeker.user_id == str(current_user.get("id")))
        if not job_seeker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Get profile strength analysis using AI service
        profile_strength = await ai_service.analyze_profile_strength(
            job_seeker_id=str(job_seeker.id),
            db=db
        )
        
        return profile_strength
    except Exception as e:
        logger.error(f"Error getting profile strength: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze profile strength"
        )

@router.get("/interviews", response_model=InterviewList)
async def get_interviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get interviews for job seeker"""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    try:
        # Get job seeker profile
        job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.get("id")).first()
        if not job_seeker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Build query
        interviews_query = db.query(InterviewModel).join(JobPost).filter(
            InterviewModel.job_seeker_id == job_seeker.id
        )
        
        # Apply status filter if provided
        if status_filter:
            interviews_query = interviews_query.filter(
                InterviewModel.status == status_filter
            )
        
        interviews_query = interviews_query.order_by(InterviewModel.scheduled_at.desc())
        
        total = interviews_query.count()
        interviews = interviews_query.offset(skip).limit(limit).all()
        
        # Convert to response format
        interviews_data = []
        for interview in interviews:
            job_post = interview.job_post
            interviews_data.append(InterviewResponse(
                id=interview.id,
                job_post_id=interview.job_post_id,
                interview_type=interview.interview_type,
                status=interview.status,
                scheduled_at=interview.scheduled_at,
                duration_minutes=interview.duration_minutes,
                meeting_link=interview.meeting_link,
                notes=interview.notes,
                feedback=interview.feedback,
                created_at=interview.created_at,
                updated_at=interview.updated_at,
                job_post={
                    "id": str(job_post.id),
                    "title": job_post.title,
                    "company": job_post.company,
                    "location": job_post.location
                }
            ))
        
        return InterviewList(
            interviews=interviews_data,
            total=total,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error getting interviews: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve interviews"
        )

@router.get("/interviews/stats", response_model=InterviewStats)
async def get_interview_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get interview statistics for job seeker"""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    try:
        # Get job seeker profile
        job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.get("id")).first()
        if not job_seeker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Get interview statistics
        total_interviews = db.query(InterviewModel).filter(
            InterviewModel.job_seeker_id == job_seeker.id
        ).count()
        
        scheduled_interviews = db.query(InterviewModel).filter(
            and_(
                InterviewModel.job_seeker_id == job_seeker.id,
                InterviewModel.status == 'scheduled'
            )
        ).count()
        
        completed_interviews = db.query(InterviewModel).filter(
            and_(
                InterviewModel.job_seeker_id == job_seeker.id,
                InterviewModel.status == 'completed'
            )
        ).count()
        
        # Get upcoming interview
        upcoming_interview = db.query(InterviewModel).filter(
            and_(
                InterviewModel.job_seeker_id == job_seeker.id,
                InterviewModel.status == 'scheduled',
                InterviewModel.scheduled_at > datetime.now()
            )
        ).order_by(InterviewModel.scheduled_at.asc()).first()
        
        return InterviewStats(
            total_interviews=total_interviews,
            scheduled_interviews=scheduled_interviews,
            completed_interviews=completed_interviews,
            upcoming_interview=upcoming_interview.scheduled_at if upcoming_interview else None
        )
    except Exception as e:
        logger.error(f"Error getting interview stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve interview statistics"
        )

@router.post("/career-advice")
async def get_career_advice(
    question: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get personalized career advice using AI"""
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    try:
        # Get job seeker profile
        job_seeker = db.query(JobSeeker).filter(JobSeeker.user_id == current_user.get("id")).first()
        if not job_seeker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job seeker profile not found"
            )
        
        # Get career advice using AI service
        advice = await ai_service.get_career_advice(
            job_seeker_id=job_seeker.id,
            question=question,
            db=db
        )
        
        return {"advice": advice}
    except Exception as e:
        logger.error(f"Error getting career advice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get career advice"
        )

@router.post("/profile", response_model=JobSeekerSchema)
async def create_job_seeker_profile(
    job_seeker_data: JobSeekerCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Create job seeker profile"""
    # Check if user is a job seeker
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    job_seeker_service = JobSeekerService(db)
    
    # Check if profile already exists
    existing_profile = job_seeker_service.get_job_seeker_by_user_id(current_user.get("id"))
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job seeker profile already exists"
        )
    
    try:
        # Create new job seeker profile
        job_seeker_data_dict = job_seeker_data.dict()
        job_seeker_data_dict["user_id"] = current_user.get("id")
        
        job_seeker = job_seeker_service.create_job_seeker(job_seeker_data_dict)
        
        logger.info(f"Created job seeker profile for user {current_user.get('id')}")
        return JobSeekerSchema(
            id=job_seeker.id,
            user_id=job_seeker.user_id,
            skills=job_seeker.skills,
            experience_level=job_seeker.experience_level,
            preferred_locations=job_seeker.preferred_locations,
            resume_url=job_seeker.resume_url,
            portfolio_url=job_seeker.portfolio_url,
            linkedin_url=job_seeker.linkedin_url,
            github_url=job_seeker.github_url,
            bio=job_seeker.bio,
            is_actively_looking=job_seeker.is_actively_looking,
            salary_expectation_min=job_seeker.salary_expectation_min,
            salary_expectation_max=job_seeker.salary_expectation_max,
            availability_date=job_seeker.availability_date,
            created_at=job_seeker.created_at,
            updated_at=job_seeker.updated_at
        )
        
    except Exception as e:
        logger.error(f"Failed to create job seeker profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job seeker profile"
        )

@router.put("/profile", response_model=JobSeekerSchema)
async def update_job_seeker_profile(
    job_seeker_data: JobSeekerUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update job seeker profile"""
    # Check if user is a job seeker
    if current_user.get("role") != "job_seeker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Job seeker role required."
        )
    
    job_seeker_service = JobSeekerService(db)
    job_seeker = job_seeker_service.get_job_seeker_by_user_id(current_user.get("id"))
    
    if not job_seeker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job seeker profile not found"
        )
    
    try:
        # Update job seeker profile
        update_data = job_seeker_data.dict(exclude_unset=True)
        
        updated_job_seeker = job_seeker_service.update_job_seeker(job_seeker.id, update_data)
        
        logger.info(f"Updated job seeker profile for user {current_user.get('id')}")
        return JobSeekerSchema(
            id=str(updated_job_seeker.id),
            user_id=str(updated_job_seeker.user_id),
            skills=updated_job_seeker.skills,
            experience_level=updated_job_seeker.experience_level,
            preferred_locations=updated_job_seeker.preferred_locations,
            resume_url=updated_job_seeker.resume_url,
            portfolio_url=updated_job_seeker.portfolio_url,
            linkedin_url=updated_job_seeker.linkedin_url,
            github_url=updated_job_seeker.github_url,
            bio=updated_job_seeker.bio,
            is_actively_looking=updated_job_seeker.is_actively_looking,
            salary_expectation_min=updated_job_seeker.salary_expectation_min,
            salary_expectation_max=updated_job_seeker.salary_expectation_max,
            availability_date=updated_job_seeker.availability_date,
            created_at=updated_job_seeker.created_at,
            updated_at=updated_job_seeker.updated_at
        )
        
    except Exception as e:
        logger.error(f"Failed to update job seeker profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update job seeker profile"
        )

@router.get("/", response_model=JobSeekerList)
async def get_job_seekers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    is_actively_looking: Optional[bool] = Query(None),
    experience_level: Optional[str] = Query(None),
    skills: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(get_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get list of job seekers (admin only)"""
    try:
        # JobSeekerService uses static methods, no need to instantiate with db
        
        # Build filters
        filters = {}
        if is_actively_looking is not None:
            filters["is_actively_looking"] = is_actively_looking
        if experience_level:
            filters["experience_level"] = experience_level
        if skills:
            filters["skills_contains"] = skills
        if location:
            filters["location_contains"] = location
        
        # Get job seekers with pagination using static method
        skip = (page - 1) * per_page
        search_term = skills or location  # Use skills or location as search term
        job_seekers = await JobSeekerService.get_job_seekers(
            db=db,
            search=search_term,
            skip=skip,
            limit=per_page
        )
        
        # For now, set total to length of results (can be improved with count query)
        total = len(job_seekers)
        
        # Calculate pagination info
        pages = (total + per_page - 1) // per_page
        
        return JobSeekerList(
            job_seekers=[
                JobSeekerSchema(
                    id=str(js.id),
                    user_id=str(js.user_id),
                    skills=js.skills,
                    experience_level=js.experience_level,
                    preferred_locations=js.preferred_locations,
                    resume_url=js.resume_url,
                    portfolio_url=js.portfolio_url,
                    linkedin_url=js.linkedin_url,
                    github_url=js.github_url,
                    bio=js.bio,
                    is_actively_looking=js.is_actively_looking,
                    salary_expectation_min=js.salary_expectation_min,
                    salary_expectation_max=js.salary_expectation_max,
                    availability_date=js.availability_date,
                    created_at=js.created_at,
                    updated_at=js.updated_at
                ) for js in job_seekers
            ],
            total=total,
            page=page,
            per_page=per_page,
            pages=pages
        )
        
    except Exception as e:
        logger.error(f"Failed to get job seekers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job seekers"
        )

@router.get("/stats", response_model=JobSeekerStats)
async def get_job_seeker_stats(
    current_user: User = Depends(get_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get job seeker statistics (admin only)"""
    try:
        # For now, return basic stats using available static methods
        # Get all job seekers to calculate basic stats
        all_job_seekers = await JobSeekerService.get_job_seekers(db=db, skip=0, limit=1000)
        
        # Total job seekers
        total_job_seekers = len(all_job_seekers)
        
        # Active job seekers (those actively looking)
        active_job_seekers = len([js for js in all_job_seekers if getattr(js, 'is_actively_looking', False)])
        
        # New job seekers this month (simplified)
        month_ago = datetime.utcnow() - timedelta(days=30)
        new_job_seekers_this_month = 0  # Placeholder - would need created_at filtering
        
        # Average applications per seeker (placeholder)
        avg_applications_per_seeker = 0.0
        
        # Top skills (simplified)
        top_skills = []
        
        # Experience level distribution (simplified)
        experience_level_distribution = {}
        
        return JobSeekerStats(
            total_job_seekers=total_job_seekers,
            active_job_seekers=active_job_seekers,
            new_job_seekers_this_month=new_job_seekers_this_month,
            avg_applications_per_seeker=avg_applications_per_seeker,
            top_skills=top_skills,
            experience_level_distribution=experience_level_distribution
        )
        
    except Exception as e:
        logger.error(f"Failed to get job seeker statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job seeker statistics"
        )

@router.get("/{job_seeker_id}", response_model=JobSeekerProfile)
async def get_job_seeker_by_id(
    job_seeker_id: int,
    current_user: User = Depends(get_admin),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get job seeker by ID (admin only)"""
    # For now, return a simple response since get_job_seeker_with_user method doesn't exist
    # This would need to be implemented properly with user joins
    job_seeker = None
    
    if not job_seeker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job seeker not found"
        )
    
    # Create profile with user info
    profile_data = {
        "id": job_seeker.id,
        "user_id": job_seeker.user_id,
        "skills": job_seeker.skills,
        "experience_level": job_seeker.experience_level,
        "preferred_locations": job_seeker.preferred_locations,
        "resume_url": job_seeker.resume_url,
        "portfolio_url": job_seeker.portfolio_url,
        "linkedin_url": job_seeker.linkedin_url,
        "github_url": job_seeker.github_url,
        "bio": job_seeker.bio,
        "is_actively_looking": job_seeker.is_actively_looking,
        "salary_expectation_min": job_seeker.salary_expectation_min,
        "salary_expectation_max": job_seeker.salary_expectation_max,
        "availability_date": job_seeker.availability_date,
        "created_at": job_seeker.created_at,
        "updated_at": job_seeker.updated_at,
        "user": {
            "id": job_seeker.user.id,
            "email": job_seeker.user.email,
            "first_name": job_seeker.user.first_name,
            "last_name": job_seeker.user.last_name,
            "is_active": job_seeker.user.is_active,
            "is_verified": job_seeker.user.is_verified
        } if job_seeker.user else {}
    }
    
    return JobSeekerProfile(**profile_data)