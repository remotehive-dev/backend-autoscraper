from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session  # Using MongoDB instead
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from backend.database import get_db_session
from backend.database.services import JobPostService, EmployerService
from backend.database.models import JobPost

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Pydantic models for request/response
class JobPostCreate(BaseModel):
    title: str
    description: str
    requirements: Optional[str] = None
    job_type: str = "full-time"  # full-time, part-time, contract, internship
    location_type: str = "remote"  # remote, hybrid, on-site
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    experience_level: Optional[str] = None  # entry, mid, senior, executive
    category: Optional[str] = None
    tags: Optional[str] = None  # JSON string of tags
    application_url: Optional[str] = None
    application_email: Optional[str] = None
    employer_id: int
    is_featured: bool = False
    expires_at: Optional[datetime] = None

class JobPostUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    job_type: Optional[str] = None
    location_type: Optional[str] = None
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    experience_level: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    application_url: Optional[str] = None
    application_email: Optional[str] = None
    is_featured: Optional[bool] = None
    status: Optional[str] = None
    expires_at: Optional[datetime] = None

class JobPostResponse(BaseModel):
    id: int
    title: str
    description: str
    requirements: Optional[str] = None
    job_type: str
    location_type: str
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str
    experience_level: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    application_url: Optional[str] = None
    application_email: Optional[str] = None
    company_name: Optional[str] = None
    employer_id: int
    is_featured: bool
    status: str
    views_count: Optional[int] = None
    applications_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class JobsListResponse(BaseModel):
    jobs: List[JobPostResponse]
    total: int
    page: int
    limit: int

