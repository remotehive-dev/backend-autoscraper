from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase
import re

from backend.core.database import get_db
from backend.database.services import JobPostService, EmployerService
from backend.models.mongodb_models import User, JobPost, Employer
from backend.core.enums import JobStatus
from backend.core.auth_middleware import require_admin, require_employer, require_job_seeker
from backend.core.local_auth import get_current_user
from backend.schemas.job_post import (
    JobPost as JobPostSchema,
    JobPostCreate,
    JobPostUpdate,
    JobPostStatusUpdate,
    JobPostList,
    JobPostSearch,
    JobPostStats
)

router = APIRouter()

# RBAC middleware functions will be used as dependencies in endpoints

def get_admin_or_employer_user(current_user: User = Depends(get_current_user)):
    """Dependency to ensure user is an admin, super_admin, or employer"""
    user_role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
    if user_role not in ["admin", "super_admin", "employer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins, super_admins, or employers can access this endpoint"
        )
    return current_user

@router.post("/", response_model=JobPostSchema)
async def create_job_post(
    job_data: JobPostCreate,
    current_user: User = Depends(get_admin_or_employer_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Create a new job post"""
    try:
        # Handle different user roles
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
        logger.info(f"User role: {user_role}, employer_id: {job_data.employer_id}")
        
        if user_role in ["admin", "super_admin"]:
            # Admin users can create jobs for any employer
            if not job_data.employer_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admin users must specify employer_id when creating jobs"
                )
            
            # Verify the employer exists
            employer_service = EmployerService()
            employer = await employer_service.get_employer_by_id(db, job_data.employer_id)
            logger.info(f"Employer lookup result: {employer.company_name if employer else 'None'}")
            if not employer:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Specified employer not found"
                )
        else:
            # Employer users use their own profile
            employer_service = EmployerService()
            employer = await employer_service.get_employer_by_user_id(db, current_user.id)
            
            if not employer:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Employer profile not found. Please complete your employer profile first."
                )
        
        # Create job post data
        job_post_data = job_data.dict()
        # Remove employer_id from job_post_data since it will be passed as a separate parameter
        job_post_data.pop("employer_id", None)
        
        # Create job post
        job_post_service = JobPostService()
        job_post = await job_post_service.create_job_post(employer.id, job_post_data)
        
        logger.info(f"Job post created: {job_post.id} by employer {employer.id}")
        return JobPostSchema.from_orm(job_post)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create job post: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job post"
        )

@router.get("/", response_model=JobPostList)
async def get_job_posts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[JobStatus] = Query(None),
    job_type: Optional[str] = Query(None),
    work_location: Optional[str] = Query(None),
    experience_level: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    remote_only: bool = Query(False),
    featured_only: bool = Query(False),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    print("ENDPOINT REACHED - get_job_posts called")
    logger.info("ENDPOINT REACHED - get_job_posts called")
    """Get list of job posts with filtering and pagination"""
    try:
        skip = (page - 1) * per_page
        logger.info(f"Pagination: page={page}, per_page={per_page}, skip={skip}")
        
        # Use JobPostService for querying
        job_post_service = JobPostService()
        logger.info("JobPostService initialized")
        
        # Get job posts with filters
        status_str = status.value if status else "active"
        logger.info(f"Calling get_job_posts with filters: search={search}, job_type={job_type}, location={location}, status={status_str}")
        job_posts = await job_post_service.get_job_posts(
            db=db,
            skip=skip,
            limit=per_page,
            search=search,
            job_type=job_type,
            location=location,
            status=status_str
        )
        logger.info(f"Retrieved {len(job_posts)} job posts")
        
        # Get total count for pagination using MongoDB
        filter_dict = {}
        
        if status is not None:
            filter_dict["status"] = status.value
        else:
            filter_dict["status"] = "active"
        
        if search:
            filter_dict["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
                {"company_name": {"$regex": search, "$options": "i"}}
            ]
        
        if job_type:
            filter_dict["job_type"] = job_type
        
        if location:
            location_filter = {
                "$or": [
                    {"location_city": {"$regex": location, "$options": "i"}},
                    {"location_state": {"$regex": location, "$options": "i"}},
                    {"location_country": {"$regex": location, "$options": "i"}}
                ]
            }
            if "$or" in filter_dict:
                filter_dict = {"$and": [filter_dict, location_filter]}
            else:
                filter_dict.update(location_filter)
        
        if remote_only:
            filter_dict["work_location"] = "remote"
        
        if featured_only:
            filter_dict["is_featured"] = True
            
        total = await db.job_posts.count_documents(filter_dict)
        
        return JobPostList(
            jobs=[JobPostSchema.from_orm(job) for job in job_posts],
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page
        )
        
    except Exception as e:
        logger.error(f"Failed to get job posts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve job posts"
        )

@router.get("/my-jobs", response_model=JobPostList)
async def get_my_job_posts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[JobStatus] = Query(None),
    current_user: User = Depends(require_employer()),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get job posts for the current employer"""
    try:
        # Get employer profile
        employer_service = EmployerService()
        employer = await employer_service.get_employer_by_user_id(db, current_user.id)
        
        if not employer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employer profile not found"
            )
        
        skip = (page - 1) * per_page
        
        # Get job posts by employer
        job_post_service = JobPostService()
        job_posts = job_post_service.get_job_posts_by_employer(
            db=db,
            employer_id=employer.id,
            skip=skip,
            limit=per_page
        )
        
        # Get total count
        query = db.query(JobPost).filter(JobPost.employer_id == employer.id)
        if status:
            query = query.filter(JobPost.status == status)
        total = query.count()
        
        return JobPostList(
            jobs=[JobPostSchema.from_orm(job) for job in job_posts],
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get employer job posts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job posts"
        )

@router.get("/stats", response_model=JobPostStats)
async def get_job_post_statistics(
    current_user: Dict[str, Any] = Depends(require_admin()),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get job post statistics (admin only)"""
    try:
        # Get various statistics
        total_jobs = db.query(JobPost).count()
        active_jobs = db.query(JobPost).filter(JobPost.status == JobStatus.ACTIVE).count()
        draft_jobs = db.query(JobPost).filter(JobPost.status == JobStatus.DRAFT).count()
        closed_jobs = db.query(JobPost).filter(JobPost.status == JobStatus.CLOSED).count()
        featured_jobs = db.query(JobPost).filter(JobPost.is_featured == True).count()
        
        # Get job type distribution
        job_type_stats = db.query(
            JobPost.job_type,
            func.count(JobPost.id).label('count')
        ).group_by(JobPost.job_type).all()
        
        # Get location distribution
        location_stats = db.query(
            JobPost.work_location,
            func.count(JobPost.id).label('count')
        ).group_by(JobPost.work_location).all()
        
        return JobPostStats(
            total_jobs=total_jobs,
            active_jobs=active_jobs,
            draft_jobs=draft_jobs,
            closed_jobs=closed_jobs,
            featured_jobs=featured_jobs,
            job_type_distribution={stat.job_type: stat.count for stat in job_type_stats},
            location_distribution={stat.work_location: stat.count for stat in location_stats}
        )
        
    except Exception as e:
        logger.error(f"Failed to get job statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job statistics"
        )

@router.get("/{job_id}", response_model=JobPostSchema)
async def get_job_post(
    job_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Get a specific job post by ID"""
    try:
        job_post_service = JobPostService()
        job_post = await job_post_service.get_job_post_by_id(db, job_id)
        
        if not job_post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job post not found"
            )
        
        # Increment view count
        job_post_service.increment_view_count(db, job_id)
        
        return JobPostSchema.from_orm(job_post)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job post {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job post"
        )

@router.put("/{job_id}", response_model=JobPostSchema)
async def update_job_post(
    job_id: int,
    job_update: JobPostUpdate,
    current_user: Dict[str, Any] = Depends(require_employer()),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update a job post"""
    try:
        # Get employer profile
        employer = EmployerService.get_employer_by_user_id(db, current_user.get("id"))
        
        if not employer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employer profile not found"
            )
        
        # Get job post
        job_post_service = JobPostService()
        job_post = job_post_service.get_job_post_by_id(db, job_id)
        
        if not job_post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job post not found"
            )
        
        # Check ownership
        if job_post.employer_id != employer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own job posts"
            )
        
        # Update job post
        update_data = job_update.dict(exclude_unset=True)
        updated_job = job_post_service.update_job_post(db, job_id, **update_data)
        
        logger.info(f"Job post updated: {job_id} by employer {employer.id}")
        return JobPostSchema.from_orm(updated_job)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update job post {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update job post"
        )

@router.patch("/{job_id}/status", response_model=JobPostSchema)
async def update_job_post_status(
    job_id: int,
    status_update: JobPostStatusUpdate,
    current_user: User = Depends(require_employer()),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Update job post status"""
    try:
        # Get employer profile
        employer = EmployerService.get_employer_by_user_id(db, current_user.id)
        
        if not employer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employer profile not found"
            )
        
        # Get job post
        job_post_service = JobPostService()
        job_post = job_post_service.get_job_post_by_id(db, job_id)
        
        if not job_post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job post not found"
            )
        
        # Check ownership
        if job_post.employer_id != employer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own job posts"
            )
        
        # Update status
        updated_job = job_post_service.update_job_post(
            db, job_id, status=status_update.status
        )
        
        logger.info(f"Job post status updated: {job_id} to {status_update.status}")
        return JobPostSchema.from_orm(updated_job)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update job post status {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update job post status"
        )

@router.delete("/{job_id}")
async def delete_job_post(
    job_id: int,
    current_user: User = Depends(require_employer()),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """Delete a job post"""
    try:
        # Get employer profile
        employer = EmployerService.get_employer_by_user_id(db, current_user.id)
        
        if not employer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employer profile not found"
            )
        
        # Get job post
        job_post_service = JobPostService()
        job_post = job_post_service.get_job_post_by_id(db, job_id)
        
        if not job_post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job post not found"
            )
        
        # Check ownership
        if job_post.employer_id != employer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own job posts"
            )
        
        # Delete job post
        db.delete(job_post)
        db.commit()
        
        logger.info(f"Job post deleted: {job_id} by employer {employer.id}")
        return {"message": "Job post deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete job post {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete job post"
        )

@router.get("/health")
async def jobs_health():
    """Health check for jobs endpoints"""
    return {"status": "healthy", "service": "jobs"}