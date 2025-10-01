from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum

class AdminLogAction(str, Enum):
    """Enum for admin log actions"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    VERIFY = "verify"
    SUSPEND = "suspend"
    UNSUSPEND = "unsuspend"
    APPROVE = "approve"
    REJECT = "reject"
    EXPORT = "export"
    IMPORT = "import"
    BACKUP = "backup"
    RESTORE = "restore"
    VIEW_DASHBOARD_STATS = "view_dashboard_stats"

class AdminLogCreate(BaseModel):
    """Schema for creating admin log entries"""
    action: AdminLogAction
    target_table: Optional[str] = None
    target_id: Optional[str] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    notes: Optional[str] = None

class AdminLog(BaseModel):
    """Schema for admin log response"""
    id: int
    admin_user_id: str
    action: AdminLogAction
    target_table: Optional[str]
    target_id: Optional[str]
    old_values: Optional[Dict[str, Any]]
    new_values: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class SystemSettingUpdate(BaseModel):
    """Schema for updating system settings"""
    value: str = Field(..., min_length=1, max_length=1000)
    description: Optional[str] = Field(None, max_length=500)
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v):
        if not v or v.strip() == "":
            raise ValueError('Value cannot be empty')
        return v.strip()

class SystemSetting(BaseModel):
    """Schema for system setting response"""
    id: int
    key: str
    value: str
    data_type: str
    description: Optional[str]
    is_public: bool
    category: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    updated_by: Optional[str]
    
    class Config:
        from_attributes = True

class DashboardStats(BaseModel):
    """Schema for dashboard statistics"""
    total_users: int = Field(..., ge=0)
    active_users: int = Field(..., ge=0)
    total_jobs: int = Field(..., ge=0)
    active_jobs: int = Field(..., ge=0)
    total_applications: int = Field(..., ge=0)
    pending_applications: int = Field(..., ge=0)
    revenue_this_month: float = Field(..., ge=0)
    new_users_this_week: int = Field(..., ge=0)
    new_jobs_this_week: int = Field(..., ge=0)
    conversion_rate: float = Field(..., ge=0, le=100)
    avg_response_time: float = Field(..., ge=0)

class UserSuspensionCreate(BaseModel):
    """Schema for creating user suspension"""
    reason: str = Field(..., min_length=10, max_length=500)
    duration_days: Optional[int] = Field(None, ge=1, le=365)
    suspension_type: str = Field(default="temporary")
    notes: Optional[str] = Field(None, max_length=1000)
    
    @field_validator('suspension_type')
    @classmethod
    def validate_suspension_type(cls, v):
        if v not in ['temporary', 'permanent']:
            raise ValueError('Suspension type must be temporary or permanent')
        return v

class UserSuspension(BaseModel):
    """Schema for user suspension response"""
    id: int
    user_id: str
    reason: str
    duration_days: Optional[int]
    suspension_type: str
    notes: Optional[str]
    suspended_by: str
    starts_at: datetime
    ends_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class AnnouncementCreate(BaseModel):
    """Schema for creating announcements"""
    title: str = Field(..., min_length=5, max_length=200)
    content: str = Field(..., min_length=10, max_length=2000)
    type: str = Field(..., pattern="^(info|warning|success|error)$")
    target_audience: str = Field(..., pattern="^(all|job_seekers|employers|admins)$")
    is_active: bool = Field(default=True)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    
    @field_validator('ends_at')
    @classmethod
    def validate_end_date(cls, v, info):
        if v and hasattr(info, 'data') and 'starts_at' in info.data and info.data['starts_at']:
            if v <= info.data['starts_at']:
                raise ValueError('End date must be after start date')
        return v

class Announcement(BaseModel):
    """Schema for announcement response"""
    id: int
    title: str
    content: str
    type: str
    target_audience: str
    is_active: bool
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class ReportCreate(BaseModel):
    """Schema for creating reports"""
    reported_type: str = Field(..., pattern="^(user|job|application|review)$")
    reported_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=10, max_length=500)
    description: Optional[str] = Field(None, max_length=1000)
    evidence_urls: Optional[List[str]] = Field(default_factory=list)

class Report(BaseModel):
    """Schema for report response"""
    id: int
    reported_type: str
    reported_id: str
    reported_by: str
    reason: str
    description: Optional[str]
    evidence_urls: Optional[List[str]]
    status: str
    priority: str
    assigned_to: Optional[str]
    resolution: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class ReportUpdate(BaseModel):
    """Schema for updating reports"""
    status: Optional[str] = Field(None, pattern="^(pending|investigating|resolved|dismissed)$")
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|critical)$")
    assigned_to: Optional[str] = None
    resolution: Optional[str] = Field(None, max_length=1000)

class AnalyticsFilter(BaseModel):
    """Schema for analytics filtering"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metric_type: Optional[str] = Field(None, pattern="^(users|jobs|applications|revenue|engagement)$")
    group_by: Optional[str] = Field(None, pattern="^(day|week|month|year)$")
    
    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v, info):
        if v and hasattr(info, 'data') and 'start_date' in info.data and info.data['start_date']:
            if v <= info.data['start_date']:
                raise ValueError('End date must be after start date')
        return v

