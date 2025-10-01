#!/usr/bin/env python3
"""
MongoDB Document Models for AutoScraper Service using Beanie ODM
Replacement for SQLAlchemy models to work with MongoDB Atlas
"""

from beanie import Document, Indexed
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid
from bson import ObjectId


class JobBoardType(str, Enum):
    """Job board type enumeration"""
    INDEED = "indeed"
    LINKEDIN = "linkedin"
    GLASSDOOR = "glassdoor"
    MONSTER = "monster"
    ZIPRECRUITER = "ziprecruiter"
    CAREERBUILDER = "careerbuilder"
    DICE = "dice"
    STACKOVERFLOW = "stackoverflow"
    ANGELLIST = "angellist"
    REMOTE_OK = "remote_ok"
    WE_WORK_REMOTELY = "we_work_remotely"
    FLEXJOBS = "flexjobs"
    UPWORK = "upwork"
    FREELANCER = "freelancer"
    TOPTAL = "toptal"
    GURU = "guru"
    FIVERR = "fiverr"
    PEOPLEPERHOUR = "peopleperhour"
    CONTRA = "contra"
    GUN_IO = "gun_io"
    AUTHENTIC_JOBS = "authentic_jobs"
    DRIBBBLE = "dribbble"
    BEHANCE = "behance"
    GITHUB_JOBS = "github_jobs"
    HACKER_NEWS = "hacker_news"
    PRODUCT_HUNT = "product_hunt"
    ANGEL_CO = "angel_co"
    CRUNCHBASE = "crunchbase"
    TECHCRUNCH = "techcrunch"
    VENTUREBEAT = "venturebeat"
    MASHABLE = "mashable"
    THE_VERGE = "the_verge"
    WIRED = "wired"
    FAST_COMPANY = "fast_company"
    HARVARD_BUSINESS_REVIEW = "harvard_business_review"
    MIT_TECHNOLOGY_REVIEW = "mit_technology_review"
    CUSTOM = "custom"


class ScrapeJobStatus(str, Enum):
    """Scrape job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RETRYING = "retrying"


class ScrapeJobMode(str, Enum):
    """Scrape job mode enumeration"""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    API = "api"
    WEBHOOK = "webhook"


class JobBoardStatus(str, Enum):
    """Job board status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    DEPRECATED = "deprecated"


