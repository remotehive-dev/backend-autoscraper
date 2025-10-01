from celery import current_app as celery_app
from backend.core.database import get_db
from backend.core.config import settings
from backend.database.services import UserService, JobPostService, JobApplicationService
from backend.database.database import get_database_manager
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
from typing import List, Dict, Any, Optional
from jinja2 import Template

logger = logging.getLogger(__name__)

# Email templates
WELCOME_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Welcome to RemoteHive</title>
</head>
<body>
    <h1>Welcome to RemoteHive, {{ user_name }}!</h1>
    <p>Thank you for joining our platform. We're excited to help you find your next remote opportunity.</p>
    <p>Here are some next steps to get started:</p>
    <ul>
        <li>Complete your profile</li>
        <li>Upload your resume</li>
        <li>Set up job alerts</li>
        <li>Browse available positions</li>
    </ul>
    <p>Best regards,<br>The RemoteHive Team</p>
</body>
</html>
"""

JOB_ALERT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>New Job Matches - RemoteHive</title>
</head>
<body>
    <h1>New Job Opportunities for You!</h1>
    <p>Hi {{ user_name }},</p>
    <p>We found {{ job_count }} new job(s) that match your preferences:</p>
    
    {% for job in jobs %}
    <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0;">
        <h3>{{ job.title }}</h3>
        <p><strong>Company:</strong> {{ job.company_name }}</p>
        <p><strong>Location:</strong> {{ job.location }}</p>
        <p><strong>Type:</strong> {{ job.job_type }}</p>
        {% if job.salary_min and job.salary_max %}
        <p><strong>Salary:</strong> ${{ job.salary_min }} - ${{ job.salary_max }}</p>
        {% endif %}
        <p>{{ job.description[:200] }}...</p>
        <a href="{{ base_url }}/jobs/{{ job.id }}" style="background-color: #007bff; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">View Job</a>
    </div>
    {% endfor %}
    
    <p>Best regards,<br>The RemoteHive Team</p>
</body>
</html>
"""

APPLICATION_STATUS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Application Status Update - RemoteHive</title>
</head>
<body>
    <h1>Application Status Update</h1>
    <p>Hi {{ user_name }},</p>
    <p>Your application for <strong>{{ job_title }}</strong> at <strong>{{ company_name }}</strong> has been updated.</p>
    <p><strong>New Status:</strong> {{ status }}</p>
    {% if message %}
    <p><strong>Message from employer:</strong></p>
    <p>{{ message }}</p>
    {% endif %}
    <p>You can view your application details <a href="{{ base_url }}/applications/{{ application_id }}">here</a>.</p>
    <p>Best regards,<br>The RemoteHive Team</p>
</body>
</html>
"""

EMAIL_VERIFICATION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Verify Your Email - RemoteHive</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #007bff; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background-color: #f9f9f9; }
        .button { background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Verify Your Email Address</h1>
        </div>
        <div class="content">
            <p>Hi {{ user_name }},</p>
            <p>Thank you for signing up for RemoteHive! To complete your registration and start exploring job opportunities, please verify your email address by clicking the button below:</p>
            <p style="text-align: center;">
                <a href="{{ verification_url }}" class="button">Verify Email Address</a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; background-color: #f0f0f0; padding: 10px; border-radius: 3px;">{{ verification_url }}</p>
            <p><strong>Important:</strong> This verification link will expire in {{ expiry_hours }} hour(s) for security reasons.</p>
            <p>If you didn't create an account with RemoteHive, please ignore this email and no account will be created.</p>
            <p>Need help? Contact our support team at <a href="mailto:{{ support_email }}">{{ support_email }}</a></p>
        </div>
        <div class="footer">
            <p>Best regards,<br>The RemoteHive Team</p>
            <p>This is an automated message, please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""

SUPPORT_REQUEST_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Support Request - RemoteHive</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #dc3545; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background-color: #f9f9f9; }
        .info-box { background-color: #e9ecef; padding: 15px; border-radius: 5px; margin: 15px 0; }
        .message-box { background-color: white; padding: 15px; border-left: 4px solid #007bff; margin: 15px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>New Support Request</h1>
        </div>
        <div class="content">
            <div class="info-box">
                <h3>Contact Information</h3>
                <p><strong>Name:</strong> {{ from_name }}</p>
                <p><strong>Email:</strong> {{ from_email }}</p>
                <p><strong>User ID:</strong> {{ user_id or 'Not provided' }}</p>
                <p><strong>Timestamp:</strong> {{ timestamp }}</p>
            </div>
            <div class="info-box">
                <h3>Subject</h3>
                <p>{{ user_subject }}</p>
            </div>
            <div class="message-box">
                <h3>Message</h3>
                <p>{{ user_message }}</p>
            </div>
            <p><em>Please respond to this support request as soon as possible.</em></p>
        </div>
    </div>
</body>
</html>
"""

