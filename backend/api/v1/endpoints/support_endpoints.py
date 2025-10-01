from fastapi import APIRouter, HTTPException, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr
from backend.core.database import get_db
# from backend.database.models import User, EmailLog  # Using MongoDB models instead
from backend.models.mongodb_models import User
from backend.core.local_auth import get_current_user
from backend.tasks.email import send_support_email_task
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class SupportRequest(BaseModel):
    subject: str
    message: str
    from_name: str = None
    from_email: EmailStr = None

class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    subject: str
    message: str

@router.post("/support")
async def send_support_request(
    support_data: SupportRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Send support request from authenticated user
    """
    try:
        # Get user details
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Use provided name/email or fall back to user data
        from_name = support_data.from_name or f"{user.first_name} {user.last_name}".strip() or user.email
        from_email = support_data.from_email or user.email
        
        # Queue support email task
        send_support_email_task.delay(
            from_email=from_email,
            from_name=from_name,
            subject=support_data.subject,
            message=support_data.message,
            user_id=str(user.id)
        )
        
        # Log the email request
        email_log = EmailLog(
            user_id=user.id,
            email_type="support_request",
            recipient_email=from_email,
            subject=f"Support Request: {support_data.subject}",
            status="queued",
            created_at=datetime.utcnow()
        )
        db.add(email_log)
        db.commit()
        
        logger.info(f"Support request queued from user: {user.email}")
        
        return {
            "message": "Support request sent successfully",
            "ticket_id": email_log.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending support request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send support request"
        )

@router.post("/contact")
async def send_contact_message(
    contact_data: ContactRequest,
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Send contact message from website visitors (no authentication required)
    """
    try:
        # Queue support email task
        send_support_email_task.delay(
            from_email=contact_data.email,
            from_name=contact_data.name,
            subject=contact_data.subject,
            message=contact_data.message,
            user_id=None  # No user ID for public contact
        )
        
        # Log the email request (no user_id for public contact)
        email_log = EmailLog(
            user_id=None,
            email_type="contact_form",
            recipient_email=contact_data.email,
            subject=f"Contact Form: {contact_data.subject}",
            status="queued",
            created_at=datetime.utcnow()
        )
        db.add(email_log)
        db.commit()
        
        logger.info(f"Contact message queued from: {contact_data.email}")
        
        return {
            "message": "Contact message sent successfully",
            "reference_id": email_log.id
        }
        
    except Exception as e:
        logger.error(f"Error sending contact message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send contact message"
        )

@router.get("/support/history")
async def get_support_history(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    """
    Get support request history for authenticated user
    """
    try:
        # Get user
        user = db.query(User).filter(User.id == current_user["user_id"]).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get support email history
        support_emails = db.query(EmailLog).filter(
            EmailLog.user_id == user.id,
            EmailLog.email_type.in_(["support_request", "contact_form"])
        ).order_by(EmailLog.created_at.desc()).limit(20).all()
        
        return {
            "support_requests": [
                {
                    "id": email.id,
                    "subject": email.subject,
                    "status": email.status,
                    "created_at": email.created_at.isoformat(),
                    "sent_at": email.sent_at.isoformat() if email.sent_at else None,
                    "error_message": email.error_message
                }
                for email in support_emails
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting support history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get support history"
        )