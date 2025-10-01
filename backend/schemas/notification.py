from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class NotificationType(str, Enum):
    APPLICATION_STATUS_UPDATE = "application_status_update"
    NEW_APPLICATION = "new_application"
    JOB_POSTED = "job_posted"
    JOB_EXPIRED = "job_expired"
    PROFILE_VIEWED = "profile_viewed"
    MESSAGE_RECEIVED = "message_received"
    SYSTEM_ANNOUNCEMENT = "system_announcement"

class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class NotificationBase(BaseModel):
    type: NotificationType
    title: str = Field(..., max_length=255)
    message: str
    data: Optional[Dict[str, Any]] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    action_url: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[datetime] = None

class NotificationCreate(NotificationBase):
    user_id: str

class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None
    title: Optional[str] = Field(None, max_length=255)
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    priority: Optional[NotificationPriority] = None
    action_url: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[datetime] = None

class Notification(NotificationBase):
    id: int
    user_id: str
    is_read: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class NotificationList(BaseModel):
    notifications: List[Notification]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool
    unread_count: int

class NotificationPreferencesBase(BaseModel):
    email_notifications: bool = True
    push_notifications: bool = True
    application_updates: bool = True
    new_job_alerts: bool = True
    marketing_emails: bool = False
    weekly_digest: bool = True

class NotificationPreferencesCreate(NotificationPreferencesBase):
    user_id: str

class NotificationPreferencesUpdate(BaseModel):
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    application_updates: Optional[bool] = None
    new_job_alerts: Optional[bool] = None
    marketing_emails: Optional[bool] = None
    weekly_digest: Optional[bool] = None

class NotificationPreferences(NotificationPreferencesBase):
    id: int
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class NotificationStats(BaseModel):
    total_notifications: int
    unread_notifications: int
    read_notifications: int
    notifications_by_type: Dict[str, int]
    recent_notifications: List[Notification]

class MarkAsReadRequest(BaseModel):
    notification_ids: Optional[List[int]] = None  # If None, mark all as read

class BulkNotificationCreate(BaseModel):
    user_ids: List[str]
    type: NotificationType
    title: str = Field(..., max_length=255)
    message: str
    data: Optional[Dict[str, Any]] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    action_url: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[datetime] = None