def send_email(to_email: str, subject: str, template_name: str = None, template_data: dict = None, html_content: str = None, attachments: Optional[List[str]] = None, reply_to: str = None):
    """Send an email using SMTP with template support."""
    try:
        logger.info(f"Attempting to send email to {to_email} with subject: {subject}")
        logger.info(f"SMTP settings - Host: {settings.EMAIL_HOST}, Port: {settings.EMAIL_PORT}, Username: {settings.EMAIL_USERNAME}")
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = settings.EMAIL_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add reply-to if provided
        if reply_to:
            msg['Reply-To'] = reply_to
        
        # Generate HTML content from template or use provided content
        if template_name and template_data:
            html_content = render_email_template(template_name, template_data)
        elif not html_content:
            raise ValueError("Either template_name with template_data or html_content must be provided")
        
        # Add HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Add attachments if any
        if attachments:
            for file_path in attachments:
                try:
                    with open(file_path, 'rb') as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {file_path.split("/")[-1]}'
                    )
                    msg.attach(part)
                except Exception as e:
                    logger.error(f"Failed to attach file {file_path}: {str(e)}")
        
        # Send email
        logger.info("Starting SMTP connection...")
        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
            logger.info("SMTP connection established")
            if settings.EMAIL_USE_TLS:
                logger.info("Starting TLS...")
                server.starttls()
                logger.info("TLS started successfully")
            if settings.EMAIL_USERNAME and settings.EMAIL_PASSWORD:
                logger.info("Authenticating with SMTP server...")
                server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
                logger.info("Authentication successful")
            
            logger.info("Sending email message...")
            server.send_message(msg)
            logger.info("Email message sent successfully")
        
        logger.info(f"Email sent successfully to {to_email}")
        return {'success': True, 'message': f'Email sent to {to_email}'}
    
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return {'success': False, 'message': str(e)}

def render_email_template(template_name: str, template_data: dict) -> str:
    """Render email template with provided data."""
    templates = {
        'welcome': WELCOME_EMAIL_TEMPLATE,
        'job_alert': JOB_ALERT_TEMPLATE,
        'application_status': APPLICATION_STATUS_TEMPLATE,
        'email_verification': EMAIL_VERIFICATION_TEMPLATE,
        'support_request': SUPPORT_REQUEST_TEMPLATE
    }
    
    if template_name not in templates:
        raise ValueError(f"Template '{template_name}' not found")
    
    template = Template(templates[template_name])
    return template.render(**template_data)

@celery_app.task(bind=True, max_retries=3)
def send_verification_email_task(self, to_email: str, user_name: str, verification_token: str):
    """
    Send email verification email to user
    """
    try:
        # Construct verification URL
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}&email={to_email}"
        
        # Send verification email using template
        result = send_email(
            to_email=to_email,
            subject="Verify Your Email Address - RemoteHive",
            template_name="email_verification",
            template_data={
                'user_name': user_name,
                'verification_url': verification_url,
                'expiry_hours': 1,
                'support_email': settings.SUPPORT_EMAIL or 'support@remotehive.com'
            }
        )
        
        if result['success']:
            logger.info(f"Verification email sent successfully to {to_email}")
            return {
                "to_email": to_email,
                "success": True,
                "message": f"Verification email sent to {to_email}"
            }
        else:
            raise Exception(result['message'])
        
    except Exception as e:
        logger.error(f"Failed to send verification email to {to_email}: {str(e)}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying verification email task. Attempt {self.request.retries + 1}")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            "to_email": to_email,
            "success": False,
            "message": f"Failed to send verification email: {str(e)}"
        }

