from fastapi import APIRouter, HTTPException, Depends, status, Query
# from sqlalchemy.orm import Session  # Using MongoDB instead
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import json

from backend.database.database import get_db_session as get_db
from backend.core.auth import get_admin
# from backend.database.models import EmailTemplate, EmailLog, SystemSettings
# TODO: Implement EmailTemplate and EmailLog models in MongoDB
# TODO: Import SystemSettings from deployment_package or implement in current MongoDB models
# Note: EmailTemplate and EmailLog are currently handled as dictionaries in email_management_service.py
from backend.schemas.email import (
    EmailTemplate as EmailTemplateSchema,
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailLog as EmailLogSchema,
    EmailStats,
    EmailTestRequest,
    EmailTestResponse,
    EmailPreviewRequest,
    EmailPreviewResponse,
    SMTPSettings,
    SMTPSettingsUpdate,
    GmailAPISettings,
    GmailAPISettingsUpdate,
    EmailProviderSettings,
    EmailProviderType,
    PaginatedEmailTemplates,
    PaginatedEmailLogs,
    BulkEmailRequest,
    BulkEmailResponse
)
from backend.tasks.email import send_email, render_email_template
from backend.core.config import settings
# from sqlalchemy import func, desc, or_  # Using MongoDB instead
from jinja2 import Template, TemplateSyntaxError
import re

logger = logging.getLogger(__name__)
router = APIRouter()

# Email Templates Endpoints
@router.get("/templates", response_model=PaginatedEmailTemplates)
async def get_email_templates(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(get_admin)
):
    """Get paginated list of email templates"""
    try:
        query = db.query(EmailTemplate)
        
        # Apply filters
        if search:
            query = query.filter(
                or_(
                    EmailTemplate.name.ilike(f"%{search}%"),
                    EmailTemplate.subject.ilike(f"%{search}%"),
                    EmailTemplate.template_type.ilike(f"%{search}%")
                )
            )
        
        if category:
            query = query.filter(EmailTemplate.template_type == category)
        
        if is_active is not None:
            query = query.filter(EmailTemplate.is_active == is_active)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        templates = query.order_by(desc(EmailTemplate.updated_at)).offset((page - 1) * size).limit(size).all()
        
        return PaginatedEmailTemplates(
            items=templates,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
    
    except Exception as e:
        logger.error(f"Error fetching email templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch email templates"
        )

@router.get("/templates/{template_id}", response_model=EmailTemplateSchema)
async def get_email_template(
    template_id: int,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(get_admin)
):
    """Get a specific email template by ID"""
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email template not found"
        )
    
    return template

@router.post("/templates", response_model=EmailTemplateSchema)
async def create_email_template(
    template_data: EmailTemplateCreate,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(get_admin)
):
    """Create a new email template"""
    try:
        # Check if template name already exists
        existing = db.query(EmailTemplate).filter(EmailTemplate.name == template_data.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template with this name already exists"
            )
        
        # Validate template syntax
        try:
            Template(template_data.html_content)
        except TemplateSyntaxError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid template syntax: {str(e)}"
            )
        
        # Create new template
        template = EmailTemplate(
            name=template_data.name,
            subject=template_data.subject,
            html_content=template_data.html_content,
            text_content=template_data.text_content,
            template_type=template_data.template_type,
            is_active=template_data.is_active
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        logger.info(f"Email template created: {template.name} by admin {current_user.get('user_id')}")
        return template
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating email template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create email template"
        )

@router.put("/templates/{template_id}", response_model=EmailTemplateSchema)
async def update_email_template(
    template_id: int,
    template_data: EmailTemplateUpdate,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(get_admin)
):
    """Update an existing email template"""
    try:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email template not found"
            )
        
        # Check for name conflicts if name is being updated
        if template_data.name and template_data.name != template.name:
            existing = db.query(EmailTemplate).filter(
                EmailTemplate.name == template_data.name,
                EmailTemplate.id != template_id
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Template with this name already exists"
                )
        
        # Validate template syntax if html_content is being updated
        if template_data.html_content:
            try:
                Template(template_data.html_content)
            except TemplateSyntaxError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid template syntax: {str(e)}"
                )
        
        # Update template fields
        update_data = template_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)
        
        template.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(template)
        
        logger.info(f"Email template updated: {template.name} by admin {current_user.get('user_id')}")
        return template
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating email template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update email template"
        )

