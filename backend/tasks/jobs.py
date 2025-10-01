from celery import current_app as celery_app
from backend.core.database import get_db
from backend.database.services import JobPostService, JobApplicationService, UserService
from backend.database.database import get_database_manager
# from backend.database.models import ScraperConfig, ScraperLog, ScraperMemory, JobPost, JobApplication
from backend.models.mongodb_models import JobPost, JobApplication
from backend.database.mongodb_models import ScraperConfig, ScraperLog
# Note: ScraperMemory needs to be implemented in MongoDB models if needed
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any
# from sqlalchemy import and_, or_  # Using MongoDB instead

logger = logging.getLogger(__name__)

@celery_app.task
def cleanup_expired_jobs():
    """Clean up expired job posts and update their status."""
    try:
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as db:
            # Find jobs that have expired (application_deadline passed)
            current_time = datetime.utcnow()
            expired_jobs = db.query(JobPost).filter(
                and_(
                    JobPost.application_deadline < current_time,
                    JobPost.status == "active"
                )
            ).all()
            
            updated_count = 0
            for job in expired_jobs:
                # Update job status to closed
                JobPostService.update_job_post(db, job.id, status="closed", updated_at=current_time)
                updated_count += 1
            
            logger.info(f"Updated {updated_count} expired jobs to CLOSED status")
            return {"updated_jobs": updated_count}
    
    except Exception as e:
        logger.error(f"Error cleaning up expired jobs: {str(e)}")
        raise

@celery_app.task
def cleanup_old_job_posts():
    """Clean up old job posts (older than 6 months and closed)."""
    try:
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as db:
            # Delete job posts older than 6 months and closed
            cutoff_date = datetime.utcnow() - timedelta(days=180)
            old_jobs = db.query(JobPost).filter(
                and_(
                    JobPost.updated_at < cutoff_date,
                    JobPost.status == "closed"
                )
            ).all()
            
            deleted_count = 0
            for job in old_jobs:
                db.delete(job)
                deleted_count += 1
            
            db.commit()
            logger.info(f"Deleted {deleted_count} old job posts")
            return {"deleted_jobs": deleted_count}
    
    except Exception as e:
        logger.error(f"Error cleaning up old job posts: {str(e)}")
        raise

@celery_app.task
def update_job_view_counts():
    """Update job view counts and calculate trending jobs."""
    try:
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as db:
            # This is a placeholder for view count analytics
            # In a real implementation, you might:
            # 1. Aggregate view data from Redis or analytics service
            # 2. Update job popularity scores
            # 3. Calculate trending jobs
            
            active_jobs = db.query(JobPost).filter(JobPost.status == "active").all()
            
            updated_count = 0
            for job in active_jobs:
                # Simulate view count updates (replace with actual analytics)
                # JobPostService.update_job_post(db, job.id, view_count=get_actual_view_count(job.id))
                updated_count += 1
            
            logger.info(f"Updated view counts for {updated_count} jobs")
            return {"updated_jobs": updated_count}
    
    except Exception as e:
        logger.error(f"Error updating job view counts: {str(e)}")
        raise

@celery_app.task
def send_job_alerts():
    """Send job alerts to users based on their preferences."""
    try:
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as db:
            # This is a placeholder for job alert functionality
            # In a real implementation, you would:
            # 1. Get users with job alert preferences
            # 2. Find matching new jobs
            # 3. Send email notifications
            
            # Get new jobs from the last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)
            new_jobs = db.query(JobPost).filter(
                and_(
                    JobPost.created_at >= yesterday,
                    JobPost.status == "active"
                )
            ).all()
            
            alerts_sent = 0
            # Placeholder for actual alert logic
            for job in new_jobs:
                # Find matching users and send alerts
                # alerts_sent += send_alert_to_matching_users(job)
                pass
        
        logger.info(f"Sent {alerts_sent} job alerts")
        return {"alerts_sent": alerts_sent, "new_jobs": len(new_jobs.data)}
    
    except Exception as e:
        logger.error(f"Error sending job alerts: {str(e)}")
        raise

@celery_app.task
def cleanup_old_applications():
    """Clean up old job applications (older than 1 year and rejected)."""
    try:
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as db:
            # Delete applications older than 1 year and rejected
            cutoff_date = datetime.utcnow() - timedelta(days=365)
            old_applications = db.query(JobApplication).filter(
                and_(
                    JobApplication.updated_at < cutoff_date,
                    JobApplication.status == "rejected"
                )
            ).all()
            
            deleted_count = 0
            for application in old_applications:
                db.delete(application)
                deleted_count += 1
            
            db.commit()
            logger.info(f"Deleted {deleted_count} old job applications")
            return {"deleted_applications": deleted_count}
    
    except Exception as e:
        logger.error(f"Error cleaning up old applications: {str(e)}")
        raise

@celery_app.task
def generate_job_recommendations(user_id: int):
    """Generate job recommendations for a specific user."""
    try:
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as db:
            # This is a placeholder for recommendation engine
            # In a real implementation, you would:
            # 1. Get user's profile and preferences
            # 2. Analyze their application history
            # 3. Use ML algorithms to find matching jobs
            # 4. Store recommendations in cache or database
            
            # Get active jobs (simplified recommendation)
            recommended_jobs = db.query(JobPost).filter(JobPost.status == "active").limit(10).all()
            
            recommendations = [{
                "job_id": job.id,
                "title": job.title,
                "company_name": job.company_name,
                "score": 0.8  # Placeholder score
            } for job in recommended_jobs]
        
        logger.info(f"Generated {len(recommendations)} recommendations for user {user_id}")
        return {
            "user_id": user_id,
            "recommendations": recommendations,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error generating recommendations for user {user_id}: {str(e)}")
        raise