@celery_app.task(bind=True)
def send_welcome_email(self, user_id: int):
    """Send welcome email to new user."""
    try:
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as db:
            user_service = UserService(db)
            user = user_service.get_user_by_id(str(user_id))
            
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Send welcome email using template
            result = send_email(
                to_email=user.email,
                subject="Welcome to RemoteHive!",
                template_name="welcome",
                template_data={
                    'user_name': user.first_name or user.email,
                    'base_url': settings.FRONTEND_URL
                }
            )
            
            success = result['success']
            
            return {
                "user_id": user_id,
                "email": user.email,
                "success": success
            }
    
    except Exception as e:
        logger.error(f"Error sending welcome email to user {user_id}: {str(e)}")
        raise self.retry(countdown=300, max_retries=3)

@celery_app.task(bind=True)
def send_job_alert_email(self, user_id: int, job_ids: List[int]):
    """Send job alert email to user."""
    try:
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as db:
            user_service = UserService(db)
            user = user_service.get_user_by_id(str(user_id))
            
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Get job posts by IDs
            jobs = []
            for job_id in job_ids:
                job = JobPostService.get_job_post_by_id(db, job_id)
                if job:
                    jobs.append(job)
            
            if not jobs:
                logger.warning(f"No jobs found for IDs: {job_ids}")
                return {"user_id": user_id, "success": False, "reason": "No jobs found"}
            
            # Convert job objects to dict for template rendering
            jobs_data = [{
                'id': job.id,
                'title': job.title,
                'company_name': job.company_name,
                'location_city': job.location_city,
                'location_state': job.location_state,
                'job_type': job.job_type,
                'description': job.description[:200] + '...' if len(job.description) > 200 else job.description
            } for job in jobs]
            
            template = Template(JOB_ALERT_TEMPLATE)
            html_content = template.render(
                user_name=user.first_name or user.email,
                job_count=len(jobs),
                jobs=jobs_data,
                base_url=settings.FRONTEND_URL
            )
            
            success = send_email(
                to_email=user.email,
                subject=f"New Job Opportunities - {len(jobs)} matches found!",
                html_content=html_content
            )
            
            return {
                "user_id": user_id,
                "email": user.email,
                "job_count": len(jobs),
                "success": success
            }
    
    except Exception as e:
        logger.error(f"Error sending job alert email to user {user_id}: {str(e)}")
        raise self.retry(countdown=300, max_retries=3)

@celery_app.task(bind=True)
def send_application_status_email(self, application_id: int):
    """Send application status update email."""
    try:
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as db:
            # Get application with related user and job data
            application_service = JobApplicationService()
            application = application_service.get_application_by_id(db, application_id)
            
            if not application:
                raise ValueError(f"Application {application_id} not found")
            
            # Get related user and job data
            user_service = UserService(db)
            user = user_service.get_user_by_id(str(application.user_id))
            
            job = JobPostService.get_job_post_by_id(db, application.job_post_id)
            
            if not user or not job:
                raise ValueError(f"Missing user or job data for application {application_id}")
            
            template = Template(APPLICATION_STATUS_TEMPLATE)
            html_content = template.render(
                user_name=user.first_name or user.email,
                job_title=job.title,
                company_name=job.company_name,
                status=application.status,
                message=application.employer_notes,
                application_id=application.id,
                base_url=settings.FRONTEND_URL
            )
            
            success = send_email(
                to_email=user.email,
                subject=f"Application Status Update - {job.title}",
                html_content=html_content
            )
            
            return {
                "application_id": application_id,
                "user_email": user.email,
                "job_title": job.title,
                "status": application.status,
                "success": success
            }
    
    except Exception as e:
        logger.error(f"Error sending application status email for application {application_id}: {str(e)}")
        raise self.retry(countdown=300, max_retries=3)

