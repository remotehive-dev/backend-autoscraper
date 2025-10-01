from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
import logging
import os
from backend.database.database import get_db_session
from backend.core.auth import get_admin
from backend.services.slack_service import SlackService
# from backend.database.models import ContactSubmission  # Commented out - model doesn't exist yet
# from sqlalchemy.orm import Session  # Commented out - using MongoDB
# from sqlalchemy import func, or_  # Commented out - using MongoDB
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic Models
class ContactSubmissionCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    subject: str = Field(..., min_length=5, max_length=200)
    message: str = Field(..., min_length=10, max_length=2000)
    inquiry_type: str = Field(default="general", pattern="^(general|support|business|press)$")
    phone: Optional[str] = Field(None, max_length=20)
    company_name: Optional[str] = Field(None, max_length=100)

class ContactSubmissionResponse(BaseModel):
    id: str
    name: str
    email: str
    subject: str
    message: str
    inquiry_type: str
    phone: Optional[str]
    company_name: Optional[str]
    status: str
    priority: str
    assigned_to: Optional[str]
    admin_notes: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    source: str
    created_at: datetime
    updated_at: Optional[datetime]
    resolved_at: Optional[datetime]

class ContactSubmitResponse(BaseModel):
    success: bool
    message: str
    submission_id: str
    estimated_response_time: str

class ContactSubmissionUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(new|in_progress|resolved|closed)$")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|urgent)$")
    assigned_to: Optional[str] = None
    admin_notes: Optional[str] = None

class ContactStats(BaseModel):
    total_submissions: int
    recent_submissions: int
    status_breakdown: dict
    inquiry_type_breakdown: dict
    priority_breakdown: dict

class EmailReplyRequest(BaseModel):
    subject: str
    message: str
    reply_type: str = "reply"  # reply, follow_up, resolution

class EmailReplyResponse(BaseModel):
    success: bool
    message: str
    email_sent_at: Optional[str] = None

