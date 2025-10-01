"""Email Service for RemoteHive CRM"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
from jinja2 import Template
from backend.core.config import settings

class EmailService:
    """Service for sending emails in the CRM system"""
    
    def __init__(self):
        self.smtp_server = getattr(settings, 'SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_username = getattr(settings, 'SMTP_USERNAME', '')
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', '')
        self.from_email = getattr(settings, 'FROM_EMAIL', self.smtp_username)
        self.from_name = getattr(settings, 'FROM_NAME', 'RemoteHive CRM')
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send an email"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            if bcc:
                msg['Bcc'] = ', '.join(bcc)
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    self._add_attachment(msg, attachment)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                
                recipients = [to_email]
                if cc:
                    recipients.extend(cc)
                if bcc:
                    recipients.extend(bcc)
                
                server.send_message(msg, to_addrs=recipients)
            
            return True
        except Exception as e:
            print(f"Failed to send email: {str(e)}")
            return False
    
    def _add_attachment(self, msg: MIMEMultipart, attachment: Dict[str, Any]):
        """Add attachment to email message"""
        try:
            with open(attachment['path'], 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {attachment.get("filename", "attachment")}'
            )
            msg.attach(part)
        except Exception as e:
            print(f"Failed to add attachment: {str(e)}")
    
    async def send_lead_assignment_notification(
        self,
        lead_data: Dict[str, Any],
        assigned_to_email: str,
        assigned_by_name: str
    ) -> bool:
        """Send notification when a lead is assigned"""
        subject = f"New Lead Assigned: {lead_data['first_name']} {lead_data['last_name']}"
        
        body = f"""
Hi there,

A new lead has been assigned to you:

Lead Details:
- Name: {lead_data['first_name']} {lead_data['last_name']}
- Email: {lead_data['email']}
- Company: {lead_data.get('company', 'N/A')}
- Phone: {lead_data.get('phone', 'N/A')}
- Category: {lead_data['lead_category']}
- Source: {lead_data['lead_source']}
- Score: {lead_data.get('score', 'N/A')}

Assigned by: {assigned_by_name}
Assigned at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

Please log into the CRM system to view full details and take action.

Best regards,
RemoteHive CRM System
"""
        
        html_body = f"""
<html>
<body>
    <h2>New Lead Assigned</h2>
    <p>Hi there,</p>
    <p>A new lead has been assigned to you:</p>
    
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">
        <tr><td><strong>Name</strong></td><td>{lead_data['first_name']} {lead_data['last_name']}</td></tr>
        <tr><td><strong>Email</strong></td><td>{lead_data['email']}</td></tr>
        <tr><td><strong>Company</strong></td><td>{lead_data.get('company', 'N/A')}</td></tr>
        <tr><td><strong>Phone</strong></td><td>{lead_data.get('phone', 'N/A')}</td></tr>
        <tr><td><strong>Category</strong></td><td>{lead_data['lead_category']}</td></tr>
        <tr><td><strong>Source</strong></td><td>{lead_data['lead_source']}</td></tr>
        <tr><td><strong>Score</strong></td><td>{lead_data.get('score', 'N/A')}</td></tr>
    </table>
    
    <p><strong>Assigned by:</strong> {assigned_by_name}<br>
    <strong>Assigned at:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    
    <p>Please log into the CRM system to view full details and take action.</p>
    
    <p>Best regards,<br>RemoteHive CRM System</p>
</body>
</html>
"""
        
        return await self.send_email(
            to_email=assigned_to_email,
            subject=subject,
            body=body,
            html_body=html_body
        )
    
    async def send_follow_up_reminder(
        self,
        lead_data: Dict[str, Any],
        assigned_to_email: str,
        task_details: Dict[str, Any]
    ) -> bool:
        """Send follow-up reminder for a lead"""
        subject = f"Follow-up Reminder: {lead_data['first_name']} {lead_data['last_name']}"
        
        body = f"""
Hi there,

This is a reminder for your follow-up task:

Lead: {lead_data['first_name']} {lead_data['last_name']} ({lead_data['email']})
Company: {lead_data.get('company', 'N/A')}

Task: {task_details['title']}
Due Date: {task_details['due_date']}
Priority: {task_details.get('priority', 'Medium')}

Description:
{task_details.get('description', 'No description provided')}

Please complete this task and update the lead status accordingly.

Best regards,
RemoteHive CRM System
"""
        
        return await self.send_email(
            to_email=assigned_to_email,
            subject=subject,
            body=body
        )
    
    async def send_lead_status_change_notification(
        self,
        lead_data: Dict[str, Any],
        old_status: str,
        new_status: str,
        changed_by_name: str,
        notify_emails: List[str]
    ) -> bool:
        """Send notification when lead status changes"""
        subject = f"Lead Status Updated: {lead_data['first_name']} {lead_data['last_name']}"
        
        body = f"""
Hi there,

A lead status has been updated:

Lead: {lead_data['first_name']} {lead_data['last_name']} ({lead_data['email']})
Company: {lead_data.get('company', 'N/A')}