@router.delete("/templates/{template_id}")
async def delete_email_template(
    template_id: int,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(get_admin)
):
    """Delete an email template"""
    try:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email template not found"
            )
        
        # Check if template is being used in email logs
        logs_count = db.query(EmailLog).filter(EmailLog.template_name == template.name).count()
        if logs_count > 0:
            # Instead of deleting, deactivate the template
            template.is_active = False
            db.commit()
            logger.info(f"Email template deactivated (has {logs_count} logs): {template.name}")
            return {"message": "Template deactivated due to existing usage in email logs"}
        
        db.delete(template)
        db.commit()
        
        logger.info(f"Email template deleted: {template.name} by admin {current_user.get('user_id')}")
        return {"message": "Email template deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting email template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete email template"
        )

# Email Preview Endpoint
@router.post("/templates/{template_id}/preview", response_model=EmailPreviewResponse)
async def preview_email_template(
    template_id: int,
    preview_data: EmailPreviewRequest,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(get_admin)
):
    """Preview an email template with sample data"""
    try:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email template not found"
            )
        
        # Use provided template data or default sample data
        template_data = preview_data.template_data or {
            "user_name": "Test User",
            "company_name": "Test Company",
            "job_title": "Test Position",
            "job_count": 5,
            "base_url": settings.FRONTEND_URL or "https://remotehive.com"
        }
        
        # Render the template
        try:
            html_template = Template(template.html_content)
            subject_template = Template(template.subject)
            
            rendered_html = html_template.render(**template_data)
            rendered_subject = subject_template.render(**template_data)
            
            rendered_text = None
            if template.text_content:
                text_template = Template(template.text_content)
                rendered_text = text_template.render(**template_data)
            
            # Extract variables used in template
            variables_used = list(set(re.findall(r'{{\s*(\w+)\s*}}', template.html_content + template.subject)))
            
            return EmailPreviewResponse(
                subject=rendered_subject,
                html_content=rendered_html,
                text_content=rendered_text,
                variables_used=variables_used
            )
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template rendering error: {str(e)}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing email template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preview email template"
        )

# Email Test Endpoint
@router.post("/test", response_model=EmailTestResponse)
async def test_email(
    test_data: EmailTestRequest,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(get_admin)
):
    """Send a test email"""
    try:
        html_content = None
        subject = test_data.subject or "Test Email from RemoteHive"
        
        if test_data.template_id:
            # Use template
            template = db.query(EmailTemplate).filter(EmailTemplate.id == test_data.template_id).first()
            if not template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email template not found"
                )
            
            template_data = test_data.template_data or {
                "user_name": "Test User",
                "company_name": "Test Company",
                "job_title": "Test Position",
                "base_url": settings.FRONTEND_URL or "https://remotehive.com"
            }
            
            html_template = Template(template.html_content)
            subject_template = Template(template.subject)
            
            html_content = html_template.render(**template_data)
            subject = subject_template.render(**template_data)
        
        elif test_data.html_content:
            # Use provided HTML content
            html_content = test_data.html_content
        
        else:
            # Default test content
            html_content = "<h1>Test Email</h1><p>This is a test email from RemoteHive admin panel.</p>"
        
        # Send the email
        email_result = send_email(
            to_email=test_data.recipient_email,
            subject=subject,
            html_content=html_content
        )
        
        success = email_result.get('success', False) if isinstance(email_result, dict) else bool(email_result)
        
        # Log the test email
        email_log = EmailLog(
            recipient_email=test_data.recipient_email,
            subject=subject,
            template_name=f"test_template_{test_data.template_id}" if test_data.template_id else "manual_test",
            status="sent" if success else "failed",
            sent_at=datetime.utcnow() if success else None
        )
        db.add(email_log)
        db.commit()
        db.refresh(email_log)
        
        logger.info(f"Test email sent to {test_data.recipient_email} by admin {current_user.get('user_id')}")
        
        return EmailTestResponse(
            success=success,
            message="Test email sent successfully" if success else "Failed to send test email",
            email_log_id=email_log.id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error sending test email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test email"
        )

# Email Logs Endpoints
@router.get("/logs", response_model=PaginatedEmailLogs)
async def get_email_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    template_name: Optional[str] = Query(None),
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(get_admin)
):
    """Get paginated list of email logs"""
    try:
        query = db.query(EmailLog)
        
        # Apply filters
        if search:
            query = query.filter(
                or_(
                    EmailLog.recipient_email.ilike(f"%{search}%"),
                    EmailLog.subject.ilike(f"%{search}%")
                )
            )
        
        if status:
            query = query.filter(EmailLog.status == status)
        
        if template_name:
            query = query.filter(EmailLog.template_name == template_name)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        logs = query.order_by(desc(EmailLog.created_at)).offset((page - 1) * size).limit(size).all()
        
        return PaginatedEmailLogs(
            items=logs,
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )
    
    except Exception as e:
        logger.error(f"Error fetching email logs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch email logs"
        )

