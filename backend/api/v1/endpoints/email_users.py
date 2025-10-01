from fastapi import APIRouter, Depends, HTTPException, status, Query
# from sqlalchemy.orm import Session  # Using MongoDB instead
from typing import List, Optional
from backend.core.security import get_current_user, require_admin, require_super_admin
from backend.core.database import get_db
from backend.schemas.email_users import (
    EmailUserCreate, EmailUserResponse, EmailUserUpdate, EmailSendRequest,
    EmailTestRequest, PasswordResetRequest
)
from backend.services.email_management_service import EmailManagementService
from backend.services.email_service import EmailService
# TODO: Migrate email models to MongoDB or handle differently
# from backend.models.email import EmailUser, EmailMessage
from datetime import datetime
import uuid

router = APIRouter()

@router.post("/test-send")
def test_send_email(
    email_request: EmailTestRequest,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_admin)
):
    """Test sending email to specified address"""
    email_service = EmailService(db)
    
    # Test SMTP connection first
    if not email_service.test_email_connection():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SMTP connection failed. Please check email configuration."
        )
    
    # Send test email
    success = email_service.send_email(
        to_email=email_request.to_email,
        subject=email_request.subject or "Test Email from RemoteHive",
        body=email_request.body or "<h2>Hello!</h2><p>This is a test email from RemoteHive email system.</p><p>If you received this, the email system is working correctly!</p>",
        is_html=True
    )
    
    if success:
        return {
            "success": True,
            "message": f"Test email sent successfully to {email_request.to_email}"
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test email"
        )

@router.get("/", response_model=List[EmailUserResponse])
def get_email_users(
    skip: int = 0,
    limit: int = 100,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_admin)
):
    """Get all email users"""
    email_management = EmailManagementService(db)
    email_users = email_management.get_all_email_users(limit=limit, offset=skip)
    return email_users

@router.get("/search")
def search_email_users(
    q: str = Query(..., description="Search query for email address or name"),
    limit: int = 50,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_admin)
):
    """Search email users by email address or name"""
    email_management = EmailManagementService(db)
    users = email_management.search_email_users(query=q, limit=limit)
    return {
        "users": users,
        "total": len(users),
        "query": q
    }

@router.post("/", response_model=dict)
def create_email_user(
    email_user: EmailUserCreate,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_admin)
):
    """Create new email user with welcome email"""
    # Check if email already exists
    existing_user = db.query(EmailUser).filter(
        EmailUser.email == email_user.email_address,
        EmailUser.deleted_at.is_(None)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address already exists"
        )
    
    email_management = EmailManagementService(db)
    result = email_management.create_email_user(
        email_address=email_user.email_address,
        full_name=email_user.full_name,
        personal_email=email_user.personal_email,
        created_by=current_user.id,
        role=email_user.role
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result['error']
        )
    
    return result

@router.post("/{user_id}/reset-password")
def reset_user_password(
    user_id: str,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_super_admin)
):
    """Reset user password (Super Admin only)"""
    email_management = EmailManagementService(db)
    result = email_management.reset_user_password(
        user_id=user_id,
        reset_by=current_user.id
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['error']
        )
    
    return result

@router.post("/send-email")
def send_email(
    email_request: EmailSendRequest,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_admin)
):
    """Send email from user account"""
    email_management = EmailManagementService(db)
    
    # Find sender's email user account
    sender = db.query(EmailUser).filter(
        EmailUser.created_by == current_user.id,
        EmailUser.deleted_at.is_(None),
        EmailUser.is_active == True
    ).first()
    
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active email account found for current user"
        )
    
    result = email_management.send_email(
        from_user_id=sender.id,
        to_emails=email_request.to_emails,
        subject=email_request.subject,
        body=email_request.body,
        cc_emails=email_request.cc_emails,
        bcc_emails=email_request.bcc_emails,
        is_draft=email_request.is_draft
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result['error']
        )
    
    return result

@router.get("/messages/{folder_name}")
def get_user_messages(
    folder_name: str,
    skip: int = 0,
    limit: int = 50,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_admin)
):
    """Get user messages from specific folder (inbox, sent, drafts, spam, trash, starred)"""
    # Find user's email account
    email_user = db.query(EmailUser).filter(
        EmailUser.created_by == current_user.id,
        EmailUser.deleted_at.is_(None),
        EmailUser.is_active == True
    ).first()
    
    if not email_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active email account found for current user"
        )
    
    email_management = EmailManagementService(db)
    messages = email_management.get_user_messages(
        user_id=email_user.id,
        folder_name=folder_name,
        limit=limit,
        offset=skip
    )
    
    return {
        "messages": messages,
        "folder": folder_name,
        "total": len(messages)
    }

@router.post("/messages/{message_id}/star")
def star_message(
    message_id: str,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_admin)
):
    """Star/unstar a message"""
    # Find user's email account
    email_user = db.query(EmailUser).filter(
        EmailUser.created_by == current_user.id,
        EmailUser.deleted_at.is_(None),
        EmailUser.is_active == True
    ).first()
    
    if not email_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active email account found for current user"
        )
    
    email_management = EmailManagementService(db)
    result = email_management.star_message(
        user_id=email_user.id,
        message_id=message_id
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['error']
        )
    
    return result

@router.post("/messages/{message_id}/spam")
def move_to_spam(
    message_id: str,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_admin)
):
    """Move message to spam folder"""
    # Find user's email account
    email_user = db.query(EmailUser).filter(
        EmailUser.created_by == current_user.id,
        EmailUser.deleted_at.is_(None),
        EmailUser.is_active == True
    ).first()
    
    if not email_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active email account found for current user"
        )
    
    email_management = EmailManagementService(db)
    result = email_management.move_to_spam(
        user_id=email_user.id,
        message_id=message_id
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['error']
        )
    
    return result

@router.get("/{user_id}", response_model=EmailUserResponse)
def get_email_user(
    user_id: str,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_admin)
):
    """Get email user by ID"""
    email_user = db.query(EmailUser).filter(
        EmailUser.id == user_id,
        EmailUser.deleted_at.is_(None)
    ).first()
    
    if not email_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email user not found"
        )
    
    return email_user

@router.put("/{user_id}", response_model=EmailUserResponse)
def update_email_user(
    user_id: str,
    email_user_update: EmailUserUpdate,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_admin)
):
    """Update email user"""
    email_user = db.query(EmailUser).filter(
        EmailUser.id == user_id,
        EmailUser.deleted_at.is_(None)
    ).first()
    
    if not email_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email user not found"
        )
    
    # Update fields
    for field, value in email_user_update.dict(exclude_unset=True).items():
        setattr(email_user, field, value)
    
    email_user.updated_by = current_user.id
    email_user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(email_user)
    
    return email_user

@router.delete("/{user_id}")
def delete_email_user(
    user_id: str,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(require_admin)
):
    """Delete email user (soft delete)"""
    email_management = EmailManagementService(db)
    result = email_management.delete_email_user(
        user_id=user_id,
        deleted_by=current_user.id
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result['error']
        )
    
    return result