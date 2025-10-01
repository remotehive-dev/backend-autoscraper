# ============================================================================
# ADVANCED JOB WORKFLOW API - Enhanced Admin Management
# RemoteHive - RH00 Employer Integration & Workflow System
# ============================================================================

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
# from sqlalchemy.orm import Session, joinedload, noload  # Commented out - using MongoDB
# from sqlalchemy import and_, or_, func, desc, asc, text  # Commented out - using MongoDB
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

# from backend.core.database import get_db  # Commented out - using MongoDB
from backend.models.mongodb_models import Employer, User  # JobWorkflowLog commented out - doesn't exist
# Removed job_post schema imports to isolate serialization issue
from backend.schemas.employer import (
    Employer as EmployerSchema,
    EmployerWithJobStats,
    EmployerSearchParams
)
from backend.schemas.job_post import JobWorkflowAction
from backend.core.auth import get_current_user, get_admin
from backend.core.enums import JobStatus, JobAction
# Workflow logging is handled directly in the endpoint functions

router = APIRouter(tags=["Advanced Job Workflow"])

# ============================================================================
# EMPLOYER MANAGEMENT WITH RH00 SYSTEM
# ============================================================================

@router.get("/employers", response_model=Dict[str, Any])
async def get_employers_with_stats(
    search_params: EmployerSearchParams = Depends(),
    current_user: User = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - using MongoDB
):
    """
    Get all employers with job statistics and RH00 numbers.
    Enhanced search and filtering capabilities.
    """
    query = db.query(Employer)
    
    # Apply search filters
    if search_params.search:
        search_term = f"%{search_params.search}%"
        query = query.filter(
            or_(
                Employer.company_name.ilike(search_term),
                Employer.company_email.ilike(search_term)
            )
        )
    
    if search_params.industry:
        query = query.filter(Employer.industry == search_params.industry)
    
    if search_params.company_size:
        query = query.filter(Employer.company_size == search_params.company_size)
    
    if search_params.is_verified is not None:
        query = query.filter(Employer.is_verified == search_params.is_verified)
    
    if search_params.created_after:
        query = query.filter(Employer.created_at >= search_params.created_after)
    
    if search_params.created_before:
        query = query.filter(Employer.created_at <= search_params.created_before)
    
    # Filter by employers with active jobs - temporarily disabled
    # if search_params.has_active_jobs:
    #     query = query.join(JobPost).filter(JobPost.status == 'active')
    
    # Apply sorting
    if search_params.sort_by == "company_name":
        order_col = Employer.company_name
    elif search_params.sort_by == "created_at":
        order_col = Employer.created_at
    elif search_params.sort_by == "employer_number":
        order_col = Employer.employer_number
    else:
        order_col = Employer.created_at
    
    if search_params.sort_order == "asc":
        query = query.order_by(asc(order_col))
    else:
        query = query.order_by(desc(order_col))
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (search_params.page - 1) * search_params.per_page
    employers = query.offset(offset).limit(search_params.per_page).all()
    
    # Get job statistics for each employer
    employers_with_stats = []
    for employer in employers:
        # Get job stats using raw SQL for better performance
        job_stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_jobs,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_jobs,
                COUNT(CASE WHEN status = 'pending_approval' THEN 1 END) as pending_jobs,
                COUNT(CASE WHEN status = 'draft' THEN 1 END) as draft_jobs,
                COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_jobs,
                COUNT(CASE WHEN is_featured = true THEN 1 END) as featured_jobs,
                AVG(views_count) as avg_views,
                AVG(applications_count) as avg_applications,
                MAX(created_at) as last_job_created,
                MIN(created_at) as first_job_created
            FROM job_posts 
            WHERE employer_id = :employer_id
        """), {"employer_id": employer.id}).fetchone()
        
        employer_data = {
            "id": employer.id,
            "employer_number": employer.employer_number,
            "company_name": employer.company_name,
            "company_email": employer.company_email,
            "company_phone": employer.company_phone,
            "company_website": employer.company_website,
            "company_description": employer.company_description,
            "company_logo": employer.company_logo,
            "company_size": employer.company_size,
            "industry": employer.industry,
            "is_verified": employer.is_verified,
            "created_at": employer.created_at,
            "updated_at": employer.updated_at,
            "total_jobs": job_stats.total_jobs or 0,
            "active_jobs": job_stats.active_jobs or 0,
            "pending_jobs": job_stats.pending_jobs or 0,
            "draft_jobs": job_stats.draft_jobs or 0,
            "rejected_jobs": job_stats.rejected_jobs or 0,
            "featured_jobs": job_stats.featured_jobs or 0,
            "avg_views": float(job_stats.avg_views) if job_stats.avg_views else 0.0,
            "avg_applications": float(job_stats.avg_applications) if job_stats.avg_applications else 0.0,
            "last_job_created": job_stats.last_job_created,
            "first_job_created": job_stats.first_job_created
        }
        employers_with_stats.append(employer_data)
    
    return {
        "employers": employers_with_stats,
        "total": total,
        "page": search_params.page,
        "per_page": search_params.per_page,
        "pages": (total + search_params.per_page - 1) // search_params.per_page
    }

@router.get("/employers/{employer_number}", response_model=EmployerWithJobStats)
async def get_employer_by_rh_number(
    employer_number: str,
    current_user: User = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - using MongoDB
):
    """
    Get employer details by RH00 series number with comprehensive job statistics.
    """
    # Use the database function we created
    result = db.execute(
        text("SELECT * FROM get_employer_by_rh_number(:rh_number)"),
        {"rh_number": employer_number}
    ).fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Employer with RH number {employer_number} not found")
    
    return {
        "id": result.id,
        "employer_number": result.employer_number,
        "company_name": result.company_name,
        "company_email": result.company_email,
        "is_verified": result.is_verified,
        "total_jobs": result.total_jobs,
        "active_jobs": result.active_jobs
    }

# ============================================================================
# JOB POSTS BY EMPLOYER (RH00 Integration)
# ============================================================================

@router.get("/test-endpoint")
async def test_endpoint():
    """
    Test endpoint to isolate serialization issues.
    """
    return {"message": "test successful"}

@router.get("/debug-test")
def debug_test():
    """Synchronous test endpoint"""
    return {"status": "working", "message": "Debug test successful"}

@router.get("/test-serialization")
def test_serialization():
    """Test endpoint to reproduce serialization issue without any auth"""
    # Simulate the data structure that might be causing serialization issues
    test_data = {
        "jobs": [
            {
                "id": "test-job-1",
                "title": "Test Job",
                "description": "Test Description",
                "employer_number": "RH0001",
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        ],
        "employer": {
            "employer_number": "RH0001",
            "company_name": "Test Company",
            "company_email": "ranjeettiwary589@gmail.com",
            "is_verified": True
        },
        "total": 1,
        "page": 1,
        "per_page": 20,
        "pages": 1,
        "timestamp": "2024-01-01T12:00:00Z"  # Added to trigger reload
    }
    return test_data

@router.get("/simple-test")
async def simple_test():
    """Simple test endpoint without any dependencies"""
    from fastapi.responses import JSONResponse
    return JSONResponse(content={"status": "ok", "message": "Simple test working"})

@router.get("/employers/{employer_number}/jobs-no-auth")
async def get_jobs_by_employer_no_auth(
    employer_number: str
):
    """
    Get all job posts for a specific employer by RH00 number (no auth for testing).
    """
    from fastapi.responses import JSONResponse
    
    # Return minimal response to test
    response_data = {
        "jobs": [],
        "employer": {
            "employer_number": employer_number,
            "company_name": "Test Company",
            "company_email": "ranjeettiwary589@gmail.com",
            "is_verified": True
        },
        "total": 0,
        "page": 1,
        "per_page": 20,
        "pages": 0
    }
    
    return JSONResponse(content=response_data)

@router.get("/employers/{employer_number}/jobs")
async def get_jobs_by_employer(
    employer_number: str
    # Temporarily removed auth for testing: current_user: User = Depends(get_admin),
    # Temporarily removed db for testing: db: Session = Depends(get_db)
):
    """
    Get all job posts for a specific employer by RH00 number.
    """
    from fastapi.responses import JSONResponse
    
    # Return minimal response to test
    response_data = {
        "jobs": [],
        "employer": {
            "employer_number": employer_number,
            "company_name": "Test Company",
            "company_email": "ranjeettiwary589@gmail.com",
            "is_verified": True
        },
        "total": 0,
        "page": 1,
        "per_page": 20,
        "pages": 0
    }
    
    return JSONResponse(content=response_data)

# ============================================================================
# ENHANCED WORKFLOW ACTIONS
# ============================================================================

@router.post("/jobs/{job_id}/workflow-action")
async def perform_workflow_action(
    job_id: str,
    action: JobWorkflowAction,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - using MongoDB
):
    """
    Perform enhanced workflow actions on job posts.
    """
    # job = db.query(JobPost).filter(JobPost.id == job_id).first()
    # if not job:
    #     raise HTTPException(status_code=404, detail="Job post not found")
    raise HTTPException(status_code=501, detail="Temporarily disabled")
    
    old_status = job.status
    old_workflow_stage = job.workflow_stage
    
    # Perform action based on type
    if action.action == JobAction.APPROVE:
        job.status = "approved"
        job.workflow_stage = "approved"
        job.approved_at = datetime.utcnow()
        job.approved_by = current_user.id
        job.last_workflow_action = "approved"
        
        # Auto-publish if configured
        if job.auto_publish:
            job.status = "active"
            job.workflow_stage = "published"
            job.published_at = datetime.utcnow()
            job.published_by = current_user.id
            job.last_workflow_action = "auto_published"
    
    elif action.action == JobAction.REJECT:
        job.status = "rejected"
        job.workflow_stage = "rejected"
        job.rejected_at = datetime.utcnow()
        job.rejected_by = current_user.id
        job.rejection_reason = action.reason
        job.last_workflow_action = "rejected"
    
    elif action.action == JobAction.PUBLISH:
        job.status = "active"
        job.workflow_stage = "published"
        job.published_at = datetime.utcnow()
        job.published_by = current_user.id
        job.last_workflow_action = "published"
    
    elif action.action == JobAction.UNPUBLISH:
        job.status = "approved"
        job.workflow_stage = "approved"
        job.unpublished_at = datetime.utcnow()
        job.unpublished_by = current_user.id
        job.last_workflow_action = "unpublished"
    
    elif action.action == JobAction.PAUSE:
        job.status = "paused"
        job.workflow_stage = "paused"
        job.last_workflow_action = "paused"
    
    elif action.action == JobAction.RESUME:
        job.status = "active"
        job.workflow_stage = "published"
        job.last_workflow_action = "resumed"
    
    elif action.action == JobAction.CLOSE:
        job.status = "closed"
        job.workflow_stage = "closed"
        job.last_workflow_action = "closed"
    
    elif action.action == JobAction.FLAG:
        job.is_flagged = True
        job.flagged_at = datetime.utcnow()
        job.flagged_by = current_user.id
        job.flagged_reason = action.reason
        job.last_workflow_action = "flagged"
    
    elif action.action == JobAction.UNFLAG:
        job.is_flagged = False
        job.flagged_at = None
        job.flagged_by = None
        job.flagged_reason = None
        job.last_workflow_action = "unflagged"
    
    # Update workflow notes if provided
    if action.notes:
        job.workflow_notes = action.notes
    
    job.updated_at = datetime.utcnow()
    
    # Log the workflow action
    workflow_log = JobWorkflowLog(
        id=str(uuid.uuid4()),
        job_post_id=job_id,
        employer_number=job.employer_number,
        action=action.action.value,
        from_status=old_status,
        to_status=job.status,
        workflow_stage_before=old_workflow_stage,
        workflow_stage_after=job.workflow_stage,
        performed_by=current_user.id,
        reason=action.reason,
        notes=action.notes,
        automated_action=False,
        ip_address="127.0.0.1"  # You can get this from request
    )
    
    db.add(workflow_log)
    db.commit()
    db.refresh(job)
    
    # Send notifications in background
    background_tasks.add_task(
        send_workflow_notification,
        job_id=job_id,
        action=action.action.value,
        performed_by=current_user.id
    )
    
    return {
        "message": f"Job {action.action.value} successfully",
        "job_id": job_id,
        "new_status": job.status,
        "new_workflow_stage": job.workflow_stage
    }

# ============================================================================
# BULK OPERATIONS
# ============================================================================

@router.post("/jobs/bulk-action")
async def bulk_workflow_action(
    job_ids: List[str],
    action: JobWorkflowAction,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - using MongoDB
):
    """
    Perform bulk workflow actions on multiple job posts.
    """
    if len(job_ids) > 50:  # Limit bulk operations
        raise HTTPException(status_code=400, detail="Cannot perform bulk action on more than 50 jobs at once")
    
    # jobs = db.query(JobPost).filter(JobPost.id.in_(job_ids)).all()
    # if len(jobs) != len(job_ids):
    #     raise HTTPException(status_code=404, detail="Some job posts not found")
    raise HTTPException(status_code=501, detail="Bulk operations temporarily disabled")
    
    updated_jobs = []
    
    for job in jobs:
        old_status = job.status
        old_workflow_stage = job.workflow_stage
        
        # Apply the same logic as single action
        if action.action == JobAction.APPROVE:
            job.status = "approved"
            job.workflow_stage = "approved"
            job.approved_at = datetime.utcnow()
            job.approved_by = current_user.id
            job.last_workflow_action = "bulk_approved"
        
        elif action.action == JobAction.REJECT:
            job.status = "rejected"
            job.workflow_stage = "rejected"
            job.rejected_at = datetime.utcnow()
            job.rejected_by = current_user.id
            job.rejection_reason = action.reason
            job.last_workflow_action = "bulk_rejected"
        
        elif action.action == JobAction.PUBLISH:
            job.status = "active"
            job.workflow_stage = "published"
            job.published_at = datetime.utcnow()
            job.published_by = current_user.id
            job.last_workflow_action = "bulk_published"
        
        # Add other actions as needed...
        
        job.updated_at = datetime.utcnow()
        
        # Log each action
        workflow_log = JobWorkflowLog(
            id=str(uuid.uuid4()),
            job_post_id=job.id,
            employer_number=job.employer_number,
            action=f"bulk_{action.action.value}",
            from_status=old_status,
            to_status=job.status,
            workflow_stage_before=old_workflow_stage,
            workflow_stage_after=job.workflow_stage,
            performed_by=current_user.id,
            reason=action.reason,
            notes=action.notes,
            automated_action=False,
            ip_address="127.0.0.1"
        )
        
        db.add(workflow_log)
        updated_jobs.append({
            "job_id": job.id,
            "title": job.title,
            "old_status": old_status,
            "new_status": job.status
        })
    
    db.commit()
    
    return {
        "message": f"Bulk {action.action.value} completed successfully",
        "updated_jobs": updated_jobs,
        "total_updated": len(updated_jobs)
    }

# ============================================================================
# WORKFLOW STATISTICS AND ANALYTICS
# ============================================================================

@router.get("/statistics")
async def get_workflow_statistics(
    current_user: User = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - using MongoDB
):
    """
    Get comprehensive workflow statistics.
    """
    # Get workflow statistics using direct SQL queries
    stats = db.execute(text("""
        SELECT 
            COUNT(*) as total_jobs,
            COUNT(CASE WHEN status = 'pending_approval' THEN 1 END) as pending_approval,
            COUNT(CASE WHEN status = 'approved' AND DATE(updated_at) = CURRENT_DATE THEN 1 END) as approved_today,
            COUNT(CASE WHEN status = 'rejected' AND DATE(updated_at) = CURRENT_DATE THEN 1 END) as rejected_today,
            COUNT(CASE WHEN status = 'published' AND DATE(updated_at) = CURRENT_DATE THEN 1 END) as published_today,
            COUNT(DISTINCT employer_id) as active_employers,
            AVG(CASE 
                WHEN status IN ('approved', 'published') AND created_at IS NOT NULL AND updated_at IS NOT NULL 
                THEN (julianday(updated_at) - julianday(created_at)) * 24 
                ELSE NULL 
            END) as avg_approval_time_hours
        FROM job_posts
    """)).fetchone()
    
    # Get additional statistics
    employer_stats = db.execute(text("""
        SELECT 
            COUNT(*) as total_employers,
            COUNT(CASE WHEN is_verified = 1 THEN 1 END) as verified_employers,
            COUNT(CASE WHEN created_at >= date('now', '-30 days') THEN 1 END) as new_employers_this_month,
            COUNT(*) as latest_rh_number
        FROM employers
    """)).fetchone()
    
    # Get workflow stage distribution
    stage_distribution = db.execute(text("""
        SELECT 
            status,
            COUNT(*) as count
        FROM job_posts 
        GROUP BY status
        ORDER BY count DESC
    """)).fetchall()
    
    return {
        "workflow_stats": {
            "total_jobs": stats.total_jobs,
            "pending_approval": stats.pending_approval,
            "approved_today": stats.approved_today,
            "rejected_today": stats.rejected_today,
            "published_today": stats.published_today,
            "avg_approval_time_hours": float(stats.avg_approval_time_hours) if stats.avg_approval_time_hours else 0.0
        },
        "employer_stats": {
            "total_employers": employer_stats.total_employers,
            "verified_employers": employer_stats.verified_employers,
            "new_employers_this_month": employer_stats.new_employers_this_month,
            "latest_rh_number": employer_stats.latest_rh_number,
            "active_employers": stats.active_employers
        },
        "workflow_stage_distribution": [
            {"stage": stage.status, "count": stage.count}
            for stage in stage_distribution
        ]
    }

# ============================================================================
# AUTOMATED WORKFLOW FUNCTIONS
# ============================================================================

@router.post("/automation/publish-scheduled")
async def run_auto_publish(
    current_user: User = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - using MongoDB
):
    """
    Manually trigger auto-publishing of scheduled jobs.
    """
    result = db.execute(text("SELECT auto_publish_scheduled_jobs()")).fetchone()
    published_count = result[0]
    
    db.commit()
    
    return {
        "message": f"Auto-published {published_count} jobs",
        "published_count": published_count
    }

@router.post("/automation/expire-jobs")
async def run_auto_expire(
    current_user: User = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - using MongoDB
):
    """
    Manually trigger auto-expiration of jobs.
    """
    result = db.execute(text("SELECT auto_expire_jobs()")).fetchone()
    expired_count = result[0]
    
    db.commit()
    
    return {
        "message": f"Auto-expired {expired_count} jobs",
        "expired_count": expired_count
    }

# ============================================================================
# WORKFLOW HISTORY AND LOGS
# ============================================================================

@router.get("/jobs/{job_id}/workflow-history")
async def get_job_workflow_history(
    job_id: str,
    current_user: User = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - using MongoDB
):
    """
    Get complete workflow history for a specific job.
    """
    # job = db.query(JobPost).filter(JobPost.id == job_id).first()
    # if not job:
    #     raise HTTPException(status_code=404, detail="Job post not found")
    raise HTTPException(status_code=501, detail="Workflow history temporarily disabled")
    
    workflow_logs = db.query(JobWorkflowLog).filter(
        JobWorkflowLog.job_post_id == job_id
    ).order_by(desc(JobWorkflowLog.created_at)).all()
    
    return {
        "job_id": job_id,
        "job_title": job.title,
        "employer_number": job.employer_number,
        "current_status": job.status,
        "current_workflow_stage": job.workflow_stage,
        "workflow_history": workflow_logs
    }

@router.get("/employers/{employer_number}/workflow-history")
async def get_employer_workflow_history(
    employer_number: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_admin)
    # db: Session = Depends(get_db)  # Commented out - using MongoDB
):
    """
    Get workflow history for all jobs of a specific employer.
    """
    # Verify employer exists
    employer = db.query(Employer).filter(Employer.employer_number == employer_number).first()
    if not employer:
        raise HTTPException(status_code=404, detail=f"Employer with RH number {employer_number} not found")
    
    query = db.query(JobWorkflowLog).filter(
        JobWorkflowLog.employer_number == employer_number
    ).order_by(desc(JobWorkflowLog.created_at))
    
    total = query.count()
    offset = (page - 1) * per_page
    logs = query.offset(offset).limit(per_page).all()
    
    return {
        "employer_number": employer_number,
        "company_name": employer.company_name,
        "workflow_history": logs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page
    }