# Email Statistics Endpoint
@router.get("/stats", response_model=EmailStats)
async def get_email_stats(
    days: int = Query(30, ge=1, le=365),
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(get_admin)
):
    """Get email statistics for the specified number of days"""
    try:
        from datetime import timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get statistics
        total_sent = db.query(EmailLog).filter(
            EmailLog.status == "sent",
            EmailLog.created_at >= start_date
        ).count()
        
        total_failed = db.query(EmailLog).filter(
            EmailLog.status == "failed",
            EmailLog.created_at >= start_date
        ).count()
        
        total_pending = db.query(EmailLog).filter(
            EmailLog.status == "pending",
            EmailLog.created_at >= start_date
        ).count()
        
        total_emails = total_sent + total_failed
        delivery_rate = (total_sent / total_emails * 100) if total_emails > 0 else 0
        
        # Calculate average delivery time (simplified)
        avg_delivery_time = 2.5  # Default value, can be calculated from actual data
        
        return EmailStats(
            total_sent=total_sent,
            total_failed=total_failed,
            total_pending=total_pending,
            delivery_rate=round(delivery_rate, 2),
            avg_delivery_time=avg_delivery_time
        )
    
    except Exception as e:
        logger.error(f"Error fetching email stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch email statistics"
        )

# SMTP Settings Endpoints
@router.get("/smtp-settings", response_model=SMTPSettings)
async def get_smtp_settings(
    current_user = Depends(get_admin),
    # db: Session = Depends(get_db)  # Using MongoDB instead
):
    """Get current SMTP settings"""
    try:
        # Get SMTP settings from system_settings table
        smtp_keys = [
            'email_host', 'email_port', 'email_username', 
            'email_password', 'email_from', 'email_use_tls', 'email_use_ssl'
        ]
        
        smtp_settings = {}
        for key in smtp_keys:
            setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
            if setting:
                if key == 'email_port':
                    smtp_settings[key] = int(setting.value)
                elif key in ['email_use_tls', 'email_use_ssl']:
                    smtp_settings[key] = setting.value.lower() == 'true'
                else:
                    smtp_settings[key] = setting.value
            else:
                # Fallback to config values with proper defaults
                if key == 'email_host':
                    smtp_settings[key] = settings.EMAIL_HOST or 'smtp.gmail.com'
                elif key == 'email_port':
                    smtp_settings[key] = settings.EMAIL_PORT or 587
                elif key == 'email_username':
                    smtp_settings[key] = settings.EMAIL_USERNAME or 'admin@remotehive.in'
                elif key == 'email_password':
                    smtp_settings[key] = '***masked***'  # Never expose actual password
                elif key == 'email_from':
                    smtp_settings[key] = settings.EMAIL_FROM or 'noreply@remotehive.com'
                elif key == 'email_use_tls':
                    smtp_settings[key] = getattr(settings, 'EMAIL_USE_TLS', True)
                elif key == 'email_use_ssl':
                    smtp_settings[key] = getattr(settings, 'EMAIL_USE_SSL', False)
        
        logger.info(f"SMTP settings before validation: {smtp_settings}")
        result = SMTPSettings(**smtp_settings)
        logger.info(f"SMTP settings validation successful")
        return result
    
    except Exception as e:
        logger.error(f"Error fetching SMTP settings: {str(e)}")
        logger.error(f"SMTP settings data: {smtp_settings if 'smtp_settings' in locals() else 'Not available'}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch SMTP settings"
        )

@router.put("/smtp-settings", response_model=SMTPSettings)
async def update_smtp_settings(
    smtp_data: SMTPSettingsUpdate,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user = Depends(get_admin)
):
    """Update SMTP settings"""
    try:
        update_data = smtp_data.dict(exclude_unset=True)
        
        for key, value in update_data.items():
            # Find existing setting or create new one
            setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
            
            if setting:
                setting.value = str(value)
                setting.updated_at = datetime.utcnow()
            else:
                setting = SystemSettings(
                    key=key,
                    value=str(value),
                    data_type='string',
                    description=f'SMTP setting: {key}',
                    is_public=False
                )
                db.add(setting)
        
        db.commit()
        
        logger.info(f"SMTP settings updated by admin {current_user.get('user_id')}")
        
        # Return updated settings (mask password)
        updated_settings = smtp_data.dict(exclude_unset=True)
        if 'email_password' in updated_settings:
            updated_settings['email_password'] = '***masked***'
        
        # Get current settings to fill in missing values
        current_settings = await get_smtp_settings(current_user, db)
        current_dict = current_settings.dict()
        current_dict.update(updated_settings)
        
        return SMTPSettings(**current_dict)
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating SMTP settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update SMTP settings"
        )