class EngineStatus(str, Enum):
    """Engine status enumeration"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class JobBoard(Document):
    """Job board configuration document model"""
    name: str
    type: JobBoardType
    base_url: str
    search_url_template: str
    description: Optional[str] = None  # Added description field
    region: Optional[str] = None
    is_active: bool = True
    rate_limit_delay: float = 1.0
    max_pages_per_search: int = 10
    selectors: Dict[str, str] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    cookies: Dict[str, str] = Field(default_factory=dict)
    proxy_enabled: bool = False
    javascript_required: bool = False
    captcha_protection: bool = False
    requires_login: bool = False
    login_url: Optional[str] = None
    login_credentials: Optional[Dict[str, str]] = None
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    last_successful_scrape: Optional[datetime] = None
    total_jobs_scraped: int = 0
    success_rate: float = 0.0
    average_response_time: float = 0.0
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "job_boards"
        indexes = [
            "name",
            "type",
            "is_active",
            "created_at"
        ]


class ScheduleConfig(Document):
    """Schedule configuration document model"""
    name: str
    job_board_ids: List[str] = Field(default_factory=list)  # References to JobBoard documents
    search_terms: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    job_types: List[str] = Field(default_factory=list)
    experience_levels: List[str] = Field(default_factory=list)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    remote_only: bool = False
    date_posted_days: int = 7
    max_results_per_board: int = 100
    
    # Schedule settings
    is_active: bool = True
    schedule_type: str = "interval"  # interval, cron, manual
    interval_minutes: Optional[int] = None
    cron_expression: Optional[str] = None
    timezone: str = "UTC"
    
    # Execution settings
    max_concurrent_jobs: int = 3
    retry_failed_jobs: bool = True
    max_retries: int = 3
    retry_delay_minutes: int = 30
    
    # Notification settings
    notify_on_completion: bool = False
    notify_on_failure: bool = True
    notification_emails: List[str] = Field(default_factory=list)
    webhook_url: Optional[str] = None
    
    # Metadata
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "schedule_configs"
        indexes = [
            "name",
            "is_active",
            "schedule_type",
            "next_run_at",
            "created_at"
        ]


class ScrapeJob(Document):
    """Scrape job document model"""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schedule_config_id: Optional[str] = None  # Reference to ScheduleConfig document
    job_board_id: str  # Reference to JobBoard document
    
    # Job parameters
    search_terms: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    remote_only: bool = False
    date_posted_days: int = 7
    max_results: int = 100
    
    # Job execution
    status: ScrapeJobStatus = ScrapeJobStatus.PENDING
    mode: ScrapeJobMode = ScrapeJobMode.MANUAL
    priority: int = 5  # 1-10, higher is more priority
    
    # Timing
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Results
    total_pages_scraped: int = 0
    total_jobs_found: int = 0
    total_jobs_processed: int = 0
    total_jobs_saved: int = 0
    total_duplicates_skipped: int = 0
    
    # Error handling
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Metadata
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    proxy_used: Optional[str] = None
    
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "scrape_jobs"
        indexes = [
            "job_id",
            "schedule_config_id",
            "job_board_id",
            "status",
            "mode",
            "priority",
            "scheduled_at",
            "created_at"
        ]


class ScrapeRun(Document):
    """Scrape run document model"""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scrape_job_id: str  # Reference to ScrapeJob document
    
    # Run details
    page_number: int
    page_url: str
    status: ScrapeJobStatus = ScrapeJobStatus.PENDING
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Results
    jobs_found_on_page: int = 0
    jobs_processed: int = 0
    jobs_saved: int = 0
    duplicates_skipped: int = 0
    
    # Response details
    http_status_code: Optional[int] = None
    response_size_bytes: Optional[int] = None
    response_time_ms: Optional[float] = None
    
    # Error handling
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    
    # Raw data (optional, for debugging)
    raw_html: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "scrape_runs"
        indexes = [
            "run_id",
            "scrape_job_id",
            "status",
            "page_number",
            "created_at"
        ]


class RawJob(Document):
    """Raw job data document model"""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scrape_run_id: str  # Reference to ScrapeRun document
    job_board_id: str  # Reference to JobBoard document
    
    # Raw scraped data
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    salary: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    posted_date: Optional[str] = None
    application_url: Optional[str] = None
    job_url: Optional[str] = None
    
    # Additional raw fields
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Processing status
    is_processed: bool = False
    processed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    
    # Deduplication
    content_hash: Optional[str] = None
    url_hash: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "raw_jobs"
        indexes = [
            "job_id",
            "scrape_run_id",
            "job_board_id",
            "is_processed",
            "content_hash",
            "url_hash",
            "created_at"
        ]


class NormalizedJob(Document):
    """Normalized job data document model"""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    raw_job_id: str  # Reference to RawJob document
    job_board_id: str  # Reference to JobBoard document
    
    # Normalized data
    title: str
    company: str
    location: Optional[str] = None
    description: str
    requirements: Optional[str] = None
    benefits: Optional[str] = None
    
    # Salary information
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    salary_period: Optional[str] = None  # hourly, monthly, yearly
    
    # Job details
    job_type: Optional[str] = None  # full-time, part-time, contract, etc.
    experience_level: Optional[str] = None  # entry, mid, senior, etc.
    remote_allowed: bool = False
    
    # Location details
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    
    # Dates
    posted_date: Optional[datetime] = None
    application_deadline: Optional[datetime] = None
    
    # URLs
    application_url: Optional[str] = None
    job_url: Optional[str] = None
    
    # Skills and tags
    skills: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    
    # Quality metrics
    quality_score: float = 0.0
    completeness_score: float = 0.0
    
    # Deduplication
    content_hash: str
    duplicate_of: Optional[str] = None  # Reference to another NormalizedJob
    
    # Export status
    exported_to_main_db: bool = False
    exported_at: Optional[datetime] = None
    export_error: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "normalized_jobs"
        indexes = [
            "job_id",
            "raw_job_id",
            "job_board_id",
            "title",
            "company",
            "location",
            "job_type",
            "experience_level",
            "remote_allowed",
            "posted_date",
            "content_hash",
            "exported_to_main_db",
            "created_at"
        ]


class EngineState(Document):
    """Engine state document model"""
    engine_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: EngineStatus = EngineStatus.IDLE
    
    # Job counts (matching EngineStateResponse schema)
    active_jobs: int = 0
    queued_jobs: int = 0
    total_jobs_today: int = 0
    success_rate: float = 0.0
    
    # Timing
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    uptime_seconds: int = 0
    
    # Legacy fields for backward compatibility
    name: Optional[str] = None
    current_job_id: Optional[str] = None
    current_operation: Optional[str] = None
    total_jobs_processed: int = 0
    total_jobs_completed: int = 0
    total_jobs_failed: int = 0
    average_job_duration: float = 0.0
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    disk_usage_mb: float = 0.0
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    health_status: str = "healthy"
    error_count: int = 0
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    max_concurrent_jobs: int = 3
    worker_threads: int = 4
    version: Optional[str] = None
    host_name: Optional[str] = None
    process_id: Optional[int] = None
    
    started_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "engine_states"
        indexes = [
            "engine_id",
            "name",
            "status",
            "health_status",
            "last_heartbeat",
            "started_at"
        ]


class ScrapingMetrics(Document):
    """
    Scraping performance metrics
    """
    job_board: str
    engine: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    jobs_scraped: int = 0
    success_rate: float = 0.0
    error_count: int = 0
    errors: List[str] = Field(default_factory=list)
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    network_requests: int = 0
    bytes_downloaded: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Settings:
        name = "scraping_metrics"
        indexes = [
            "job_board",
            "engine", 
            "start_time",
            ["job_board", "engine"],
            ["start_time", "end_time"]
        ]


class JobPosting(Document):
    """Job posting document for data quality validation"""
    title: str
    company: str
    location: Optional[str] = None
    description: str
    url: str
    job_board: str
    scraped_at: datetime = Field(default_factory=datetime.now)
    
    # Optional fields
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    employment_type: Optional[str] = None  # full-time, part-time, contract, etc.
    experience_level: Optional[str] = None  # entry, mid, senior, etc.
    remote_type: Optional[str] = None  # remote, hybrid, on-site
    skills: Optional[List[str]] = None
    benefits: Optional[List[str]] = None
    posted_date: Optional[datetime] = None
    application_deadline: Optional[datetime] = None
    
    class Settings:
        name = "job_postings"
        indexes = [
            "job_board",
            "scraped_at",
            "company",
            "location",
            "employment_type",
            "remote_type",
            ["job_board", "scraped_at"],
            ["company", "title"]
        ]


class ScrapingSession(Document):
    """Scraping session tracking document"""
    job_board_name: str
    engine: str  # ScrapingEngine value
    status: str  # pending, running, completed, failed
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_time: Optional[float] = None  # Total time in seconds
    jobs_found: Optional[int] = None
    jobs_processed: Optional[int] = None
    errors: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Settings:
        name = "scraping_sessions"
        indexes = [
            "job_board_name",
            "engine",
            "status",
            "created_at",
            ["job_board_name", "created_at"],
            ["status", "created_at"]
        ]