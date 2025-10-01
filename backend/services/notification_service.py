import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
# from sqlalchemy.orm import Session  # Using MongoDB instead
from backend.core.database import get_db
from backend.services.email_service import EmailService

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for handling various notification types in RemoteHive"""
    
    @staticmethod
    async def notify_admin_new_application(job_id: int, applicant_email: str):
        """Notify admin about new job application"""
        try:
            subject = f"New Job Application - Job ID: {job_id}"
            message = f"""
            A new job application has been received.
            
            Job ID: {job_id}
            Applicant Email: {applicant_email}
            Timestamp: {datetime.utcnow().isoformat()}
            
            Please review the application in the admin panel.
            """
            
            # Send to admin email (you should configure this in settings)
            admin_email = "admin@remotehive.in"  # Configure this
            await EmailService.send_plain_email(admin_email, subject, message)
            
            logger.info(f"Admin notification sent for new application: Job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to send admin notification for new application: {str(e)}")
    
    @staticmethod
    async def notify_admin_job_flagged(job_id: int, reason: str):
        """Notify admin about flagged job"""
        try:
            subject = f"Job Flagged for Review - Job ID: {job_id}"
            message = f"""
            A job has been flagged for manual review.
            
            Job ID: {job_id}
            Reason: {reason}
            Timestamp: {datetime.utcnow().isoformat()}
            
            Please review the job in the admin panel.
            """
            
            admin_email = "admin@remotehive.in"  # Configure this
            await EmailService.send_plain_email(admin_email, subject, message)
            
            logger.info(f"Admin notification sent for flagged job: {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to send admin notification for flagged job: {str(e)}")
    
    @staticmethod
    async def send_admin_alert(alert_type: str, message: str, priority: str = "medium"):
        """Send general admin alert"""
        try:
            subject = f"[{priority.upper()}] RemoteHive Alert: {alert_type}"
            email_message = f"""
            RemoteHive System Alert
            
            Type: {alert_type}
            Priority: {priority}
            Message: {message}
            Timestamp: {datetime.utcnow().isoformat()}
            
            Please check the admin panel for more details.
            """
            
            admin_email = "admin@remotehive.in"  # Configure this
            await EmailService.send_plain_email(admin_email, subject, email_message)
            
            logger.info(f"Admin alert sent: {alert_type} - {priority}")
            
        except Exception as e:
            logger.error(f"Failed to send admin alert: {str(e)}")
    
    @staticmethod
    async def schedule_reminder(user_id: int, reminder_type: str, scheduled_time: str):
        """Schedule a reminder for a user"""
        try:
            # This is a placeholder for reminder scheduling
            # In a real implementation, you might use Celery or another task queue
            logger.info(f"Reminder scheduled for user {user_id}: {reminder_type} at {scheduled_time}")
            
            # For now, just log the reminder
            # You could implement actual scheduling logic here
            
        except Exception as e:
            logger.error(f"Failed to schedule reminder: {str(e)}")
    
    @staticmethod
    async def send_bulk_notification(
        recipients: List[str], 
        subject: str, 
        message: str, 
        notification_type: str = "email"
    ):
        """Send bulk notifications to multiple recipients"""
        try:
            success_count = 0
            failed_count = 0
            
            for recipient in recipients:
                try:
                    if notification_type == "email":
                        await EmailService.send_plain_email(recipient, subject, message)
                        success_count += 1
                    else:
                        logger.warning(f"Unsupported notification type: {notification_type}")
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to send notification to {recipient}: {str(e)}")
                    failed_count += 1
            
            logger.info(f"Bulk notification completed: {success_count} sent, {failed_count} failed")
            return {"sent": success_count, "failed": failed_count}
            
        except Exception as e:
            logger.error(f"Failed to send bulk notifications: {str(e)}")
            return {"sent": 0, "failed": len(recipients)}
    
    @staticmethod
    async def notify_user_status_change(user_id: int, old_status: str, new_status: str):
        """Notify about user status changes"""
        try:
            # Get user details from database
            db = next(get_db())
            # TODO: MongoDB Migration - Update User import to use MongoDB models
            # from backend.database.models import User
            from backend.models.mongodb_models import User
            user = db.query(User).filter(User.id == user_id).first()
            
            if user:
                subject = "Account Status Update"
                message = f"""
                Hello {user.full_name or user.email},
                
                Your account status has been updated.
                
                Previous Status: {old_status}
                New Status: {new_status}
                
                If you have any questions, please contact our support team.
                
                Best regards,
                RemoteHive Team
                """
                
                await EmailService.send_plain_email(user.email, subject, message)
                logger.info(f"Status change notification sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send user status change notification: {str(e)}")
    
    @staticmethod
    async def notify_job_status_change(job_id: int, old_status: str, new_status: str):
        """Notify about job status changes"""
        try:
            # Get job and company details from database
            db = next(get_db())
            # TODO: MongoDB Migration - Update Job import to use MongoDB models
            # from backend.database.models import Job
            from backend.models.mongodb_models import Job
            job = db.query(Job).filter(Job.id == job_id).first()
            
            if job and job.company and job.company.contact_email:
                subject = f"Job Status Update - {job.title}"
                message = f"""
                Hello,
                
                The status of your job posting has been updated.
                
                Job Title: {job.title}
                Previous Status: {old_status}
                New Status: {new_status}
                
                You can view your job posting in the employer dashboard.
                
                Best regards,
                RemoteHive Team
                """
                
                await EmailService.send_plain_email(job.company.contact_email, subject, message)
                logger.info(f"Job status change notification sent for job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to send job status change notification: {str(e)}")
    
    @staticmethod
    async def send_system_maintenance_notice(maintenance_start: datetime, maintenance_end: datetime, description: str):
        """Send system maintenance notice to all active users"""
        try:
            db = next(get_db())
            # TODO: MongoDB Migration - Update User import to use MongoDB models
            # from backend.database.models import User
            from backend.models.mongodb_models import User
            
            # Get all active users
            active_users = db.query(User).filter(User.is_active == True).all()
            
            subject = "Scheduled System Maintenance Notice"
            message = f"""
            Dear RemoteHive Users,
            
            We will be performing scheduled system maintenance:
            
            Start Time: {maintenance_start.strftime('%Y-%m-%d %H:%M UTC')}
            End Time: {maintenance_end.strftime('%Y-%m-%d %H:%M UTC')}
            
            Description: {description}
            
            During this time, the platform may be temporarily unavailable.
            We apologize for any inconvenience.
            
            Best regards,
            RemoteHive Team
            """
            
            recipients = [user.email for user in active_users]
            result = await NotificationService.send_bulk_notification(recipients, subject, message)
            
            logger.info(f"System maintenance notice sent to {result['sent']} users")
            return result
            
        except Exception as e:
            logger.error(f"Failed to send system maintenance notice: {str(e)}")
            return {"sent": 0, "failed": 0}


# Create a singleton instance
notification_service = NotificationService()