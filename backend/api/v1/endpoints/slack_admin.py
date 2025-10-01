from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
import json
import os
from datetime import datetime

from backend.core.database import get_db
from backend.core.auth import get_admin
from backend.schemas.user import User
from backend.services.slack_service import SlackService
from backend.core.config import settings

router = APIRouter()

# Pydantic models for request/response
class SlackNotificationSettings(BaseModel):
    contact_forms: bool = True
    user_registrations: bool = False
    job_applications: bool = False
    system_alerts: bool = True
    payment_notifications: bool = False

class SlackConfigRequest(BaseModel):
    webhook_url: Optional[str] = None
    channel_name: Optional[str] = "#general"
    bot_name: Optional[str] = "RemoteHive Bot"
    enabled: bool = False
    notifications: SlackNotificationSettings = SlackNotificationSettings()

class SlackConfigResponse(BaseModel):
    webhook_url: str
    channel_name: str
    bot_name: str
    enabled: bool
    notifications: SlackNotificationSettings
    last_updated: Optional[datetime] = None

class SlackMessageRequest(BaseModel):
    type: str  # 'contact_form', 'system', 'test', 'manual'
    title: str
    content: str
    submission_id: Optional[str] = None

class SlackMessageResponse(BaseModel):
    id: str
    type: str
    title: str
    content: str
    timestamp: datetime
    status: str  # 'sent', 'failed', 'pending'
    submission_id: Optional[str] = None
    error_message: Optional[str] = None

# In-memory storage for demo purposes (in production, use database)
slack_config_storage = {
    "webhook_url": os.getenv("SLACK_WEBHOOK_URL", ""),
    "channel_name": "#contact-forms",
    "bot_name": "RemoteHive Bot",
    "enabled": bool(os.getenv("SLACK_WEBHOOK_URL")),
    "notifications": {
        "contact_forms": True,
        "user_registrations": False,
        "job_applications": False,
        "system_alerts": True,
        "payment_notifications": False
    },
    "last_updated": datetime.utcnow()
}

slack_messages_storage = []

@router.get("/config", response_model=SlackConfigResponse)
async def get_slack_config(
    current_admin: User = Depends(get_admin)
):
    """
    Get current Slack configuration
    """
    try:
        # In production, fetch from database
        config = slack_config_storage.copy()
        
        # Don't expose the full webhook URL for security
        if config["webhook_url"]:
            webhook_url = config["webhook_url"]
            if len(webhook_url) > 20:
                config["webhook_url"] = webhook_url[:20] + "..." + webhook_url[-10:]
        
        return SlackConfigResponse(**config)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Slack configuration: {str(e)}"
        )

@router.post("/config", response_model=SlackConfigResponse)
async def save_slack_config(
    config: SlackConfigRequest,
    current_admin: User = Depends(get_admin)
):
    """
    Save Slack configuration
    """
    try:
        # Validate webhook URL if provided
        if config.webhook_url and not config.webhook_url.startswith("https://hooks.slack.com/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Slack webhook URL format"
            )
        
        # Update configuration
        slack_config_storage.update({
            "webhook_url": config.webhook_url or slack_config_storage["webhook_url"],
            "channel_name": config.channel_name,
            "bot_name": config.bot_name,
            "enabled": config.enabled,
            "notifications": config.notifications.dict(),
            "last_updated": datetime.utcnow()
        })
        
        # In production, save to database
        # Also update environment variables or configuration file
        
        # Test the configuration if enabled
        if config.enabled and config.webhook_url:
            slack_service = SlackService()
            try:
                await slack_service.send_test_message()
            except Exception as e:
                # Log the error but don't fail the configuration save
                print(f"Warning: Failed to test Slack configuration: {e}")
        
        # Return sanitized configuration
        response_config = slack_config_storage.copy()
        if response_config["webhook_url"]:
            webhook_url = response_config["webhook_url"]
            if len(webhook_url) > 20:
                response_config["webhook_url"] = webhook_url[:20] + "..." + webhook_url[-10:]
        
        return SlackConfigResponse(**response_config)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save Slack configuration: {str(e)}"
        )

