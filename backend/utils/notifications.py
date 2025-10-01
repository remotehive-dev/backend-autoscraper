"""Notification service for RemoteHive application"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for handling various types of notifications"""
    
    def __init__(self):
        self.logger = logger
    
    def send_scraping_notification(self, result: Dict[str, Any], source: str) -> bool:
        """Send notification about scraping results"""
        try:
            # Log the scraping result
            jobs_count = result.get('jobs_stored', 0)
            status = result.get('status', 'unknown')
            
            self.logger.info(
                f"Scraping notification: {source} - Status: {status}, Jobs: {jobs_count}"
            )
            
            # In a real implementation, this could send emails, Slack messages, etc.
            # For now, we'll just log the notification
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send scraping notification: {e}")
            return False
    
    def send_error_notification(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Send notification about errors"""
        try:
            self.logger.error(
                f"Error notification: {type(error).__name__}: {str(error)}", 
                extra=context
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send error notification: {e}")
            return False
    
    def send_task_completion_notification(self, task_name: str, result: Dict[str, Any]) -> bool:
        """Send notification about task completion"""
        try:
            self.logger.info(
                f"Task completion notification: {task_name} completed", 
                extra=result
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send task completion notification: {e}")
            return False
    
    def send_health_check_notification(self, service: str, status: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Send notification about health check results"""
        try:
            self.logger.info(
                f"Health check notification: {service} - Status: {status}",
                extra=details or {}
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send health check notification: {e}")
            return False

# Create a singleton instance
notification_service = NotificationService()