@router.get("/", response_model=JobsListResponse)
async def get_jobs(
    search: Optional[str] = Query(None, description="Search term for job title, description, or company"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    location: Optional[str] = Query(None, description="Filter by location"),
    category: Optional[str] = Query(None, description="Filter by category"),
    experience_level: Optional[str] = Query(None, description="Filter by experience level"),
    is_featured: Optional[bool] = Query(None, description="Filter featured jobs"),
    status: str = Query("active", description="Filter by status"),
    limit: int = Query(12, ge=1, le=100, description="Number of jobs to return"),
    skip: int = Query(0, ge=0, description="Number of jobs to skip"),
    db = Depends(get_db_session)  # TODO: MongoDB Migration - Remove Session type
):
    """Get list of job posts with filters and pagination."""
    try:
        # Build query filters
        filters = {
            'search': search,
            'job_type': job_type,
            'location': location,
            'status': status,
            'skip': skip,
            'limit': limit
        }
        
        jobs = JobPostService.get_job_posts(db=db, **filters)
        
        # Get total count for pagination
        total_query = db.query(JobPost)
        if status:
            total_query = total_query.filter(JobPost.status == status)
        if search:
            # from sqlalchemy import or_  # TODO: MongoDB Migration - Remove SQLAlchemy dependency
            total_query = total_query.filter(
                or_(
                    JobPost.title.ilike(f'%{search}%'),
                    JobPost.description.ilike(f'%{search}%'),
                    JobPost.company_name.ilike(f'%{search}%')
                )
            )
        if job_type:
            total_query = total_query.filter(JobPost.job_type == job_type)
        if location:
            # from sqlalchemy import or_  # TODO: MongoDB Migration - Remove SQLAlchemy dependency
            total_query = total_query.filter(
                or_(
                    JobPost.location_city.ilike(f'%{location}%'),
                    JobPost.location_state.ilike(f'%{location}%'),
                    JobPost.location_country.ilike(f'%{location}%')
                )
            )
        if category:
            total_query = total_query.filter(JobPost.category == category)
        if experience_level:
            total_query = total_query.filter(JobPost.experience_level == experience_level)
        if is_featured is not None:
            total_query = total_query.filter(JobPost.is_featured == is_featured)
        
        total = total_query.count()
        
        return JobsListResponse(
            jobs=[JobPostResponse.from_orm(job) for job in jobs],
            total=total,
            page=(skip // limit) + 1,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch jobs")

@router.post("/", response_model=JobPostResponse, status_code=201)
async def create_job(
    job_data: JobPostCreate,
    db = Depends(get_db_session)  # TODO: MongoDB Migration - Remove Session type
):
    """Create a new job post."""
    try:
        # Verify employer exists
        employer = await EmployerService.get_employer_by_id(db=db, employer_id=job_data.employer_id)
        if not employer:
            raise HTTPException(status_code=404, detail="Employer not found")
        
        # Create job post
        job_post = JobPostService.create_job_post(
            db=db,
            employer_id=job_data.employer_id,
            job_data=job_data.dict(exclude={'employer_id'})
        )
        
        return JobPostResponse.from_orm(job_post)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job post: {e}")
        raise HTTPException(status_code=500, detail="Failed to create job post")

@router.get("/{job_id}", response_model=JobPostResponse)
async def get_job(
    job_id: int,
    increment_views: bool = Query(True, description="Whether to increment view count"),
    db = Depends(get_db_session)  # TODO: MongoDB Migration - Remove Session type
):
    """Get job post by ID."""
    try:
        job_post = JobPostService.get_job_post_by_id(db=db, job_id=job_id)
        
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        # Increment view count if requested
        if increment_views:
            JobPostService.increment_view_count(db=db, job_id=job_id)
            # Refresh the job post to get updated view count
            db.refresh(job_post)
        
        return JobPostResponse.from_orm(job_post)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch job post")

@router.put("/{job_id}", response_model=JobPostResponse)
async def update_job(
    job_id: int,
    job_data: JobPostUpdate,
    db = Depends(get_db_session)  # TODO: MongoDB Migration - Remove Session type
):
    """Update job post."""
    try:
        # Check if job exists
        existing_job = JobPostService.get_job_post_by_id(db=db, job_id=job_id)
        if not existing_job:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        # Update job post
        updated_job = JobPostService.update_job_post(
            db=db,
            job_id=job_id,
            **job_data.dict(exclude_unset=True)
        )
        
        return JobPostResponse.from_orm(updated_job)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update job post")

@router.delete("/{job_id}")
async def delete_job(
    job_id: int,
    db = Depends(get_db_session)  # TODO: MongoDB Migration - Remove Session type
):
    """Delete job post."""
    try:
        # Check if job exists
        job_post = JobPostService.get_job_post_by_id(db=db, job_id=job_id)
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        # Check if job has applications
        from backend.database.models import JobApplication
        applications_count = db.query(JobApplication).filter(
            JobApplication.job_post_id == job_id
        ).count()
        
        if applications_count > 0:
            # Instead of deleting, mark as inactive
            JobPostService.update_job_post(db=db, job_id=job_id, status='inactive')
            return {"message": "Job post marked as inactive due to existing applications"}
        else:
            # Safe to delete
            db.delete(job_post)
            db.commit()
            return {"message": "Job post deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete job post")

@router.get("/employer/{employer_id}", response_model=JobsListResponse)
async def get_jobs_by_employer(
    employer_id: int,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Number of jobs to return"),
    skip: int = Query(0, ge=0, description="Number of jobs to skip"),
    db = Depends(get_db_session)  # TODO: MongoDB Migration - Remove Session type
):
    """Get job posts by employer."""
    try:
        # Verify employer exists
        employer = await EmployerService.get_employer_by_id(db=db, employer_id=employer_id)
        if not employer:
            raise HTTPException(status_code=404, detail="Employer not found")
        
        jobs = JobPostService.get_job_posts_by_employer(
            db=db,
            employer_id=employer_id,
            skip=skip,
            limit=limit
        )
        
        # Apply status filter if provided
        if status:
            jobs = [job for job in jobs if job.status == status]
        
        # Get total count
        total_query = db.query(JobPost).filter(JobPost.employer_id == employer_id)
        if status:
            total_query = total_query.filter(JobPost.status == status)
        total = total_query.count()
        
        return JobsListResponse(
            jobs=[JobPostResponse.from_orm(job) for job in jobs],
            total=total,
            page=(skip // limit) + 1,
            limit=limit
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching jobs for employer {employer_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch employer jobs")