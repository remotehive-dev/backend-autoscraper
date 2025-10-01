#!/usr/bin/env python3
"""
Autoscraper Models
Database models for the dedicated autoscraper service
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, Float, JSON, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from enum import Enum as PyEnum
import uuid

# Create base for autoscraper models
Base = declarative_base()


class JobBoardType(PyEnum):
    """Job board types for autoscraper"""
    RSS = "rss"
    HTML = "html"
    API = "api"
    HYBRID = "hybrid"


class ScrapeJobStatus(PyEnum):
    """Scrape job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScrapeJobMode(PyEnum):
    """Scrape job mode enumeration"""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    CONTINUOUS = "continuous"


class EngineStatus(PyEnum):
    """Engine status enumeration"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class JobBoard(Base):
    """Job board configuration for autoscraper"""
    __tablename__ = 'autoscraper_job_boards'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    type = Column(Enum(JobBoardType), nullable=False)  # Changed from board_type to type
    base_url = Column(String(500), nullable=False)
    rss_url = Column(String(500), nullable=True)  # For RSS feeds
    
    # Scraping configuration
    selectors = Column(JSON, nullable=True)  # CSS/XPath selectors for HTML scraping
    headers = Column(JSON, nullable=True)  # HTTP headers
    rate_limit_delay = Column(Integer, default=2)  # Seconds between requests
    max_pages = Column(Integer, default=10)
    request_timeout = Column(Integer, default=30)
    retry_attempts = Column(Integer, default=3)
    quality_threshold = Column(Float, default=0.7)  # Quality threshold for job filtering
    
    # Status and metrics
    is_active = Column(Boolean, default=True)
    success_rate = Column(Float, default=0.0)
    last_scraped_at = Column(DateTime, nullable=True)
    total_scrapes = Column(Integer, default=0)
    successful_scrapes = Column(Integer, default=0)
    failed_scrapes = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    scrape_jobs = relationship("ScrapeJob", back_populates="job_board")
    schedule_configs = relationship("ScheduleConfig", back_populates="job_board")
    
    # Indexes
    __table_args__ = (
        Index('idx_job_board_type', 'type'),
        Index('idx_job_board_active', 'is_active'),
    )


class ScheduleConfig(Base):
    """Schedule configuration for automated scraping"""
    __tablename__ = 'autoscraper_schedule_configs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_board_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_job_boards.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Schedule configuration
    cron_expression = Column(String(100), nullable=False)  # Cron format
    timezone = Column(String(50), default='UTC')
    is_enabled = Column(Boolean, default=True)
    
    # Job configuration
    max_concurrent_jobs = Column(Integer, default=1)
    max_retries = Column(Integer, default=3)
    retry_delay_minutes = Column(Integer, default=5)
    
    # Schedule tracking
    next_run_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    job_board = relationship("JobBoard", back_populates="schedule_configs")
    scrape_jobs = relationship("ScrapeJob", back_populates="schedule_config")
    
    # Indexes
    __table_args__ = (
        Index('idx_schedule_enabled', 'is_enabled'),
        Index('idx_schedule_next_run', 'next_run_at'),
    )


class ScrapeJob(Base):
    """Individual scrape job execution"""
    __tablename__ = 'autoscraper_scrape_jobs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_board_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_job_boards.id', ondelete='CASCADE'), nullable=False)
    schedule_config_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_schedule_configs.id', ondelete='SET NULL'), nullable=True)
    
    # Job configuration
    mode = Column(Enum(ScrapeJobMode), nullable=False)  # Changed from job_mode to mode
    status = Column(Enum(ScrapeJobStatus), default=ScrapeJobStatus.PENDING)
    priority = Column(Integer, default=0)  # Higher number = higher priority
    max_pages = Column(Integer, nullable=True)  # Override job board default
    
    # Execution tracking
    celery_task_id = Column(String(255), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Results tracking
    items_processed = Column(Integer, default=0)  # Changed from total_items_processed
    total_items_found = Column(Integer, default=0)
    total_items_created = Column(Integer, default=0)
    total_items_updated = Column(Integer, default=0)
    total_items_skipped = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)  # Added for compatibility
    
    # Error handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Configuration snapshot
    config_snapshot = Column(JSON, nullable=True)  # Snapshot of board config at execution time
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    job_board = relationship("JobBoard", back_populates="scrape_jobs")
    schedule_config = relationship("ScheduleConfig", back_populates="scrape_jobs")
    scrape_runs = relationship("ScrapeRun", back_populates="scrape_job")
    
    # Indexes
    __table_args__ = (
        Index('idx_scrape_job_status', 'status'),
        Index('idx_scrape_job_mode', 'mode'),
        Index('idx_scrape_job_priority', 'priority'),
        Index('idx_scrape_job_created', 'created_at'),
    )


class ScrapeRun(Base):
    """Individual page/URL scrape within a job"""
    __tablename__ = 'autoscraper_scrape_runs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scrape_job_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_scrape_jobs.id', ondelete='CASCADE'), nullable=False)
    
    # Run configuration
    run_type = Column(String(50), nullable=False)  # 'rss', 'html', 'api'
    url = Column(String(1000), nullable=False)
    page_number = Column(Integer, default=1)
    
    # Execution tracking
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Results tracking
    items_found = Column(Integer, default=0)
    items_processed = Column(Integer, default=0)
    items_created = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    items_skipped = Column(Integer, default=0)
    
    # HTTP response tracking
    http_status_code = Column(Integer, nullable=True)
    response_size_bytes = Column(Integer, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    scrape_job = relationship("ScrapeJob", back_populates="scrape_runs")
    raw_jobs = relationship("RawJob", back_populates="scrape_run")
    
    # Indexes
    __table_args__ = (
        Index('idx_scrape_run_type', 'run_type'),
        Index('idx_scrape_run_created', 'created_at'),
    )


class RawJob(Base):
    """Raw job data extracted from job boards"""
    __tablename__ = 'autoscraper_raw_jobs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scrape_run_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_scrape_runs.id', ondelete='CASCADE'), nullable=False)
    
    # Raw job fields
    title = Column(String(500), nullable=True)
    company = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(1000), nullable=True)
    salary = Column(String(255), nullable=True)
    job_type = Column(String(100), nullable=True)
    posted_date = Column(String(255), nullable=True)  # Raw string before parsing
    
    # Raw data storage
    raw_data = Column(JSON, nullable=True)  # Complete raw data as JSON
    html_content = Column(Text, nullable=True)  # Raw HTML if needed
    
    # Processing status
    is_processed = Column(Boolean, default=False)
    is_duplicate = Column(Boolean, default=False)
    checksum = Column(String(64), nullable=True)  # For deduplication
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    scrape_run = relationship("ScrapeRun", back_populates="raw_jobs")
    normalized_job = relationship("NormalizedJob", back_populates="raw_job", uselist=False)
    
    # Indexes
    __table_args__ = (
        Index('idx_raw_job_processed', 'is_processed'),
        Index('idx_raw_job_duplicate', 'is_duplicate'),
        Index('idx_raw_job_checksum', 'checksum'),
        Index('idx_raw_job_created', 'created_at'),
    )


class NormalizedJob(Base):
    """Normalized and cleaned job data"""
    __tablename__ = 'autoscraper_normalized_jobs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_job_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_raw_jobs.id', ondelete='CASCADE'), nullable=False)
    
    # Normalized job fields
    title = Column(String(500), nullable=False)
    company = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(1000), nullable=True)
    
    # Salary information
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String(10), default='USD')
    salary_period = Column(String(20), nullable=True)  # hourly, monthly, yearly
    
    # Job details
    job_type = Column(String(100), nullable=True)  # full-time, part-time, contract
    experience_level = Column(String(50), nullable=True)
    remote_allowed = Column(Boolean, default=False)
    
    # Dates
    posted_date = Column(DateTime, nullable=True)
    application_deadline = Column(DateTime, nullable=True)
    
    # Additional fields
    skills_required = Column(JSON, nullable=True)  # Array of skills
    education_required = Column(String(100), nullable=True)
    
    # Normalization metadata
    normalization_confidence = Column(Float, default=0.0)  # 0.0 to 1.0
    normalization_method = Column(String(50), nullable=True)  # 'rule_based', 'ml', 'hybrid'
    
    # Publishing status
    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)
    job_post_id = Column(UUID(as_uuid=True), nullable=True)  # Reference to main job_posts table
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    raw_job = relationship("RawJob", back_populates="normalized_job")
    # Note: job_post relationship would be defined in main app models
    
    # Indexes
    __table_args__ = (
        Index('idx_normalized_job_published', 'is_published'),
        Index('idx_normalized_job_posted_date', 'posted_date'),
        Index('idx_normalized_job_created', 'created_at'),
    )


class EngineState(Base):
    """Autoscraper engine state and metrics"""
    __tablename__ = 'autoscraper_engine_state'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Engine status
    status = Column(Enum(EngineStatus), default=EngineStatus.IDLE)
    last_heartbeat = Column(DateTime, nullable=True)
    
    # Job metrics
    active_jobs_count = Column(Integer, default=0)
    queued_jobs_count = Column(Integer, default=0)
    total_jobs_processed = Column(Integer, default=0)
    total_jobs_today = Column(Integer, default=0)  # Added for compatibility
    success_rate_today = Column(Float, default=0.0)  # Added for compatibility
    
    # Performance metrics
    average_job_duration = Column(Float, default=0.0)  # seconds
    success_rate = Column(Float, default=0.0)  # 0.0 to 1.0
    
    # System metrics
    memory_usage_mb = Column(Float, default=0.0)
    cpu_usage_percent = Column(Float, default=0.0)
    system_load = Column(Float, default=0.0)  # Added for compatibility
    
    # Configuration
    max_concurrent_jobs = Column(Integer, default=5)
    maintenance_mode = Column(Boolean, default=False)
    version = Column(String(50), default="1.0.0")  # Added for compatibility
    configuration = Column(JSON, nullable=True)  # Added for compatibility
    
    # Error tracking
    last_error_message = Column(Text, nullable=True)
    last_error_at = Column(DateTime, nullable=True)
    consecutive_errors = Column(Integer, default=0)
    error_count_today = Column(Integer, default=0)  # Added for compatibility
    
    # Uptime tracking
    uptime_seconds = Column(Integer, default=0)  # Added for compatibility
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Property mappings for EngineStateResponse compatibility
    @property
    def active_jobs(self):
        return self.active_jobs_count
    
    @property
    def queued_jobs(self):
        return self.queued_jobs_count
    
    @property
    def last_activity(self):
        return self.last_heartbeat
    
    # Indexes
    __table_args__ = (
        Index('idx_engine_status', 'status'),
        Index('idx_engine_heartbeat', 'last_heartbeat'),
    )