@celery_app.task(bind=True)
def send_bulk_email(self, user_ids: List[int], subject: str, html_content: str):
    """Send bulk email to multiple users."""
    try:
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as db:
            user_service = UserService(db)
            users = []
            
            # Get users by IDs
            for user_id in user_ids:
                user = user_service.get_user_by_id(str(user_id))
                if user:
                    users.append(user)
            
            results = []
            for user in users:
                try:
                    success = send_email(
                        to_email=user.email,
                        subject=subject,
                        html_content=html_content
                    )
                    results.append({
                        "user_id": user.id,
                        "email": user.email,
                        "success": success
                    })
                except Exception as e:
                    logger.error(f"Failed to send email to user {user.id}: {str(e)}")
                    results.append({
                        "user_id": user.id,
                        "email": user.email,
                        "success": False,
                        "error": str(e)
                    })
            
            successful_sends = sum(1 for r in results if r["success"])
            
            return {
                "total_users": len(users),
                "successful_sends": successful_sends,
                "failed_sends": len(users) - successful_sends,
                "results": results
            }
    
    except Exception as e:
        logger.error(f"Error in bulk email send: {str(e)}")
        raise self.retry(countdown=300, max_retries=3)

@celery_app.task(bind=True, max_retries=3)
def send_password_reset_email_task(self, to_email: str, user_name: str, reset_token: str):
    """
    Send password reset email task (fallback for Gmail API)
    """
    try:
        # Simple password reset email template
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Password Reset - RemoteHive</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
                <h2 style="color: #2563eb; text-align: center;">🏢 RemoteHive</h2>
                <h3 style="color: #333;">Password Reset Request</h3>
                
                <p>Hello <strong>{user_name}</strong>,</p>
                
                <p>We received a request to reset your password. Your password reset token is:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <code style="background-color: #e9ecef; padding: 15px; font-size: 18px; border-radius: 5px; display: inline-block;">{reset_token}</code>
                </div>
                
                <p>This token will expire in 1 hour for security reasons.</p>
                
                <p>If you didn't request this password reset, please ignore this email.</p>
                
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #dee2e6;">
                <p style="font-size: 12px; color: #6c757d; text-align: center;">
                    This email was sent by RemoteHive. Please do not reply to this email.
                </p>
            </div>
        </body>
        </html>
        """
        
        success = send_email(
            to_email=to_email,
            subject="Password Reset - RemoteHive",
            html_content=html_content
        )
        
        if success:
            logger.info(f"Password reset email sent successfully to {to_email}")
            return {
                "success": True,
                "message": f"Password reset email sent to {to_email}"
            }
        else:
            raise Exception("Failed to send email")
        
    except Exception as e:
        logger.error(f"Failed to send password reset email to {to_email}: {str(e)}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying password reset email task. Attempt {self.request.retries + 1}")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            "success": False,
            "message": f"Failed to send password reset email: {str(e)}"
        }

@celery_app.task(bind=True, max_retries=3)
def send_support_email_task(self, from_email: str, from_name: str, subject: str, message: str, user_id: str = None):
    """
    Send support request email to support team
    """
    try:
        # Send support email using template
        result = send_email(
            to_email=settings.SUPPORT_EMAIL,
            subject=f"Support Request: {subject}",
            template_name="support_request",
            template_data={
                'from_name': from_name,
                'from_email': from_email,
                'subject': subject,
                'message': message,
                'user_id': user_id or 'Guest',
                'support_email': settings.SUPPORT_EMAIL
            },
            reply_to=from_email
        )
        
        if result['success']:
            logger.info(f"Support email sent successfully from {from_email}")
            return {
                "success": True,
                "message": f"Support request sent from {from_email}"
            }
        else:
            raise Exception(result['message'])
        
    except Exception as e:
        logger.error(f"Failed to send support email from {from_email}: {str(e)}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying support email task. Attempt {self.request.retries + 1}")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            "success": False,
            "message": f"Failed to send support email: {str(e)}"
        }