class DailyStats(BaseModel):
    """Schema for daily statistics"""
    date: str
    new_users: int = Field(..., ge=0)
    active_users: int = Field(..., ge=0)
    new_job_posts: int = Field(..., ge=0)
    new_applications: int = Field(..., ge=0)
    successful_applications: int = Field(..., ge=0)
    revenue: float = Field(..., ge=0)
    page_views: int = Field(..., ge=0)
    unique_visitors: int = Field(..., ge=0)
    
    class Config:
        from_attributes = True

class JobCategoryStats(BaseModel):
    """Schema for job category statistics"""
    category_name: str
    job_count: int = Field(..., ge=0)
    application_count: int = Field(..., ge=0)
    avg_salary: Optional[float] = Field(None, ge=0)
    success_rate: float = Field(..., ge=0, le=100)

class UserActivitySummary(BaseModel):
    """Schema for user activity summary"""
    user_id: str
    full_name: str
    email: str
    role: str
    last_login: Optional[datetime]
    total_logins: int = Field(..., ge=0)
    jobs_posted: Optional[int] = Field(None, ge=0)
    applications_sent: Optional[int] = Field(None, ge=0)
    profile_completion: float = Field(..., ge=0, le=100)
    account_status: str
    
    class Config:
        from_attributes = True

class SystemHealthCheck(BaseModel):
    """Schema for system health check"""
    status: str = Field(..., pattern="^(healthy|warning|critical)$")
    database_status: str
    redis_status: Optional[str]
    api_response_time: float = Field(..., ge=0)
    memory_usage: float = Field(..., ge=0, le=100)
    cpu_usage: float = Field(..., ge=0, le=100)
    disk_usage: float = Field(..., ge=0, le=100)
    active_connections: int = Field(..., ge=0)
    error_rate: float = Field(..., ge=0, le=100)
    uptime: str
    last_backup: Optional[datetime]
    
class BulkActionRequest(BaseModel):
    """Schema for bulk actions on users/jobs"""
    action: str = Field(..., pattern="^(activate|deactivate|verify|suspend|delete)$")
    target_ids: List[str] = Field(..., min_items=1, max_items=100)
    reason: Optional[str] = Field(None, max_length=500)
    
class BulkActionResult(BaseModel):
    """Schema for bulk action results"""
    action: str
    total_requested: int = Field(..., ge=0)
    successful: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    errors: List[Dict[str, str]] = Field(default_factory=list)
    
class ExportRequest(BaseModel):
    """Schema for data export requests"""
    export_type: str = Field(..., pattern="^(users|jobs|applications|analytics|logs)$")
    format: str = Field(..., pattern="^(csv|xlsx|json)$")
    date_range: Optional[Dict[str, datetime]] = None
    filters: Optional[Dict[str, Any]] = None
    include_sensitive: bool = Field(default=False)
    
class ExportStatus(BaseModel):
    """Schema for export status"""
    export_id: str
    status: str = Field(..., pattern="^(pending|processing|completed|failed)$")
    progress: float = Field(..., ge=0, le=100)
    file_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime]
    expires_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class AdminNotification(BaseModel):
    """Schema for admin notifications"""
    id: int
    title: str
    message: str
    type: str
    priority: str
    is_read: bool
    action_url: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class AdminNotificationCreate(BaseModel):
    """Schema for creating admin notifications"""
    title: str = Field(..., min_length=5, max_length=100)
    message: str = Field(..., min_length=10, max_length=500)
    type: str = Field(..., pattern="^(info|warning|error|success)$")
    priority: str = Field(..., pattern="^(low|medium|high|urgent)$")
    target_admins: Optional[List[str]] = Field(default_factory=list)
    action_url: Optional[str] = None

class PaginatedResponse(BaseModel):
    """Generic schema for paginated responses"""
    items: List[Any]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    per_page: int = Field(..., ge=1, le=100)
    pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool

class AdminDashboardWidget(BaseModel):
    """Schema for dashboard widgets"""
    widget_id: str
    title: str
    type: str = Field(..., pattern="^(stat|chart|table|alert)$")
    data: Dict[str, Any]
    position: Dict[str, int]
    is_visible: bool = Field(default=True)
    refresh_interval: int = Field(default=300, ge=30)  # seconds
    
class AdminPreferences(BaseModel):
    """Schema for admin user preferences"""
    theme: str = Field(default="light", pattern="^(light|dark|auto)$")
    language: str = Field(default="en", pattern="^(en|es|fr|de)$")
    timezone: str = Field(default="UTC")
    notifications_enabled: bool = Field(default=True)
    email_notifications: bool = Field(default=True)
    dashboard_layout: List[AdminDashboardWidget] = Field(default_factory=list)
    items_per_page: int = Field(default=20, ge=10, le=100)
    
class AdminSession(BaseModel):
    """Schema for admin session information"""
    session_id: str
    admin_user_id: str
    ip_address: str
    user_agent: str
    is_active: bool
    last_activity: datetime
    created_at: datetime
    expires_at: datetime
    
    class Config:
        from_attributes = True