Status Change: {old_status} → {new_status}
Changed by: {changed_by_name}
Changed at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

Please review the lead details in the CRM system for more information.

Best regards,
RemoteHive CRM System
"""
        
        success = True
        for email in notify_emails:
            result = await self.send_email(
                to_email=email,
                subject=subject,
                body=body
            )
            if not result:
                success = False
        
        return success
    
    async def send_new_lead_notification(
        self,
        lead_data: Dict[str, Any],
        notify_emails: List[str]
    ) -> bool:
        """Send notification when a new lead is created"""
        subject = f"New Lead Created: {lead_data['first_name']} {lead_data['last_name']}"
        
        body = f"""
Hi there,

A new lead has been created in the system:

Lead Details:
- Name: {lead_data['first_name']} {lead_data['last_name']}
- Email: {lead_data['email']}
- Company: {lead_data.get('company', 'N/A')}
- Phone: {lead_data.get('phone', 'N/A')}
- Category: {lead_data['lead_category']}
- Source: {lead_data['lead_source']}
- Score: {lead_data.get('score', 'N/A')}

Created at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

Please review and assign this lead to the appropriate team member.

Best regards,
RemoteHive CRM System
"""
        
        html_body = f"""
<html>
<body>
    <h2>New Lead Created</h2>
    <p>Hi there,</p>
    <p>A new lead has been created in the system:</p>
    
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">
        <tr><td><strong>Name</strong></td><td>{lead_data['first_name']} {lead_data['last_name']}</td></tr>
        <tr><td><strong>Email</strong></td><td>{lead_data['email']}</td></tr>
        <tr><td><strong>Company</strong></td><td>{lead_data.get('company', 'N/A')}</td></tr>
        <tr><td><strong>Phone</strong></td><td>{lead_data.get('phone', 'N/A')}</td></tr>
        <tr><td><strong>Category</strong></td><td>{lead_data['lead_category']}</td></tr>
        <tr><td><strong>Source</strong></td><td>{lead_data['lead_source']}</td></tr>
        <tr><td><strong>Score</strong></td><td>{lead_data.get('score', 'N/A')}</td></tr>
    </table>
    
    <p><strong>Created at:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
    
    <p>Please review and assign this lead to the appropriate team member.</p>
    
    <p>Best regards,<br>RemoteHive CRM System</p>
</body>
</html>
"""
        
        success = True
        for email in notify_emails:
            result = await self.send_email(
                to_email=email,
                subject=subject,
                body=body,
                html_body=html_body
            )
            if not result:
                success = False
        
        return success
    
    async def send_lead_conversion_notification(
        self,
        lead_data: Dict[str, Any],
        conversion_details: Dict[str, Any],
        notify_emails: List[str]
    ) -> bool:
        """Send notification when a lead converts"""
        subject = f"🎉 Lead Converted: {lead_data['first_name']} {lead_data['last_name']}"
        
        body = f"""
Great news!

A lead has successfully converted:

Lead: {lead_data['first_name']} {lead_data['last_name']} ({lead_data['email']})
Company: {lead_data.get('company', 'N/A')}
Original Source: {lead_data['lead_source']}
Score: {lead_data.get('score', 'N/A')}

Conversion Details:
- Converted at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
- Value: {conversion_details.get('value', 'N/A')}
- Notes: {conversion_details.get('notes', 'No additional notes')}

Congratulations to the team!

Best regards,
RemoteHive CRM System
"""
        
        success = True
        for email in notify_emails:
            result = await self.send_email(
                to_email=email,
                subject=subject,
                body=body
            )
            if not result:
                success = False
        
        return success
    
    async def send_bulk_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send email to multiple recipients"""
        results = {
            "total": len(recipients),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        for email in recipients:
            try:
                success = await self.send_email(
                    to_email=email,
                    subject=subject,
                    body=body,
                    html_body=html_body
                )
                if success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Failed to send to {email}")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Error sending to {email}: {str(e)}")
        
        return results
    
    def get_email_templates(self) -> Dict[str, str]:
        """Get available email templates"""
        return {
            "welcome": "Welcome to RemoteHive",
            "follow_up": "Follow-up on your inquiry",
            "proposal": "Proposal for your project",
            "meeting_request": "Meeting request",
            "thank_you": "Thank you for your interest",
            "nurture_sequence_1": "Industry insights and tips",
            "nurture_sequence_2": "Case studies and success stories",
            "nurture_sequence_3": "Special offer for qualified leads"
        }
    
    def validate_email_config(self) -> Dict[str, Any]:
        """Validate email configuration"""
        config_status = {
            "smtp_server": bool(self.smtp_server),
            "smtp_port": bool(self.smtp_port),
            "smtp_username": bool(self.smtp_username),
            "smtp_password": bool(self.smtp_password),
            "from_email": bool(self.from_email)
        }
        
        all_configured = all(config_status.values())
        
        return {
            "configured": all_configured,
            "details": config_status,
            "missing": [k for k, v in config_status.items() if not v]
        }