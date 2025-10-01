import requests
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class SlackService:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")
    
    def send_contact_notification(self, submission_data: Dict[str, Any]) -> bool:
        """
        Send a notification to Slack when a new contact form is submitted
        """
        try:
            # Format the message for Slack
            message = self._format_contact_message(submission_data)
            
            # Send to Slack
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Slack notification sent successfully for submission ID: {submission_data.get('id')}")
                return True
            else:
                logger.error(f"Failed to send Slack notification. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Slack notification: {str(e)}")
            return False
    
    def _format_contact_message(self, submission_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format the contact submission data into a Slack message
        """
        # Determine priority emoji
        priority_emoji = {
            'low': '🟢',
            'medium': '🟡', 
            'high': '🟠',
            'urgent': '🔴'
        }.get(submission_data.get('priority', 'medium'), '🟡')
        
        # Determine inquiry type emoji
        inquiry_emoji = {
            'general': '💬',
            'support': '🛠️',
            'business': '💼',
            'press': '📰'
        }.get(submission_data.get('inquiry_type', 'general'), '💬')
        
        # Format timestamp
        created_at = submission_data.get('created_at', datetime.utcnow().isoformat())
        if isinstance(created_at, str):
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            except:
                formatted_time = created_at
        else:
            formatted_time = str(created_at)
        
        # Build the message
        message = {
            "text": f"🆕 New Contact Form Submission - {submission_data.get('subject', 'No Subject')}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🆕 New Contact Form Submission"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Name:*\n{submission_data.get('name', 'N/A')}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Email:*\n{submission_data.get('email', 'N/A')}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Subject:*\n{submission_data.get('subject', 'N/A')}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Inquiry Type:*\n{inquiry_emoji} {submission_data.get('inquiry_type', 'general').title()}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Priority:*\n{priority_emoji} {submission_data.get('priority', 'medium').title()}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Submitted:*\n{formatted_time}"
                        }
                    ]
                }
            ]
        }
        
        # Add phone if provided
        if submission_data.get('phone'):
            message["blocks"][1]["fields"].append({
                "type": "mrkdwn",
                "text": f"*Phone:*\n{submission_data.get('phone')}"
            })
        
        # Add company if provided
        if submission_data.get('company_name'):
            message["blocks"][1]["fields"].append({
                "type": "mrkdwn",
                "text": f"*Company:*\n{submission_data.get('company_name')}"
            })
        
        # Add message content
        message_text = submission_data.get('message', '')
        if len(message_text) > 500:
            message_text = message_text[:500] + "..."
        
        message["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Message:*\n```{message_text}```"
            }
        })
        
        # Add submission ID and admin link
        if submission_data.get('id'):
            admin_url = os.getenv('ADMIN_PANEL_URL', 'http://localhost:3000')
            admin_link = f"{admin_url}/admin/contact-management"
            
            message["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Submission ID:* {submission_data.get('id')}\n*Status:* {submission_data.get('status', 'new').title()}"
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View in Admin Panel",
                        "emoji": True
                    },
                    "url": admin_link,
                    "action_id": "view_submission"
                }
            })
        
        return message
    
    def send_test_message(self) -> bool:
        """
        Send a test message to verify Slack integration
        """
        if not self.webhook_url:
            logger.error("No Slack webhook URL configured")
            return False
            
        test_message = {
            "text": "🧪 Slack Integration Test",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "✅ Slack webhook integration is working correctly!\n\nContact form notifications will now be sent to this channel."
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Test sent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} from RemoteHive Admin Panel"
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=test_message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Slack test message sent successfully")
                return True
            else:
                logger.error(f"Failed to send Slack test message. Status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending Slack test message: {str(e)}")
            return False
    
    def send_custom_message(self, title: str, content: str, message_type: str = "custom") -> bool:
        """
        Send a custom message to Slack
        """
        if not self.webhook_url:
            logger.error("No Slack webhook URL configured")
            return False
        
        # Determine emoji based on message type
        type_emoji = {
            'system': '⚙️',
            'alert': '🚨',
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌',
            'custom': '📝'
        }.get(message_type, '📝')
        
        message = {
            "text": f"{type_emoji} {title}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{type_emoji} {title}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": content
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Sent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Type: {message_type.title()}"
                        }
                    ]
                }
            ]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Custom Slack message sent successfully: {title}")
                return True
            else:
                logger.error(f"Failed to send custom Slack message. Status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending custom Slack message: {str(e)}")
            return False
    
    def update_webhook_url(self, webhook_url: str) -> None:
        """
        Update the webhook URL for this service instance
        """
        self.webhook_url = webhook_url
        logger.info("Slack webhook URL updated")
    
    def get_webhook_url(self) -> str:
        """
        Get the current webhook URL
        """
        return self.webhook_url or ""