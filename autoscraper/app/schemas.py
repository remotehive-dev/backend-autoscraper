from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
from uuid import UUID

class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class NotificationThresholds(BaseModel):
    error_rate: float = Field(default=10.0, ge=0, le=100, description="Error rate threshold percentage")
    success_rate: float = Field(default=80.0, ge=0, le=100, description="Success rate threshold percentage")
    queue_size: int = Field(default=100, ge=0, description="Queue size threshold")

class SystemSettings(BaseModel):
    # Rate Limiting
    global_rate_limit: int = Field(default=100, ge=1, description="Global rate limit per second")
    requests_per_minute: int = Field(default=60, ge=1, description="Requests per minute limit")
    burst_limit: int = Field(default=10, ge=1, description="Burst limit for requests")
    cooldown_period: int = Field(default=300, ge=0, description="Cooldown period in seconds")
    
    # Retry Policy
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum number of retries")
    retry_delay: int = Field(default=5000, ge=100, description="Retry delay in milliseconds")
    exponential_backoff: bool = Field(default=True, description="Enable exponential backoff")
    retry_on_errors: List[str] = Field(default=["TIMEOUT", "CONNECTION_ERROR", "RATE_LIMITED"], description="Error types to retry on")
    
    # Performance
    max_concurrent_jobs: int = Field(default=5, ge=1, le=50, description="Maximum concurrent jobs")
    job_timeout: int = Field(default=300000, ge=1000, description="Job timeout in milliseconds")
    memory_limit: int = Field(default=1024, ge=128, description="Memory limit in MB")
    disk_space_threshold: int = Field(default=85, ge=50, le=95, description="Disk space threshold percentage")
    
    # Data Management
    data_retention_days: int = Field(default=90, ge=1, description="Data retention period in days")
    auto_cleanup: bool = Field(default=True, description="Enable automatic cleanup")
    compress_old_data: bool = Field(default=True, description="Compress old data")
    backup_enabled: bool = Field(default=True, description="Enable backups")
    
    # Notifications
    email_notifications: bool = Field(default=True, description="Enable email notifications")
    slack_notifications: bool = Field(default=False, description="Enable Slack notifications")
    webhook_notifications: bool = Field(default=False, description="Enable webhook notifications")
    notification_thresholds: NotificationThresholds = Field(default_factory=NotificationThresholds)
    
    # Monitoring
    health_check_interval: int = Field(default=30, ge=5, description="Health check interval in seconds")
    metrics_retention: int = Field(default=30, ge=1, description="Metrics retention period in days")
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    enable_debug_mode: bool = Field(default=False, description="Enable debug mode")
    
    # Security
    api_key_rotation: bool = Field(default=True, description="Enable API key rotation")
    encrypt_data: bool = Field(default=True, description="Enable data encryption")
    audit_logging: bool = Field(default=True, description="Enable audit logging")
    ip_whitelist: List[str] = Field(default=[], description="IP whitelist for access control")

class SystemSettingsUpdate(BaseModel):
    # Rate Limiting
    global_rate_limit: Optional[int] = Field(None, ge=1)
    requests_per_minute: Optional[int] = Field(None, ge=1)
    burst_limit: Optional[int] = Field(None, ge=1)
    cooldown_period: Optional[int] = Field(None, ge=0)
    
    # Retry Policy
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    retry_delay: Optional[int] = Field(None, ge=100)
    exponential_backoff: Optional[bool] = None
    retry_on_errors: Optional[List[str]] = None
    
    # Performance
    max_concurrent_jobs: Optional[int] = Field(None, ge=1, le=50)
    job_timeout: Optional[int] = Field(None, ge=1000)
    memory_limit: Optional[int] = Field(None, ge=128)
    disk_space_threshold: Optional[int] = Field(None, ge=50, le=95)
    
    # Data Management
    data_retention_days: Optional[int] = Field(None, ge=1)
    auto_cleanup: Optional[bool] = None
    compress_old_data: Optional[bool] = None
    backup_enabled: Optional[bool] = None
    
    # Notifications
    email_notifications: Optional[bool] = None
    slack_notifications: Optional[bool] = None
    webhook_notifications: Optional[bool] = None
    notification_thresholds: Optional[NotificationThresholds] = None
    
    # Monitoring
    health_check_interval: Optional[int] = Field(None, ge=5)
    metrics_retention: Optional[int] = Field(None, ge=1)
    log_level: Optional[LogLevel] = None
    enable_debug_mode: Optional[bool] = None
    
    # Security
    api_key_rotation: Optional[bool] = None
    encrypt_data: Optional[bool] = None
    audit_logging: Optional[bool] = None
    ip_whitelist: Optional[List[str]] = None

