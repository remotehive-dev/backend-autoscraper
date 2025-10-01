from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, EmailStr
import secrets
import hashlib
from backend.models.mongodb_models import (
    User, Employer, JobSeeker, Freelancer, NewsletterSubscriber,
    PasswordResetToken
)
from backend.core.security import get_password_hash
from backend.services.gmail_service import gmail_service
from backend.core.config import get_settings
from backend.schemas.email import PasswordResetRequest, PasswordResetConfirm, PasswordResetValidate
from loguru import logger

router = APIRouter()
settings = get_settings()

class PasswordResetResponse(BaseModel):
    message: str
    success: bool

@router.post("/request-reset", response_model=PasswordResetResponse)
async def request_password_reset(
    request: PasswordResetRequest,
    background_tasks: BackgroundTasks
):
    """Request password reset for any user type"""
    try:
        # Find user based on type
        user = None
        user_model = None
        
        if request.user_type == "super_admin" or request.user_type == "admin":
            user = await User.find_one(User.email == request.email)
            user_model = User
        elif request.user_type in ["employer", "job_seeker", "freelancer"]:
            # For these user types, find the User record and verify they have the correct role
            user = await User.find_one(User.email == request.email)
            if user:
                # Verify the user has the correct role/profile
                if request.user_type == "employer":
                    employer_profile = await Employer.find_one(Employer.user_id == user.id)
                    if not employer_profile:
                        user = None
                elif request.user_type == "job_seeker":
                    job_seeker_profile = await JobSeeker.find_one(JobSeeker.user_id == user.id)
                    if not job_seeker_profile:
                        user = None
                elif request.user_type == "freelancer":
                    freelancer_profile = await Freelancer.find_one(Freelancer.user_id == user.id)
                    if not freelancer_profile:
                        user = None
            user_model = User
        elif request.user_type == "newsletter_subscriber":
            user = await NewsletterSubscriber.find_one(NewsletterSubscriber.email == request.email)
            user_model = NewsletterSubscriber
        else:
            raise HTTPException(status_code=400, detail="Invalid user type")
        
        if not user:
            # Don't reveal if email exists or not for security
            return PasswordResetResponse(
                message="If the email exists, a password reset link has been sent.",
                success=True
            )
        
        # Generate reset token
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Create or update password reset token
        existing_token = await PasswordResetToken.find_one(
            PasswordResetToken.email == request.email,
            PasswordResetToken.user_type == request.user_type
        )
        
        if existing_token:
            existing_token.token_hash = token_hash
            existing_token.expires_at = datetime.utcnow() + timedelta(hours=1)
            existing_token.used = False
            await existing_token.save()
        else:
            reset_token = PasswordResetToken(
                email=request.email,
                user_type=request.user_type,
                token_hash=token_hash,
                expires_at=datetime.utcnow() + timedelta(hours=1),
                used=False
            )
            await reset_token.save()
        
        # Send password reset email
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}&type={request.user_type}"
        
        # Prepare request info for email service
        request_info = {
            "user_agent": "RemoteHive Admin Panel",
            "ip_address": "127.0.0.1",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            await gmail_service.send_password_reset_email(
                to_email=request.email,
                user_name=getattr(user, 'name', getattr(user, 'first_name', 'User')),
                reset_url=reset_url,
                request_info=request_info
            )
            logger.info(f"Password reset email sent to {request.email} for user type {request.user_type}")
        except Exception as email_error:
            logger.error(f"Failed to send password reset email: {email_error}")
            # Don't fail the request if email fails
        
        return PasswordResetResponse(
            message="If the email exists, a password reset link has been sent.",
            success=True
        )
        
    except Exception as e:
        logger.error(f"Password reset request error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/confirm-reset", response_model=PasswordResetResponse)
async def confirm_password_reset(request: PasswordResetConfirm):
    """Confirm password reset with token"""
    try:
        # Hash the provided token
        token_hash = hashlib.sha256(request.token.encode()).hexdigest()
        
        # Find the reset token
        reset_token = await PasswordResetToken.find_one(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.user_type == request.user_type,
            PasswordResetToken.used == False
        )
        
        if not reset_token:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        
        # Check if token is expired
        if reset_token.expires_at < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Reset token has expired")
        
        # Find and update user password
        user = None
        user_model = None
        
        if request.user_type == "super_admin" or request.user_type == "admin":
            user = await User.find_one(User.email == reset_token.email)
            user_model = User
        elif request.user_type in ["employer", "job_seeker", "freelancer"]:
            # All these user types are linked to the main User model
            user = await User.find_one(User.email == reset_token.email)
            user_model = User
        elif request.user_type == "newsletter_subscriber":
            user = await NewsletterSubscriber.find_one(NewsletterSubscriber.email == reset_token.email)
            user_model = NewsletterSubscriber
        else:
            raise HTTPException(status_code=400, detail="Invalid user type")
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update password
        hashed_password = get_password_hash(request.new_password)
        if hasattr(user, 'password_hash'):
            user.password_hash = hashed_password
        elif hasattr(user, 'hashed_password'):
            user.hashed_password = hashed_password
        else:
            # For newsletter subscribers, they might not have passwords
            if request.user_type == "newsletter_subscriber":
                raise HTTPException(status_code=400, detail="Newsletter subscribers cannot reset passwords")
            else:
                raise HTTPException(status_code=500, detail="User model does not support password reset")
        await user.save()
        
        # Mark token as used
        reset_token.used = True
        reset_token.used_at = datetime.utcnow()
        await reset_token.save()
        
        logger.info(f"Password reset completed for {reset_token.email} (type: {request.user_type})")
        
        return PasswordResetResponse(
            message="Password has been reset successfully.",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password reset confirmation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/validate-token/{token}")
async def validate_reset_token(token: str, user_type: str):
    """Validate if a reset token is valid and not expired"""
    try:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        reset_token = await PasswordResetToken.find_one(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.user_type == user_type,
            PasswordResetToken.used == False
        )
        
        if not reset_token:
            return {"valid": False, "message": "Invalid token"}
        
        if reset_token.expires_at < datetime.utcnow():
            return {"valid": False, "message": "Token expired"}
        
        return {
            "valid": True,
            "email": reset_token.email,
            "expires_at": reset_token.expires_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}")
        return {"valid": False, "message": "Validation error"}