from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
# from sqlalchemy.orm import Session  # Commented out - using MongoDB

# from backend.core.database import get_db  # Commented out - using MongoDB
from backend.core.auth import get_current_user, get_admin, get_employer
from backend.models.mongodb_models import User, JobPost  # JobWorkflowLog commented out - doesn't exist
from backend.schemas.job_post import (
    JobPost as JobPostSchema,
    JobWorkflowAction,
    JobApprovalAction,
    JobRejectionAction,
    JobPublishAction,
    JobFlagAction,
    JobWorkflowLogSchema
)
from backend.services.job_workflow_service import JobWorkflowService
from backend.core.enums import JobStatus, JobAction

router = APIRouter(prefix="/job-workflow", tags=["Job Workflow"])

# Employer endpoints
@router.post("/submit-for-approval/{job_post_id}", response_model=JobPostSchema)
async def submit_job_for_approval(
    job_post_id: str,
    notes: Optional[str] = None,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_current_user)
):
    """
    Submit a job post for admin approval.
    Only the job owner (employer) can submit their job for approval.
    """
    # Check if user owns this job post
    job_post = db.query(JobPost).filter(JobPost.id == job_post_id).first()
    if not job_post:
        raise HTTPException(status_code=404, detail="Job post not found")
    
    if job_post.employer_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=403, 
            detail="You can only submit your own job posts for approval"
        )
    
    return JobWorkflowService.submit_for_approval(
        db=db,
        job_post_id=job_post_id,
        user_id=current_user.id,
        notes=notes
    )

@router.post("/pause/{job_post_id}", response_model=JobPostSchema)
async def pause_job(
    job_post_id: str,
    reason: Optional[str] = None,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_employer)
):
    """
    Pause an active job post.
    Only the job owner or admin can pause a job.
    """
    # Check ownership for non-admin users
    if current_user.role != "admin":
        job_post = db.query(JobPost).filter(JobPost.id == job_post_id).first()
        if not job_post or job_post.employer_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only pause your own job posts"
            )
    
    return JobWorkflowService.pause_job(
        db=db,
        job_post_id=job_post_id,
        user_id=current_user.id,
        reason=reason
    )

@router.post("/resume/{job_post_id}", response_model=JobPostSchema)
async def resume_job(
    job_post_id: str,
    reason: Optional[str] = None,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_employer)
):
    """
    Resume a paused job post.
    Only the job owner or admin can resume a job.
    """
    # Check ownership for non-admin users
    if current_user.role != "admin":
        job_post = db.query(JobPost).filter(JobPost.id == job_post_id).first()
        if not job_post or job_post.employer_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only resume your own job posts"
            )
    
    return JobWorkflowService.resume_job(
        db=db,
        job_post_id=job_post_id,
        user_id=current_user.id,
        reason=reason
    )

@router.post("/close/{job_post_id}", response_model=JobPostSchema)
async def close_job(
    job_post_id: str,
    reason: Optional[str] = None,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: Dict[str, Any] = Depends(get_employer)
):
    """
    Close an active or paused job post.
    Only the job owner or admin can close a job.
    """
    # Check ownership for non-admin users
    if current_user.get("role") != "admin":
        job_post = db.query(JobPost).filter(JobPost.id == job_post_id).first()
        if not job_post or job_post.employer_id != current_user.get("id"):
            raise HTTPException(
                status_code=403,
                detail="You can only close your own job posts"
            )
    
    return JobWorkflowService.close_job(
        db=db,
        job_post_id=job_post_id,
        user_id=current_user.get("id"),
        reason=reason
    )

@router.post("/cancel/{job_post_id}", response_model=JobPostSchema)
async def cancel_job(
    job_post_id: str,
    reason: Optional[str] = None,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_employer)
):
    """
    Cancel a job post (terminal action).
    Only the job owner or admin can cancel a job.
    """
    # Check ownership for non-admin users
    if current_user.role != "admin":
        job_post = db.query(JobPost).filter(JobPost.id == job_post_id).first()
        if not job_post or job_post.employer_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only cancel your own job posts"
            )
    
    return JobWorkflowService.cancel_job(
        db=db,
        job_post_id=job_post_id,
        user_id=current_user.id,
        reason=reason
    )