# Public endpoint for contact form submission
@router.post("/submit", response_model=ContactSubmitResponse)
def submit_contact_form(
    submission: ContactSubmissionCreate,
    request: Request,
    # db: Session = Depends(get_db_session)  # Commented out - using MongoDB
):
    """
    Submit a contact form from the public website
    """
    try:
        # Get client IP and user agent
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        # Prepare submission data
        submission_data = {
            "name": submission.name,
            "email": submission.email,
            "subject": submission.subject,
            "message": submission.message,
            "inquiry_type": submission.inquiry_type,
            "phone": submission.phone,
            "company_name": submission.company_name,
            "status": "new",
            "priority": "medium",
            "ip_address": client_ip,
            "user_agent": user_agent,
            "source": "website_contact_form"
        }
        
        # Insert into database
        contact_record = ContactSubmission(**submission_data)
        db.add(contact_record)
        db.commit()
        db.refresh(contact_record)
        
        submission_id = contact_record.id
        logger.info(f"Contact form submitted successfully. ID: {submission_id}")
        
        # Send Slack notification
        slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if slack_webhook_url:
            try:
                slack_service = SlackService(slack_webhook_url)
                submission_data_with_id = {**submission_data, "id": submission_id}
                slack_notification_sent = slack_service.send_contact_notification(submission_data_with_id)
                if slack_notification_sent:
                    logger.info(f"Slack notification sent for submission ID: {submission_id}")
                else:
                    logger.warning(f"Failed to send Slack notification for submission ID: {submission_id}")
            except Exception as slack_error:
                logger.error(f"Error sending Slack notification for submission ID {submission_id}: {str(slack_error)}")
        else:
            logger.warning("SLACK_WEBHOOK_URL not configured, skipping Slack notification")
        
        return {
            "success": True,
            "message": "Thank you for your message! We'll get back to you soon.",
            "submission_id": str(submission_id),
            "estimated_response_time": "24 hours"
        }
        
    except Exception as e:
        logger.error(f"Error submitting contact form: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Admin endpoints
class ContactSubmissionsResponse(BaseModel):
    submissions: List[ContactSubmissionResponse]
    total: int
    page: int
    limit: int
    pages: int

@router.get("/admin/submissions", response_model=ContactSubmissionsResponse)
def get_contact_submissions(
    page: int = 1,
    limit: int = 50,
    status_filter: Optional[str] = None,
    inquiry_type_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    search: Optional[str] = None,
    # db: Session = Depends(get_db_session),  # Commented out - using MongoDB
    current_user = Depends(get_admin)
):
    """
    Get paginated list of contact submissions with filtering (Admin only)
    """
    try:
        # Build query
        query = db.query(ContactSubmission)
        
        # Apply filters
        if status_filter:
            query = query.filter(ContactSubmission.status == status_filter)
        if inquiry_type_filter:
            query = query.filter(ContactSubmission.inquiry_type == inquiry_type_filter)
        if priority_filter:
            query = query.filter(ContactSubmission.priority == priority_filter)
        if search:
            # Search in name, email, subject, and message
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    ContactSubmission.name.ilike(search_term),
                    ContactSubmission.email.ilike(search_term),
                    ContactSubmission.subject.ilike(search_term),
                    ContactSubmission.message.ilike(search_term)
                )
            )
        
        # Get total count for pagination
        total = query.count()
        
        # Apply pagination and ordering
        offset = (page - 1) * limit
        submissions = query.order_by(ContactSubmission.created_at.desc()).offset(offset).limit(limit).all()
        
        # Convert to response format
        submissions_data = []
        for submission in submissions:
            submission_dict = {
                "id": str(submission.id),
                "name": submission.name,
                "email": submission.email,
                "subject": submission.subject,
                "message": submission.message,
                "inquiry_type": submission.inquiry_type,
                "phone": submission.phone,
                "company_name": submission.company_name,
                "status": submission.status,
                "priority": submission.priority,
                "assigned_to": submission.assigned_to,
                "admin_notes": submission.admin_notes,
                "ip_address": submission.ip_address,
                "user_agent": submission.user_agent,
                "source": submission.source,
                "created_at": submission.created_at,
                "updated_at": submission.updated_at,
                "resolved_at": submission.resolved_at
            }
            submissions_data.append(submission_dict)
        
        return {
            "submissions": submissions_data,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
        
    except Exception as e:
        logger.error(f"Error fetching contact submissions: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/admin/submissions/{submission_id}", response_model=ContactSubmissionResponse)
def get_contact_submission(
    submission_id: str,
    # db: Session = Depends(get_db_session),  # Commented out - using MongoDB
    current_user = Depends(get_admin)
):
    """
    Get a specific contact submission (Admin only)
    """
    try:
        submission = db.query(ContactSubmission).filter(ContactSubmission.id == int(submission_id)).first()
        
        if not submission:
            raise HTTPException(status_code=404, detail="Contact submission not found")
        
        # Convert to response format
        return {
            "id": str(submission.id),
            "name": submission.name,
            "email": submission.email,
            "subject": submission.subject,
            "message": submission.message,
            "inquiry_type": submission.inquiry_type,
            "phone": submission.phone,
            "company_name": submission.company_name,
            "status": submission.status,
            "priority": submission.priority,
            "assigned_to": submission.assigned_to,
            "admin_notes": submission.admin_notes,
            "ip_address": submission.ip_address,
            "user_agent": submission.user_agent,
            "source": submission.source,
            "created_at": submission.created_at,
            "updated_at": submission.updated_at,
            "resolved_at": submission.resolved_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching contact submission {submission_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/test-slack")
def test_slack_integration(
    current_user = Depends(get_admin)
):
    """
    Test Slack webhook integration (Admin only)
    """
    try:
        slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not slack_webhook_url:
            raise HTTPException(status_code=400, detail="SLACK_WEBHOOK_URL not configured")
        
        slack_service = SlackService(slack_webhook_url)
        success = slack_service.send_test_message()
        
        if success:
            return {
                "success": True,
                "message": "Slack test message sent successfully!"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send Slack test message")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing Slack integration: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/admin/submissions/{submission_id}", response_model=ContactSubmissionResponse)
def update_contact_submission(
    submission_id: str,
    update_data: ContactSubmissionUpdate,
    # db: Session = Depends(get_db_session),  # Commented out - using MongoDB
    current_user = Depends(get_admin)
):
    """
    Update a contact submission (Admin only)
    """
    try:
        # Find the submission
        submission = db.query(ContactSubmission).filter(ContactSubmission.id == int(submission_id)).first()
        
        if not submission:
            raise HTTPException(status_code=404, detail="Contact submission not found")
        
        # Update fields
        if update_data.status is not None:
            submission.status = update_data.status
            if update_data.status == "resolved":
                submission.resolved_at = datetime.utcnow()
        if update_data.priority is not None:
            submission.priority = update_data.priority
        if update_data.assigned_to is not None:
            submission.assigned_to = update_data.assigned_to
        if update_data.admin_notes is not None:
            submission.admin_notes = update_data.admin_notes
        
        submission.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(submission)
        
        logger.info(f"Contact submission {submission_id} updated by admin {current_user.get('email', 'unknown')}")
        
        # Convert to response format
        return {
            "id": str(submission.id),
            "name": submission.name,
            "email": submission.email,
            "subject": submission.subject,
            "message": submission.message,
            "inquiry_type": submission.inquiry_type,
            "phone": submission.phone,
            "company_name": submission.company_name,
            "status": submission.status,
            "priority": submission.priority,
            "assigned_to": submission.assigned_to,
            "admin_notes": submission.admin_notes,
            "ip_address": submission.ip_address,
            "user_agent": submission.user_agent,
            "source": submission.source,
            "created_at": submission.created_at,
            "updated_at": submission.updated_at,
            "resolved_at": submission.resolved_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contact submission {submission_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/admin/submissions/{submission_id}")
def delete_contact_submission(
    submission_id: str,
    # db: Session = Depends(get_db_session),  # Commented out - using MongoDB
    current_user = Depends(get_admin)
):
    """
    Delete a contact submission (Admin only)
    """
    try:
        submission = db.query(ContactSubmission).filter(ContactSubmission.id == int(submission_id)).first()
        
        if not submission:
            raise HTTPException(status_code=404, detail="Contact submission not found")
        
        db.delete(submission)
        db.commit()
        
        logger.info(f"Contact submission {submission_id} deleted by admin {current_user.get('email', 'unknown')}")
        return {"success": True, "message": "Contact submission deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contact submission {submission_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/admin/submissions/{submission_id}/reply", response_model=EmailReplyResponse)
def send_email_reply(
    submission_id: str,
    reply_data: EmailReplyRequest,
    # db: Session = Depends(get_db_session),  # Commented out - using MongoDB
    current_user = Depends(get_admin)
):
    """
    Send an email reply to a contact submission (Admin only)
    """
    try:
        # Get the submission details
        submission = db.query(ContactSubmission).filter(ContactSubmission.id == int(submission_id)).first()
        
        if not submission:
            raise HTTPException(status_code=404, detail="Contact submission not found")
        
        recipient_email = submission.email
        recipient_name = submission.name
        
        if not recipient_email:
            raise HTTPException(status_code=400, detail="No email address found for this submission")
        
        # Email configuration from environment variables
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_username = os.getenv('SMTP_USERNAME')
        smtp_password = os.getenv('SMTP_PASSWORD')
        from_email = os.getenv('FROM_EMAIL', smtp_username)
        from_name = os.getenv('FROM_NAME', 'RemoteHive Support')
        
        if not smtp_username or not smtp_password:
            raise HTTPException(status_code=500, detail="Email configuration not found")
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = f"{from_name} <{from_email}>"
        msg['To'] = f"{recipient_name} <{recipient_email}>"
        msg['Subject'] = reply_data.subject
        
        # Email body with professional formatting
        email_body = f"""Dear {recipient_name},

Thank you for contacting RemoteHive. We have received your inquiry regarding: "{submission.subject}"

{reply_data.message}

If you have any further questions, please don't hesitate to reach out to us.

Best regards,
RemoteHive Support Team

---
This email is in response to your submission on {submission.created_at}
Submission ID: {submission_id}
"""
        
        msg.attach(MIMEText(email_body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        text = msg.as_string()
        server.sendmail(from_email, recipient_email, text)
        server.quit()
        
        # Update submission with reply information
        current_time = datetime.utcnow()
        submission.updated_at = current_time
        if submission.status == 'new':
            submission.status = 'in_progress'
        
        # Add to admin notes
        existing_notes = submission.admin_notes or ''
        new_note = f"\n[{current_time.isoformat()}] Email reply sent by {current_user.get('email', 'admin')}: {reply_data.subject}"
        submission.admin_notes = existing_notes + new_note
        
        db.commit()
        
        logger.info(f"Email reply sent for submission {submission_id} by admin {current_user.get('email', 'unknown')}")
        
        return {
            "success": True,
            "message": f"Email reply sent successfully to {recipient_email}",
            "email_sent_at": current_time.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email reply for submission {submission_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

@router.get("/admin/stats", response_model=ContactStats)
def get_contact_stats(
    # db: Session = Depends(get_db_session),  # Commented out - using MongoDB
    current_user = Depends(get_admin)
):
    """
    Get contact submission statistics (Admin only)
    """
    try:
        # Get total submissions
        total_submissions = db.query(ContactSubmission).count()
        
        # Get recent submissions (last 7 days)
        seven_days_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        recent_submissions = db.query(ContactSubmission).filter(ContactSubmission.created_at >= seven_days_ago).count()
        
        # Get status breakdown
        status_breakdown = {}
        for status in ["new", "in_progress", "resolved", "closed"]:
            status_breakdown[status] = db.query(ContactSubmission).filter(ContactSubmission.status == status).count()
        
        # Get inquiry type breakdown
        inquiry_type_breakdown = {}
        for inquiry_type in ["general", "support", "business", "press"]:
            inquiry_type_breakdown[inquiry_type] = db.query(ContactSubmission).filter(ContactSubmission.inquiry_type == inquiry_type).count()
        
        # Get priority breakdown
        priority_breakdown = {}
        for priority in ["low", "medium", "high", "urgent"]:
            priority_breakdown[priority] = db.query(ContactSubmission).filter(ContactSubmission.priority == priority).count()
        
        return {
            "total_submissions": total_submissions,
            "recent_submissions": recent_submissions,
            "status_breakdown": status_breakdown,
            "inquiry_type_breakdown": inquiry_type_breakdown,
            "priority_breakdown": priority_breakdown
        }
        
    except Exception as e:
        logger.error(f"Error fetching contact stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")