# Gmail API Settings Endpoints
@router.get("/gmail-api-settings", response_model=GmailAPISettings)
async def get_gmail_api_settings(
    current_user = Depends(get_admin)
):
    """Get current Gmail API settings"""
    try:
        from backend.core.config import settings
        
        # Get Gmail API settings from system_settings or config
        gmail_settings = {
            'gmail_api_key': settings.GMAIL_API_KEY or '***masked***',
            'gmail_from_email': settings.EMAIL_FROM or 'noreply@remotehive.com',
            'gmail_from_name': getattr(settings, 'GMAIL_FROM_NAME', 'RemoteHive'),
            'is_enabled': bool(settings.GMAIL_API_KEY)
        }
        
        logger.info(f"Gmail API settings retrieved successfully")
        return GmailAPISettings(**gmail_settings)
    
    except Exception as e:
        logger.error(f"Error fetching Gmail API settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch Gmail API settings"
        )

@router.put("/gmail-api-settings", response_model=GmailAPISettings)
async def update_gmail_api_settings(
    gmail_data: GmailAPISettingsUpdate,
    current_user = Depends(get_admin)
):
    """Update Gmail API settings"""
    try:
        from backend.database.mongodb_models import SystemSettings
        
        update_data = gmail_data.dict(exclude_unset=True)
        
        # Update settings in database
        for key, value in update_data.items():
            setting_key = f"gmail_{key}" if not key.startswith('gmail_') else key
            
            # Find existing setting or create new one
            existing_setting = await SystemSettings.find_one({"key": setting_key})
            
            if existing_setting:
                existing_setting.value = str(value)
                existing_setting.updated_at = datetime.utcnow()
                await existing_setting.save()
            else:
                new_setting = SystemSettings(
                    key=setting_key,
                    value=str(value),
                    data_type='string',
                    description=f'Gmail API setting: {key}',
                    is_public=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                await new_setting.insert()
        
        logger.info(f"Gmail API settings updated by admin {current_user.get('user_id')}")
        
        # Return updated settings (mask API key)
        updated_settings = gmail_data.dict(exclude_unset=True)
        if 'gmail_api_key' in updated_settings:
            updated_settings['gmail_api_key'] = '***masked***'
        
        # Get current settings to fill in missing values
        current_settings = await get_gmail_api_settings(current_user)
        current_dict = current_settings.dict()
        current_dict.update(updated_settings)
        
        return GmailAPISettings(**current_dict)
    
    except Exception as e:
        logger.error(f"Error updating Gmail API settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update Gmail API settings"
        )

# Email Provider Settings Endpoint
@router.get("/provider-settings", response_model=EmailProviderSettings)
async def get_email_provider_settings(
    current_user = Depends(get_admin)
):
    """Get current email provider settings (SMTP + Gmail API)"""
    try:
        # Get both SMTP and Gmail API settings
        smtp_settings = await get_smtp_settings(current_user)
        gmail_settings = await get_gmail_api_settings(current_user)
        
        # Determine active provider based on Gmail API availability
        provider_type = EmailProviderType.GMAIL_API if gmail_settings.is_enabled else EmailProviderType.SMTP
        
        return EmailProviderSettings(
            provider_type=provider_type,
            smtp_settings=smtp_settings,
            gmail_api_settings=gmail_settings
        )
    
    except Exception as e:
        logger.error(f"Error fetching email provider settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch email provider settings"
        )

@router.post("/test-gmail-connection")
async def test_gmail_connection(
    current_user = Depends(get_admin)
):
    """Test Gmail API connection"""
    try:
        from backend.services.gmail_service import gmail_service
        
        # Test Gmail API connection
        result = await gmail_service.test_connection()
        
        if result:
            return {"success": True, "message": "Gmail API connection successful"}
        else:
            return {"success": False, "message": "Gmail API connection failed"}
    
    except Exception as e:
        logger.error(f"Error testing Gmail connection: {str(e)}")
        return {"success": False, "message": f"Gmail API test failed: {str(e)}"}