@router.put("/config", response_model=SlackConfigResponse)
async def update_slack_config(
    config: SlackConfigRequest,
    current_admin: User = Depends(get_admin)
):
    """
    Update Slack configuration (partial update)
    """
    return await save_slack_config(config, current_admin)

@router.get("/messages", response_model=List[SlackMessageResponse])
async def get_slack_messages(
    page: int = 1,
    limit: int = 50,
    type: str = "all",
    status: str = "all",
    current_admin: User = Depends(get_admin)
):
    """
    Get Slack message history
    """
    try:
        # In production, fetch from database with proper pagination
        messages = slack_messages_storage.copy()
        
        # Apply filters
        if type != "all":
            messages = [m for m in messages if m.get("type") == type]
        if status != "all":
            messages = [m for m in messages if m.get("status") == status]
        
        # Sort by timestamp (newest first)
        messages.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=True)
        
        # Apply pagination
        start = (page - 1) * limit
        end = start + limit
        paginated_messages = messages[start:end]
        
        return [SlackMessageResponse(**msg) for msg in paginated_messages]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Slack messages: {str(e)}"
        )

@router.post("/messages", response_model=SlackMessageResponse)
async def send_slack_message(
    message: SlackMessageRequest,
    current_admin: User = Depends(get_admin)
):
    """
    Send a manual Slack message
    """
    try:
        if not slack_config_storage["enabled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Slack integration is not enabled"
            )
        
        slack_service = SlackService()
        message_id = f"msg_{datetime.utcnow().timestamp()}"
        
        # Create message record
        message_record = {
            "id": message_id,
            "type": message.type,
            "title": message.title,
            "content": message.content,
            "timestamp": datetime.utcnow(),
            "status": "pending",
            "submission_id": message.submission_id,
            "error_message": None
        }
        
        try:
            # Send to Slack
            if message.type == "test":
                await slack_service.send_test_message()
            else:
                # Send custom message
                await slack_service.send_custom_message(
                    title=message.title,
                    content=message.content,
                    message_type=message.type
                )
            
            message_record["status"] = "sent"
        except Exception as e:
            message_record["status"] = "failed"
            message_record["error_message"] = str(e)
        
        # Store message record
        slack_messages_storage.append(message_record)
        
        # In production, save to database
        
        return SlackMessageResponse(**message_record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send Slack message: {str(e)}"
        )

@router.delete("/messages/{message_id}")
async def delete_slack_message(
    message_id: str,
    current_admin: User = Depends(get_admin)
):
    """
    Delete a Slack message record
    """
    try:
        # Find and remove message
        global slack_messages_storage
        original_length = len(slack_messages_storage)
        slack_messages_storage = [m for m in slack_messages_storage if m.get("id") != message_id]
        
        if len(slack_messages_storage) == original_length:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # In production, delete from database
        
        return {"message": "Message deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete Slack message: {str(e)}"
        )

@router.get("/test")
async def test_slack_integration(
    current_admin: User = Depends(get_admin)
):
    """
    Test Slack integration
    """
    try:
        if not slack_config_storage["enabled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Slack integration is not enabled"
            )
        
        slack_service = SlackService()
        await slack_service.send_test_message()
        
        # Record the test message
        test_message = {
            "id": f"test_{datetime.utcnow().timestamp()}",
            "type": "test",
            "title": "Slack Integration Test",
            "content": "Test message sent from admin panel",
            "timestamp": datetime.utcnow(),
            "status": "sent",
            "submission_id": None,
            "error_message": None
        }
        slack_messages_storage.append(test_message)
        
        return {"message": "Test message sent successfully"}
    except HTTPException:
        raise
    except Exception as e:
        # Record failed test
        test_message = {
            "id": f"test_{datetime.utcnow().timestamp()}",
            "type": "test",
            "title": "Slack Integration Test",
            "content": "Test message failed",
            "timestamp": datetime.utcnow(),
            "status": "failed",
            "submission_id": None,
            "error_message": str(e)
        }
        slack_messages_storage.append(test_message)
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test message: {str(e)}"
        )