class SettingsTestRequest(BaseModel):
    test_type: str = Field(..., description="Type of test to perform")
    settings: Optional[SystemSettings] = Field(None, description="Settings to test")

class SettingsTestResponse(BaseModel):
    success: bool
    message: str
    details: Optional[dict] = None

class SystemHealthResponse(BaseModel):
    status: str
    uptime: int
    memory_usage: float
    cpu_usage: float
    disk_usage: float
    active_jobs: int
    queue_size: int
    last_check: str

class PerformanceMetrics(BaseModel):
    requests_per_second: float
    average_response_time: float
    error_rate: float
    success_rate: float
    active_connections: int
    memory_usage_mb: float
    cpu_usage_percent: float
    disk_usage_percent: float
    timestamp: str

# Job Board Schemas
class JobBoardType(str, Enum):
    RSS = "rss"
    HTML = "html"
    API = "api"
    HYBRID = "hybrid"

class JobBoardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    type: JobBoardType  # Changed from board_type to type to match model
    base_url: str = Field(..., min_length=1, max_length=500)
    rss_url: Optional[str] = Field(None, max_length=500)
    selectors: Optional[Dict[str, Any]] = None
    rate_limit_delay: int = Field(default=2, ge=1)
    max_pages: int = Field(default=10, ge=1)
    request_timeout: int = Field(default=30, ge=1)
    retry_attempts: int = Field(default=3, ge=0)
    is_active: bool = Field(default=True)

class JobBoardUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    type: Optional[JobBoardType] = None  # Changed from board_type to type to match model
    base_url: Optional[str] = Field(None, min_length=1, max_length=500)
    rss_url: Optional[str] = Field(None, max_length=500)
    selectors: Optional[Dict[str, Any]] = None
    rate_limit_delay: Optional[int] = Field(None, ge=1)
    max_pages: Optional[int] = Field(None, ge=1)
    request_timeout: Optional[int] = Field(None, ge=1)
    retry_attempts: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

class JobBoardResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    type: JobBoardType  # Changed from board_type to type to match model
    base_url: str
    rss_url: Optional[str]
    region: Optional[str]  # Added region field
    selectors: Optional[Dict[str, Any]]
    rate_limit_delay: int
    max_pages: int
    request_timeout: int
    retry_attempts: int
    is_active: bool
    success_rate: float
    last_scraped_at: Optional[datetime]
    total_scrapes: int
    successful_scrapes: int
    failed_scrapes: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Schedule Config Schemas
class ScheduleConfigCreate(BaseModel):
    job_board_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    cron_expression: str = Field(..., min_length=1, max_length=100)
    timezone: str = Field(default="UTC", max_length=50)
    is_enabled: bool = Field(default=True)
    max_concurrent_jobs: int = Field(default=1, ge=1)
    max_retries: int = Field(default=3, ge=0)
    retry_delay_minutes: int = Field(default=5, ge=1)

class ScheduleConfigUpdate(BaseModel):
    job_board_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    cron_expression: Optional[str] = Field(None, min_length=1, max_length=100)
    timezone: Optional[str] = Field(None, max_length=50)
    is_enabled: Optional[bool] = None
    max_concurrent_jobs: Optional[int] = Field(None, ge=1)
    max_retries: Optional[int] = Field(None, ge=0)
    retry_delay_minutes: Optional[int] = Field(None, ge=1)

class ScheduleConfigResponse(BaseModel):
    id: UUID
    job_board_id: UUID
    name: str
    description: Optional[str]
    cron_expression: str
    timezone: str
    is_enabled: bool
    max_concurrent_jobs: int
    max_retries: int
    retry_delay_minutes: int
    next_run_at: Optional[datetime]
    last_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Scrape Job Schemas
class ScrapeJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ScrapeJobMode(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    CONTINUOUS = "continuous"

class ScrapeJobCreate(BaseModel):
    job_board_id: UUID
    schedule_config_id: Optional[UUID] = None
    mode: ScrapeJobMode  # Changed from job_mode to mode to match model
    priority: int = Field(default=0, ge=0)

class ScrapeJobUpdate(BaseModel):
    status: Optional[ScrapeJobStatus] = None
    priority: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None

class ScrapeJobResponse(BaseModel):
    id: UUID
    job_board_id: UUID
    schedule_config_id: Optional[UUID]
    mode: ScrapeJobMode  # Changed from job_mode to mode to match model
    status: ScrapeJobStatus
    priority: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    total_items_found: int
    items_processed: int  # Changed from total_items_processed to items_processed to match model
    total_items_created: int
    total_items_updated: int
    total_items_skipped: int
    error_message: Optional[str]
    error_details: Optional[Dict[str, Any]]
    retry_count: int
    config_snapshot: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Scrape Run Schemas
class ScrapeRunResponse(BaseModel):
    id: UUID
    scrape_job_id: UUID
    run_type: str
    url: str
    page_number: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    items_found: int
    items_processed: int
    items_created: int
    items_updated: int
    items_skipped: int
    http_status_code: Optional[int]
    response_size_bytes: Optional[int]
    error_message: Optional[str]
    error_details: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Raw Job Schemas
class RawJobResponse(BaseModel):
    id: UUID
    scrape_run_id: UUID
    job_board_id: UUID
    source_url: str
    source_id: Optional[str]
    title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    description: Optional[str]
    salary: Optional[str]
    posted_at: Optional[datetime]
    raw_data: Optional[Dict[str, Any]]
    checksum: Optional[str]
    is_processed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Normalized Job Schemas
class NormalizedJobResponse(BaseModel):
    id: UUID
    raw_job_id: UUID
    title: str
    company: str
    location: Optional[str]
    description: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    salary_currency: Optional[str]
    employment_type: Optional[str]
    experience_level: Optional[str]
    skills: Optional[List[str]]
    benefits: Optional[List[str]]
    posted_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_remote: bool
    confidence_score: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Engine State Schemas
class EngineStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    MAINTENANCE = "maintenance"

class EngineStateResponse(BaseModel):
    status: EngineStatus
    active_jobs: int
    queued_jobs: int
    total_jobs_today: int
    success_rate: float
    last_activity: Optional[datetime]
    uptime_seconds: int

    class Config:
        from_attributes = True

# Request/Response Schemas
class StartScrapeJobRequest(BaseModel):
    job_board_ids: List[UUID] = Field(..., min_items=1)
    priority: int = Field(default=0, ge=0)
    mode: ScrapeJobMode = Field(default=ScrapeJobMode.MANUAL)

class EngineStartRequest(BaseModel):
    job_board_ids: Optional[List[UUID]] = Field(default=None, description="Optional list of specific job boards to start. If not provided, all active job boards will be started.")
    priority: int = Field(default=0, ge=0)
    mode: ScrapeJobMode = Field(default=ScrapeJobMode.MANUAL)

class PauseScrapeJobRequest(BaseModel):
    job_ids: List[UUID] = Field(..., min_items=1)
    reason: Optional[str] = None

class HardResetRequest(BaseModel):
    confirm: bool = Field(..., description="Must be true to confirm reset")
    reset_data: bool = Field(default=False, description="Whether to reset scraped data")
    reset_configs: bool = Field(default=False, description="Whether to reset configurations")

# Dashboard Schemas
class DashboardStats(BaseModel):
    total_job_boards: int
    active_job_boards: int
    total_scrape_jobs: int
    running_jobs: int
    completed_jobs_today: int
    failed_jobs_today: int
    total_jobs_scraped: int
    success_rate: float

    class Config:
        from_attributes = True

class RecentActivity(BaseModel):
    id: UUID
    type: str
    message: str
    timestamp: datetime
    status: str

    class Config:
        from_attributes = True

class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_activity: List[RecentActivity]
    engine_status: EngineStateResponse

# Health Check Schemas
class HealthCheckResponse(BaseModel):
    status: str
    timestamp: datetime
    services: Dict[str, str]
    version: str

# Logging Schemas
class LogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str
    source: Optional[str]
    job_id: Optional[UUID]
    details: Optional[Dict[str, Any]]

class LiveLogsResponse(BaseModel):
    logs: List[LogEntry]
    total_count: int
    has_more: bool

# Generic Response Schemas
class SuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None

# Authentication Schemas
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class UserInfo(BaseModel):
    user_id: str
    username: str
    roles: List[str] = []
    permissions: List[str] = []

# Rate Limiting Schemas
class RateLimitInfo(BaseModel):
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None