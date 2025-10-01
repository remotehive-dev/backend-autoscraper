from typing import Optional, Dict, Any, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
# from bson import ObjectId  # Removed to fix Pydantic schema generation

from backend.models.mongodb_models import JobPost, User
from backend.database.mongodb_models import JobWorkflowLog
from backend.core.enums import JobStatus, JobAction, JobPriority, RejectionReason
from backend.schemas.job_post import (
    JobWorkflowAction, JobApprovalAction, JobRejectionAction, 
    JobPublishAction, JobFlagAction
)
from fastapi import HTTPException, status

class JobWorkflowService:
    """
    Service class to handle job post workflow operations including:
    - State transitions
    - Approval/Rejection workflow
    - Publishing/Unpublishing
    - Flagging and review processes
    - Audit logging
    """
    
    # Define valid state transitions
    VALID_TRANSITIONS = {
        JobStatus.DRAFT: [JobStatus.PENDING_APPROVAL, JobStatus.CANCELLED],
        JobStatus.PENDING_APPROVAL: [JobStatus.APPROVED, JobStatus.REJECTED, JobStatus.UNDER_REVIEW],
        JobStatus.UNDER_REVIEW: [JobStatus.APPROVED, JobStatus.REJECTED, JobStatus.PENDING_APPROVAL],
        JobStatus.APPROVED: [JobStatus.ACTIVE, JobStatus.REJECTED, JobStatus.CANCELLED],
        JobStatus.REJECTED: [JobStatus.PENDING_APPROVAL, JobStatus.CANCELLED],
        JobStatus.ACTIVE: [JobStatus.PAUSED, JobStatus.CLOSED, JobStatus.EXPIRED, JobStatus.FLAGGED],
        JobStatus.PAUSED: [JobStatus.ACTIVE, JobStatus.CLOSED, JobStatus.CANCELLED],
        JobStatus.FLAGGED: [JobStatus.UNDER_REVIEW, JobStatus.ACTIVE, JobStatus.CANCELLED],
        JobStatus.CLOSED: [JobStatus.ACTIVE],  # Can reopen
        JobStatus.EXPIRED: [JobStatus.ACTIVE],  # Can reactivate
        JobStatus.CANCELLED: []  # Terminal state
    }
    
    @staticmethod
    def can_transition(from_status: JobStatus, to_status: JobStatus) -> bool:
        """Check if a status transition is valid"""
        return to_status in JobWorkflowService.VALID_TRANSITIONS.get(from_status, [])
    
    @staticmethod
    async def submit_for_approval(
        db: AsyncIOMotorDatabase, 
        job_post_id: str, 
        user_id: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a job post for admin approval"""
        job_post = await db.job_posts.find_one({"_id": job_post_id})
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        if job_post.get("status") != JobStatus.DRAFT:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot submit job with status {job_post.get('status')} for approval"
            )
        
        # Update job post
        update_data = {
            "status": JobStatus.PENDING_APPROVAL,
            "submitted_for_approval_at": datetime.utcnow(),
            "submitted_by": user_id,
            "updated_at": datetime.utcnow()
        }
        
        await db.job_posts.update_one(
            {"_id": job_post_id},
            {"$set": update_data}
        )
        
        # Log the action
        await JobWorkflowService._log_workflow_action(
            db, job_post_id, JobAction.SUBMIT_FOR_APPROVAL,
            JobStatus.DRAFT, JobStatus.PENDING_APPROVAL,
            user_id, notes=notes
        )
        
        # Return updated job post
        updated_job_post = await db.job_posts.find_one({"_id": job_post_id})
        return updated_job_post
    
    @staticmethod
    async def approve_job(
        db: AsyncIOMotorDatabase,
        job_post_id: str,
        admin_user_id: str,
        approval_data: JobApprovalAction
    ) -> Dict[str, Any]:
        """Approve a job post"""
        job_post = await db.job_posts.find_one({"_id": job_post_id})
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        current_status = job_post.get("status")
        if current_status not in [JobStatus.PENDING_APPROVAL, JobStatus.UNDER_REVIEW]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve job with status {current_status}"
            )
        
        old_status = current_status
        
        # Update job post
        update_data = {
            "status": JobStatus.APPROVED,
            "approved_at": datetime.utcnow(),
            "approved_by": admin_user_id,
            "rejected_at": None,
            "rejected_by": None,
            "rejection_reason": None,
            "rejection_notes": None,
            "updated_at": datetime.utcnow()
        }
        
        # If publish immediately is requested
        if approval_data.publish_immediately:
            update_data["status"] = JobStatus.ACTIVE
            update_data["published_at"] = datetime.utcnow()
            update_data["published_by"] = admin_user_id
        
        await db.job_posts.update_one(
            {"_id": job_post_id},
            {"$set": update_data}
        )
        
        # Log the action
        await JobWorkflowService._log_workflow_action(
            db, job_post_id, JobAction.APPROVE,
            old_status, update_data["status"],
            admin_user_id, notes=approval_data.notes,
            additional_data={"publish_immediately": approval_data.publish_immediately}
        )
        
        # Return updated job post
        updated_job_post = await db.job_posts.find_one({"_id": job_post_id})
        return updated_job_post
    
    @staticmethod
    async def reject_job(
        db: AsyncIOMotorDatabase,
        job_post_id: str,
        admin_user_id: str,
        rejection_data: JobRejectionAction
    ) -> Dict[str, Any]:
        """Reject a job post"""
        job_post = await db.job_posts.find_one({"_id": job_post_id})
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        current_status = job_post.get("status")
        if current_status not in [JobStatus.PENDING_APPROVAL, JobStatus.UNDER_REVIEW, JobStatus.APPROVED]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reject job with status {current_status}"
            )
        
        old_status = current_status
        
        # Update job post
        update_data = {
            "status": JobStatus.REJECTED,
            "rejected_at": datetime.utcnow(),
            "rejected_by": admin_user_id,
            "rejection_reason": rejection_data.rejection_reason.value,
            "rejection_notes": rejection_data.notes,
            "approved_at": None,
            "approved_by": None,
            "updated_at": datetime.utcnow()
        }
        
        await db.job_posts.update_one(
            {"_id": job_post_id},
            {"$set": update_data}
        )
        
        # Log the action
        await JobWorkflowService._log_workflow_action(
            db, job_post_id, JobAction.REJECT,
            old_status, JobStatus.REJECTED,
            admin_user_id, reason=rejection_data.rejection_reason.value,
            notes=rejection_data.notes
        )
        
        # Return updated job post
        updated_job_post = await db.job_posts.find_one({"_id": job_post_id})
        return updated_job_post
    
    @staticmethod
    async def publish_job(
        db: AsyncIOMotorDatabase,
        job_post_id: str,
        user_id: str,
        publish_data: JobPublishAction
    ) -> Dict[str, Any]:
        """Publish an approved job post"""
        job_post = await db.job_posts.find_one({"_id": job_post_id})
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        if job_post["status"] != JobStatus.APPROVED.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot publish job with status {job_post['status']}. Job must be approved first."
            )
        
        # Update job post
        update_data = {
            "status": JobStatus.ACTIVE.value,
            "published_at": datetime.utcnow(),
            "published_by": user_id,
            "priority": publish_data.priority.value,
            "is_featured": publish_data.is_featured,
            "is_urgent": publish_data.is_urgent,
            "updated_at": datetime.utcnow()
        }
        
        await db.job_posts.update_one(
            {"_id": job_post_id},
            {"$set": update_data}
        )
        
        # Log the action
        await JobWorkflowService._log_workflow_action(
            db, job_post_id, JobAction.PUBLISH,
            JobStatus.APPROVED, JobStatus.ACTIVE,
            user_id, additional_data={
                "priority": publish_data.priority.value,
                "is_featured": publish_data.is_featured,
                "is_urgent": publish_data.is_urgent
            }
        )
        
        # Return updated job post
        updated_job_post = await db.job_posts.find_one({"_id": job_post_id})
        return updated_job_post
    
    @staticmethod
    async def unpublish_job(
        db: AsyncIOMotorDatabase,
        job_post_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Unpublish an active job post"""
        job_post = await db.job_posts.find_one({"_id": job_post_id})
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        if job_post["status"] != JobStatus.ACTIVE.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot unpublish job with status {job_post['status']}"
            )
        
        # Update job post
        update_data = {
            "status": JobStatus.APPROVED.value,  # Back to approved state
            "unpublished_at": datetime.utcnow(),
            "unpublished_by": user_id,
            "updated_at": datetime.utcnow()
        }
        
        await db.job_posts.update_one(
            {"_id": job_post_id},
            {"$set": update_data}
        )
        
        # Log the action
        await JobWorkflowService._log_workflow_action(
            db, job_post_id, JobAction.UNPUBLISH,
            JobStatus.ACTIVE, JobStatus.APPROVED,
            user_id, reason=reason
        )
        
        # Return updated job post
        updated_job_post = await db.job_posts.find_one({"_id": job_post_id})
        return updated_job_post
    
    @staticmethod
    async def pause_job(
        db: AsyncIOMotorDatabase,
        job_post_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Pause an active job post"""
        job_post = await db.job_posts.find_one({"_id": job_post_id})
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        if job_post["status"] != JobStatus.ACTIVE.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot pause job with status {job_post['status']}"
            )
        
        # Update job post
        update_data = {
            "status": JobStatus.PAUSED.value,
            "updated_at": datetime.utcnow()
        }
        
        await db.job_posts.update_one(
            {"_id": job_post_id},
            {"$set": update_data}
        )
        
        # Log the action
        await JobWorkflowService._log_workflow_action(
            db, job_post_id, JobAction.PAUSE,
            JobStatus.ACTIVE, JobStatus.PAUSED,
            user_id, reason=reason
        )
        
        # Return updated job post
        updated_job_post = await db.job_posts.find_one({"_id": job_post_id})
        return updated_job_post
    
    @staticmethod
    async def resume_job(
        db: AsyncIOMotorDatabase,
        job_post_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Resume a paused job post"""
        job_post = await db.job_posts.find_one({"_id": job_post_id})
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        if job_post["status"] != JobStatus.PAUSED.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot resume job with status {job_post['status']}"
            )
        
        # Update job post
        update_data = {
            "status": JobStatus.ACTIVE.value,
            "updated_at": datetime.utcnow()
        }
        
        await db.job_posts.update_one(
            {"_id": job_post_id},
            {"$set": update_data}
        )
        
        # Log the action
        await JobWorkflowService._log_workflow_action(
            db, job_post_id, JobAction.RESUME,
            JobStatus.PAUSED, JobStatus.ACTIVE,
            user_id, reason=reason
        )
        
        # Return updated job post
        updated_job_post = await db.job_posts.find_one({"_id": job_post_id})
        return updated_job_post
    
    @staticmethod
    async def close_job(
        db: AsyncIOMotorDatabase,
        job_post_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Close an active or paused job post"""
        job_post = await db.job_posts.find_one({"_id": job_post_id})
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        if job_post["status"] not in [JobStatus.ACTIVE.value, JobStatus.PAUSED.value]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot close job with status {job_post['status']}"
            )
        
        old_status = JobStatus(job_post["status"])
        
        # Update job post
        update_data = {
            "status": JobStatus.CLOSED.value,
            "updated_at": datetime.utcnow()
        }
        
        await db.job_posts.update_one(
            {"_id": job_post_id},
            {"$set": update_data}
        )
        
        # Log the action
        await JobWorkflowService._log_workflow_action(
            db, job_post_id, JobAction.CLOSE,
            old_status, JobStatus.CLOSED,
            user_id, reason=reason
        )
        
        # Return updated job post
        updated_job_post = await db.job_posts.find_one({"_id": job_post_id})
        return updated_job_post
    
    @staticmethod
    async def flag_job(
        db: AsyncIOMotorDatabase,
        job_post_id: str,
        user_id: str,
        flag_data: JobFlagAction
    ) -> Dict[str, Any]:
        """Flag a job post for review"""
        job_post = await db.job_posts.find_one({"_id": job_post_id})
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        old_status = JobStatus(job_post["status"])
        
        # Prepare update data
        update_data = {
            "is_flagged": True,
            "flagged_at": datetime.utcnow(),
            "flagged_by": user_id,
            "flagged_reason": flag_data.reason,
            "updated_at": datetime.utcnow()
        }
        
        # If job is active, move to flagged status
        new_status = old_status
        if job_post["status"] == JobStatus.ACTIVE.value:
            update_data["status"] = JobStatus.FLAGGED.value
            new_status = JobStatus.FLAGGED
        
        await db.job_posts.update_one(
            {"_id": job_post_id},
            {"$set": update_data}
        )
        
        # Log the action
        await JobWorkflowService._log_workflow_action(
            db, job_post_id, JobAction.FLAG,
            old_status, new_status,
            user_id, reason=flag_data.reason, notes=flag_data.notes
        )
        
        # Return updated job post
        updated_job_post = await db.job_posts.find_one({"_id": job_post_id})
        return updated_job_post
    
    @staticmethod
    async def unflag_job(
        db: AsyncIOMotorDatabase,
        job_post_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Remove flag from a job post"""
        job_post = await db.job_posts.find_one({"_id": job_post_id})
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        if not job_post.get("is_flagged", False):
            raise HTTPException(status_code=400, detail="Job post is not flagged")
        
        old_status = JobStatus(job_post["status"])
        
        # Prepare update data
        update_data = {
            "is_flagged": False,
            "flagged_at": None,
            "flagged_by": None,
            "flagged_reason": None,
            "updated_at": datetime.utcnow()
        }
        
        # If job was in flagged status, restore to active
        new_status = old_status
        if job_post["status"] == JobStatus.FLAGGED.value:
            update_data["status"] = JobStatus.ACTIVE.value
            new_status = JobStatus.ACTIVE
        
        await db.job_posts.update_one(
            {"_id": job_post_id},
            {"$set": update_data}
        )
        
        # Log the action
        await JobWorkflowService._log_workflow_action(
            db, job_post_id, JobAction.UNFLAG,
            old_status, new_status,
            user_id, notes=notes
        )
        
        # Return updated job post
        updated_job_post = await db.job_posts.find_one({"_id": job_post_id})
        return updated_job_post
    
    @staticmethod
    async def cancel_job(
        db: AsyncIOMotorDatabase,
        job_post_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cancel a job post (terminal action)"""
        job_post = await db.job_posts.find_one({"_id": job_post_id})
        if not job_post:
            raise HTTPException(status_code=404, detail="Job post not found")
        
        if job_post["status"] == JobStatus.CANCELLED.value:
            raise HTTPException(status_code=400, detail="Job post is already cancelled")
        
        old_status = JobStatus(job_post["status"])
        
        # Update job post
        await db.job_posts.update_one(
            {"_id": job_post_id},
            {"$set": {
                "status": JobStatus.CANCELLED.value,
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Log the action
        await JobWorkflowService._log_workflow_action(
            db, job_post_id, JobAction.CANCEL,
            old_status, JobStatus.CANCELLED,
            user_id, reason=reason
        )
        
        # Return updated job post
        updated_job_post = await db.job_posts.find_one({"_id": job_post_id})
        return updated_job_post
    
    @staticmethod
    async def get_workflow_history(
        db: AsyncIOMotorDatabase,
        job_post_id: str
    ) -> List[Dict[str, Any]]:
        """Get workflow history for a job post"""
        cursor = db.job_workflow_logs.find(
            {"job_post_id": job_post_id}
        ).sort("created_at", -1)
        
        return await cursor.to_list(length=None)
    
    @staticmethod
    async def get_pending_approvals(
        db: AsyncIOMotorDatabase,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get jobs pending approval"""
        cursor = db.job_posts.find(
            {"status": JobStatus.PENDING_APPROVAL.value}
        ).sort("submitted_for_approval_at", 1).skip(offset).limit(limit)
        
        return await cursor.to_list(length=None)
    
    @staticmethod
    async def get_flagged_jobs(
        db: AsyncIOMotorDatabase,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get flagged jobs"""
        cursor = db.job_posts.find(
            {"is_flagged": True}
        ).sort("flagged_at", -1).skip(offset).limit(limit)
        
        return await cursor.to_list(length=None)
    
    @staticmethod
    async def _log_workflow_action(
        db: AsyncIOMotorDatabase,
        job_post_id: str,
        action: JobAction,
        from_status: Optional[JobStatus],
        to_status: Optional[JobStatus],
        performed_by: str,
        reason: Optional[str] = None,
        notes: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log a workflow action"""
        log_entry = {
            "job_post_id": job_post_id,
            "action": action.value,
            "from_status": from_status.value if from_status else None,
            "to_status": to_status.value if to_status else None,
            "performed_by": performed_by,
            "reason": reason,
            "notes": notes,
            "additional_data": additional_data,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.utcnow()
        }
        
        result = await db.job_workflow_logs.insert_one(log_entry)
        log_entry["_id"] = result.inserted_id
        return log_entry