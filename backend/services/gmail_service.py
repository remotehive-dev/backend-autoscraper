import base64
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from loguru import logger
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import smtplib
from email.mime.text import MIMEText as SMTPMIMEText
from email.mime.multipart import MIMEMultipart as SMTPMIMEMultipart
from backend.core.config import settings
from backend.models.mongodb_models import User
from beanie import PydanticObjectId

class GmailService:
    """Gmail API service for sending emails"""
    
    def __init__(self):
        self.settings = settings
        self.service = None
        self.template_env = Environment(
            loader=FileSystemLoader('backend/templates/email')
        )
        # Authentication will be done when needed
        
    async def authenticate(self, user_id: Optional[str] = None) -> bool:
        """Authenticate with Gmail API using OAuth2 or fallback to SMTP"""
        try:
            # Try to use OAuth2 credentials from user if user_id provided
            if user_id:
                user = await User.get(PydanticObjectId(user_id))
                if user and user.oauth_access_token and user.oauth_provider == "google":
                    # Create credentials from user's OAuth tokens
                    token_info = {
                        'token': user.oauth_access_token,
                        'refresh_token': user.oauth_refresh_token,
                        'token_uri': 'https://oauth2.googleapis.com/token',
                        'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
                        'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
                        'scopes': settings.GOOGLE_OAUTH_SCOPES
                    }
                    
                    creds = Credentials.from_authorized_user_info(token_info)
                    
                    # Refresh token if expired
                    if creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                        # Update user's tokens in database
                        user.oauth_access_token = creds.token
                        if creds.refresh_token:
                            user.oauth_refresh_token = creds.refresh_token
                        user.oauth_token_expires_at = creds.expiry
                        await user.save()
                    
                    self.service = build('gmail', 'v1', credentials=creds)
                    logger.info(f"Gmail API authentication successful with user OAuth2 for user {user_id}")
                    return True
            
            # Try to use OAuth2 credentials from settings if available
            if self.settings.GOOGLE_OAUTH_CLIENT_ID and self.settings.GOOGLE_OAUTH_CLIENT_SECRET:
                try:
                    # Create credentials from OAuth settings
                    token_info = {
                        'client_id': self.settings.GOOGLE_OAUTH_CLIENT_ID,
                        'client_secret': self.settings.GOOGLE_OAUTH_CLIENT_SECRET,
                        'token_uri': 'https://oauth2.googleapis.com/token',
                        'scopes': self.settings.GMAIL_SCOPES
                    }
                    
                    # Try to load existing token file
                    if os.path.exists(self.settings.GMAIL_TOKEN_FILE):
                        creds = Credentials.from_authorized_user_file(self.settings.GMAIL_TOKEN_FILE, self.settings.GMAIL_SCOPES)
                        if creds and creds.valid:
                            self.service = build('gmail', 'v1', credentials=creds)
                            logger.info("Gmail API authentication successful with OAuth2 file")
                            return True
                        elif creds and creds.expired and creds.refresh_token:
                            # Try to refresh the token
                            creds.refresh(Request())
                            # Save refreshed credentials
                            with open(self.settings.GMAIL_TOKEN_FILE, 'w') as token:
                                token.write(creds.to_json())
                            self.service = build('gmail', 'v1', credentials=creds)
                            logger.info("Gmail API authentication successful with refreshed OAuth2 token")
                            return True
                    
                    # If no valid token file, we need to create one through OAuth flow
                    logger.warning("Gmail OAuth token not found or invalid. Please run OAuth setup.")
                    
                except Exception as e:
                    logger.error(f"OAuth2 authentication failed: {str(e)}")
            
            # Try service account if available
            if self.settings.GMAIL_SERVICE_ACCOUNT_FILE and os.path.exists(self.settings.GMAIL_SERVICE_ACCOUNT_FILE):
                creds = ServiceAccountCredentials.from_service_account_file(
                    self.settings.GMAIL_SERVICE_ACCOUNT_FILE, 
                    scopes=self.settings.GMAIL_SCOPES
                )
                if self.settings.GMAIL_DELEGATED_USER:
                    creds = creds.with_subject(self.settings.GMAIL_DELEGATED_USER)
                
                self.service = build('gmail', 'v1', credentials=creds)
                logger.info("Gmail API authentication successful with service account")
                return True
            
            # Fallback to SMTP if Gmail API is not available
            logger.warning("Gmail API credentials not available, will use SMTP fallback")
            return True
            
        except Exception as e:
            logger.error(f"Gmail authentication failed: {str(e)}")
            return False
    
    def create_message(self, to: str, subject: str, body: str, 
                      from_email: Optional[str] = None, 
                      attachments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, str]:
        """Create a message for an email"""
        try:
            message = MIMEMultipart()
            message['to'] = to
            message['from'] = from_email or settings.EMAIL_FROM
            message['subject'] = subject
            
            # Add body
            message.attach(MIMEText(body, 'html'))
            
            # Add attachments if any
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    message.attach(part)
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            return {'raw': raw_message}
            
        except Exception as e:
            logger.error(f"Error creating email message: {str(e)}")
            raise
    
    async def send_email(self, to_email: str, subject: str, html_content: str = None, 
                        text_content: str = None, from_email: Optional[str] = None,
                        attachments: Optional[List[Dict[str, Any]]] = None,
                        user_id: Optional[str] = None) -> bool:
        """Send an email using Gmail API or SMTP fallback"""
        try:
            if not await self.authenticate(user_id):
                return False
            
            # Try Gmail API first if service is available
            if self.service:
                try:
                    message = self.create_message(to_email, subject, html_content or text_content, from_email, attachments)
                    result = self.service.users().messages().send(
                        userId='me', body=message
                    ).execute()
                    logger.info(f"Email sent via Gmail API to {to_email}. Message ID: {result['id']}")
                    return True
                except HttpError as error:
                    logger.error(f"Gmail API error: {error}")
                    # Fall through to SMTP
            
            # SMTP fallback
            return await self._send_via_smtp(to_email, subject, html_content, text_content, from_email)
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    async def _send_via_smtp(self, to_email: str, subject: str, html_content: str = None, 
                           text_content: str = None, from_email: Optional[str] = None) -> bool:
        """Send email via SMTP as fallback"""
        try:
            from_email = from_email or self.settings.EMAIL_FROM
            
            # Create message
            msg = SMTPMIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = to_email
            
            # Add text content
            if text_content:
                text_part = SMTPMIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            # Add HTML content
            if html_content:
                html_part = SMTPMIMEText(html_content, 'html')
                msg.attach(html_part)
            
            # Send via SMTP
            with smtplib.SMTP(self.settings.SMTP_SERVER, self.settings.SMTP_PORT) as server:
                if self.settings.EMAIL_USE_TLS:
                    server.starttls()
                if self.settings.EMAIL_USERNAME and self.settings.EMAIL_PASSWORD:
                    server.login(self.settings.EMAIL_USERNAME, self.settings.EMAIL_PASSWORD)
                
                server.send_message(msg)
                logger.info(f"Email sent via SMTP to {to_email}")
                return True
                
        except Exception as e:
            logger.error(f"SMTP email sending failed: {str(e)}")
            return False
    
    async def send_template_email(self, to: str, subject: str, template_name: str, 
                                 template_data: Dict[str, Any],
                                 from_email: Optional[str] = None) -> bool:
        """Send an email using a template"""
        try:
            template = self.template_env.get_template(f"{template_name}.html")
            body = template.render(**template_data)
            
            return await self.send_email(to, subject, body, from_email)
            
        except Exception as e:
            logger.error(f"Error sending template email: {str(e)}")
            return False
    
    async def send_password_reset_email(self, to_email: str, reset_token: str, user_type: str = "user") -> bool:
        """
        Send password reset email with token using HTML template
        
        Args:
            to_email: Recipient email address
            reset_token: Password reset token
            user_type: Type of user (for customization)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            subject = "Password Reset - RemoteHive"
            
            # Load and render HTML template
            html_content = await self._load_template(
                "password_reset_email.html",
                {
                    "email": to_email,
                    "reset_token": reset_token,
                    "user_type": user_type
                }
            )
            
            # Create plain text version
            text_content = f"""
            Password Reset Request - RemoteHive
            
            Hello,
            
            We received a request to reset your password for your RemoteHive account associated with {to_email}.
            
            Your password reset token is: {reset_token}
            
            This token will expire in 1 hour. Please use it to reset your password.
            
            If you didn't request this password reset, please ignore this email.
            
            For security reasons, we recommend:
            - Using a strong, unique password
            - Not sharing your password with anyone
            - Enabling two-factor authentication if available
            
            ---
            This email was sent from RemoteHive. If you have any questions, please contact our support team.
            © 2024 RemoteHive. All rights reserved.
            """
            
            return await self.send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            return False
    
    async def _load_template(self, template_name: str, template_data: dict) -> str:
        """
        Load and render HTML template
        
        Args:
            template_name: Name of the template file
            template_data: Data to render in the template
            
        Returns:
            str: Rendered HTML content
        """
        try:
            # Try to load template from file if template environment is available
            if hasattr(self, 'template_env') and self.template_env:
                template = self.template_env.get_template(template_name)
                return template.render(**template_data)
            else:
                # Use fallback template
                return self._get_fallback_html_template(template_data)
                
        except Exception as e:
            logger.warning(f"Template loading failed, using fallback: {str(e)}")
            return self._get_fallback_html_template(template_data)
    
    def _get_fallback_html_template(self, vars_dict: dict) -> str:
        """Fallback HTML template if file template is not available"""
        email = vars_dict.get('email', 'User')
        reset_token = vars_dict.get('reset_token', '')
        user_type = vars_dict.get('user_type', 'user')
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 30px; border-radius: 10px;">
                <h2 style="color: #2563eb; text-align: center;">🏢 RemoteHive</h2>
                <h3 style="color: #333;">Password Reset Request</h3>
                
                <p>Hello <strong>{email}</strong>,</p>
                
                <p>We received a request to reset your password for your RemoteHive account.</p>
                
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
    
    def _get_fallback_text_template(self, vars_dict: dict) -> str:
        """Fallback text template if file template is not available"""
        return f"""
        RemoteHive - Password Reset Request
        
        Hello {vars_dict['user_name']},
        
        We received a request to reset your password. Please use the following link:
        {vars_dict['reset_url']}
        
        Reset Code: {vars_dict['reset_token']}
        
        This link will expire in {vars_dict['expiry_hours']} hours.
        
        Security Details:
        Request Time: {vars_dict['request_time']}
        IP Address: {vars_dict['ip_address']}
        
        If you didn't request this password reset, please ignore this email.
        
        ---
        This email was sent by RemoteHive. Please do not reply to this email.
        """
    
    async def send_welcome_email(self, to: str, user_name: str, user_role: str) -> bool:
        """Send welcome email to new users"""
        try:
            template_data = {
                'user_name': user_name,
                'user_role': user_role,
                'login_url': f"{settings.FRONTEND_URL}/login",
                'support_email': settings.SUPPORT_EMAIL,
                'company_name': 'RemoteHive'
            }
            
            subject = f"Welcome to RemoteHive, {user_name}!"
            
            return await self.send_template_email(
                to=to,
                subject=subject,
                template_name="welcome",
                template_data=template_data
            )
            
        except Exception as e:
            logger.error(f"Error sending welcome email: {str(e)}")
            return False
    
    async def test_connection(self) -> bool:
        """Test Gmail API connection or SMTP fallback"""
        try:
            if not await self.authenticate():
                return False
            
            # Test Gmail API if available
            if self.service:
                try:
                    profile = self.service.users().getProfile(userId='me').execute()
                    logger.info(f"Gmail API connection test successful. Email: {profile.get('emailAddress')}")
                    return True
                except HttpError as error:
                    logger.error(f"Gmail API connection test failed: {error}")
                    # Fall through to SMTP test
            
            # Test SMTP connection
            try:
                with smtplib.SMTP(self.settings.SMTP_SERVER, self.settings.SMTP_PORT) as server:
                    if self.settings.EMAIL_USE_TLS:
                        server.starttls()
                    if self.settings.EMAIL_USERNAME and self.settings.EMAIL_PASSWORD:
                        server.login(self.settings.EMAIL_USERNAME, self.settings.EMAIL_PASSWORD)
                    logger.info("SMTP connection test successful")
                    return True
            except Exception as smtp_error:
                logger.error(f"SMTP connection test failed: {smtp_error}")
                return False
            
        except Exception as e:
            logger.error(f"Connection test error: {str(e)}")
            return False

# Global instance
gmail_service = GmailService()