# Admin-only endpoints
@router.post("/admin/approve/{job_post_id}", response_model=JobPostSchema)
async def approve_job(
    job_post_id: str,
    approval_data: JobApprovalAction,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Approve a job post.
    Only admins can approve jobs.
    """
    return JobWorkflowService.approve_job(
        db=db,
        job_post_id=job_post_id,
        admin_user_id=current_user.id,
        approval_data=approval_data
    )

@router.post("/admin/reject/{job_post_id}", response_model=JobPostSchema)
async def reject_job(
    job_post_id: str,
    rejection_data: JobRejectionAction,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Reject a job post.
    Only admins can reject jobs.
    """
    return JobWorkflowService.reject_job(
        db=db,
        job_post_id=job_post_id,
        admin_user_id=current_user.id,
        rejection_data=rejection_data
    )

@router.post("/admin/publish/{job_post_id}", response_model=JobPostSchema)
async def publish_job(
    job_post_id: str,
    publish_data: JobPublishAction,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Publish an approved job post.
    Only admins can publish jobs.
    """
    return JobWorkflowService.publish_job(
        db=db,
        job_post_id=job_post_id,
        user_id=current_user.id,
        publish_data=publish_data
    )

@router.post("/admin/unpublish/{job_post_id}", response_model=JobPostSchema)
async def unpublish_job(
    job_post_id: str,
    reason: Optional[str] = None,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Unpublish an active job post.
    Only admins can unpublish jobs.
    """
    return JobWorkflowService.unpublish_job(
        db=db,
        job_post_id=job_post_id,
        user_id=current_user.id,
        reason=reason
    )

@router.post("/admin/flag/{job_post_id}", response_model=JobPostSchema)
async def flag_job(
    job_post_id: str,
    flag_data: JobFlagAction,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Flag a job post for review.
    Only admins can flag jobs.
    """
    return JobWorkflowService.flag_job(
        db=db,
        job_post_id=job_post_id,
        user_id=current_user.id,
        flag_data=flag_data
    )

@router.post("/admin/unflag/{job_post_id}", response_model=JobPostSchema)
async def unflag_job(
    job_post_id: str,
    notes: Optional[str] = None,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Remove flag from a job post.
    Only admins can unflag jobs.
    """
    return JobWorkflowService.unflag_job(
        db=db,
        job_post_id=job_post_id,
        user_id=current_user.id,
        notes=notes
    )

@router.get("/admin/pending-approvals", response_model=List[JobPostSchema])
async def get_pending_approvals(
    limit: int = 50,
    offset: int = 0,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Get jobs pending approval.
    Only admins can view pending approvals.
    """
    return JobWorkflowService.get_pending_approvals(
        db=db,
        limit=limit,
        offset=offset
    )

@router.get("/admin/flagged-jobs", response_model=List[JobPostSchema])
async def get_flagged_jobs(
    limit: int = 50,
    offset: int = 0,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Get flagged jobs.
    Only admins can view flagged jobs.
    """
    return JobWorkflowService.get_flagged_jobs(
        db=db,
        limit=limit,
        offset=offset
    )

# Workflow history endpoints
@router.get("/history/{job_post_id}", response_model=List[JobWorkflowLogSchema])
async def get_workflow_history(
    job_post_id: str,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get workflow history for a job post.
    Job owners and admins can view workflow history.
    """
    # Check if user can view this job's history
    job_post = db.query(JobPost).filter(JobPost.id == job_post_id).first()
    if not job_post:
        raise HTTPException(status_code=404, detail="Job post not found")
    
    if job_post.employer_id != current_user.get("id") and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="You can only view workflow history for your own job posts"
        )
    
    return JobWorkflowService.get_workflow_history(
        db=db,
        job_post_id=job_post_id
    )

# Bulk operations for admins
@router.post("/admin/bulk-approve", response_model=List[JobPostSchema])
async def bulk_approve_jobs(
    job_post_ids: List[str],
    approval_data: JobApprovalAction,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Bulk approve multiple job posts.
    Only admins can perform bulk operations.
    """
    results = []
    for job_post_id in job_post_ids:
        try:
            result = JobWorkflowService.approve_job(
                db=db,
                job_post_id=job_post_id,
                admin_user_id=current_user.id,
                approval_data=approval_data
            )
            results.append(result)
        except HTTPException:
            # Skip jobs that can't be approved
            continue
    
    return results

@router.post("/admin/bulk-reject", response_model=List[JobPostSchema])
async def bulk_reject_jobs(
    job_post_ids: List[str],
    rejection_data: JobRejectionAction,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Bulk reject multiple job posts.
    Only admins can perform bulk operations.
    """
    results = []
    for job_post_id in job_post_ids:
        try:
            result = JobWorkflowService.reject_job(
                db=db,
                job_post_id=job_post_id,
                admin_user_id=current_user.id,
                rejection_data=rejection_data
            )
            results.append(result)
        except HTTPException:
            # Skip jobs that can't be rejected
            continue
    
    return results

@router.post("/admin/bulk-publish", response_model=List[JobPostSchema])
async def bulk_publish_jobs(
    job_post_ids: List[str],
    publish_data: JobPublishAction,
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Bulk publish multiple approved job posts.
    Only admins can perform bulk operations.
    """
    results = []
    for job_post_id in job_post_ids:
        try:
            result = JobWorkflowService.publish_job(
                db=db,
                job_post_id=job_post_id,
                user_id=current_user.id,
                publish_data=publish_data
            )
            results.append(result)
        except HTTPException:
            # Skip jobs that can't be published
            continue
    
    return results

# Statistics endpoints
@router.get("/admin/workflow-stats")
async def get_workflow_stats(
    # db: Session = Depends(get_db),  # Commented out - using MongoDB
    current_user: User = Depends(get_admin)
):
    """
    Get workflow statistics.
    Only admins can view workflow statistics.
    """
    stats = {
        "pending_approval": db.query(JobPost).filter(JobPost.status == JobStatus.PENDING_APPROVAL).count(),
        "under_review": db.query(JobPost).filter(JobPost.status == JobStatus.UNDER_REVIEW).count(),
        "approved": db.query(JobPost).filter(JobPost.status == JobStatus.APPROVED).count(),
        "rejected": db.query(JobPost).filter(JobPost.status == JobStatus.REJECTED).count(),
        "active": db.query(JobPost).filter(JobPost.status == JobStatus.ACTIVE).count(),
        "paused": db.query(JobPost).filter(JobPost.status == JobStatus.PAUSED).count(),
        "closed": db.query(JobPost).filter(JobPost.status == JobStatus.CLOSED).count(),
        "flagged": db.query(JobPost).filter(JobPost.is_flagged == True).count(),
        "cancelled": db.query(JobPost).filter(JobPost.status == JobStatus.CANCELLED).count(),
        "expired": db.query(JobPost).filter(JobPost.status == JobStatus.EXPIRED).count(),
        "draft": db.query(JobPost).filter(JobPost.status == JobStatus.DRAFT).count()
    }
    
    return stats