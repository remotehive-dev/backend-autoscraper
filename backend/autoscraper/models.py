# from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, Float, JSON, UniqueConstraint, Index  # TODO: MongoDB Migration - Remove SQLAlchemy dependency
# from sqlalchemy.ext.declarative import declarative_base  # TODO: MongoDB Migration - Remove SQLAlchemy dependency
# from sqlalchemy.orm import relationship  # TODO: MongoDB Migration - Remove SQLAlchemy dependency
# from sqlalchemy.sql import func  # TODO: MongoDB Migration - Remove SQLAlchemy dependency
# from sqlalchemy.dialects.postgresql import UUID  # TODO: MongoDB Migration - Remove SQLAlchemy dependency
from datetime import datetime
from enum import Enum as PyEnum
import uuid

# Import the base from the main models file
# TODO: MongoDB Migration - Update Base import to use MongoDB models
# from backend.database.models import Base
# from backend.models.mongodb_models import Base  # TODO: MongoDB Migration - Temporarily disabled


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


# TODO: MongoDB Migration - Temporarily disabled SQLAlchemy models
# class JobBoard(Base):
#     """Job board configuration for autoscraper"""
#     __tablename__ = 'autoscraper_job_boards'
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     name = Column(String(255), nullable=False, unique=True)
#     description = Column(Text, nullable=True)
#     board_type = Column(Enum(JobBoardType), nullable=False)
#     base_url = Column(String(500), nullable=False)
#     rss_url = Column(String(500), nullable=True)  # For RSS feeds
#     
#     # Scraping configuration
#     selectors = Column(JSON, nullable=True)  # CSS/XPath selectors for HTML scraping
#     rate_limit_delay = Column(Integer, default=2)  # Seconds between requests
#     max_pages = Column(Integer, default=10)
#     request_timeout = Column(Integer, default=30)
#     retry_attempts = Column(Integer, default=3)
#     
#     # Status and metrics
#     is_active = Column(Boolean, default=True)
#     success_rate = Column(Float, default=0.0)
#     last_scraped_at = Column(DateTime, nullable=True)
#     total_scrapes = Column(Integer, default=0)
#     successful_scrapes = Column(Integer, default=0)
#     failed_scrapes = Column(Integer, default=0)
#     
#     # Timestamps
#     created_at = Column(DateTime, server_default=func.now())
#     updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
#     
#     # Relationships
#     scrape_jobs = relationship("ScrapeJob", back_populates="job_board")
#     schedule_configs = relationship("ScheduleConfig", back_populates="job_board")
#     
#     # Indexes
#     __table_args__ = (
#         Index('idx_job_board_type', 'board_type'),
#         Index('idx_job_board_active', 'is_active'),
#     )


# class ScheduleConfig(Base):
#     """Schedule configuration for automated scraping"""
#     __tablename__ = 'autoscraper_schedule_configs'
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     job_board_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_job_boards.id', ondelete='CASCADE'), nullable=False)
#     name = Column(String(255), nullable=False)
#     description = Column(Text, nullable=True)
#     
#     # Schedule configuration
#     cron_expression = Column(String(100), nullable=False)  # Cron format
#     timezone = Column(String(50), default='UTC')
#     is_enabled = Column(Boolean, default=True)
#     
#     # Execution limits
#     max_concurrent_jobs = Column(Integer, default=1)
#     max_retries = Column(Integer, default=3)
#     retry_delay_minutes = Column(Integer, default=5)
#     
#     # Next execution
#     next_run_at = Column(DateTime, nullable=True)
#     last_run_at = Column(DateTime, nullable=True)
#     
#     # Timestamps
#     created_at = Column(DateTime, server_default=func.now())
#     updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
#     
#     # Relationships
#     job_board = relationship("JobBoard", back_populates="schedule_configs")
#     scrape_jobs = relationship("ScrapeJob", back_populates="schedule_config")
#     
#     # Indexes
#     __table_args__ = (
#         Index('idx_schedule_enabled', 'is_enabled'),
#         Index('idx_schedule_next_run', 'next_run_at'),
#     )


# class ScrapeJob(Base):
#     """Individual scrape job execution"""
#     __tablename__ = 'autoscraper_scrape_jobs'
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     job_board_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_job_boards.id', ondelete='CASCADE'), nullable=False)
#     schedule_config_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_schedule_configs.id', ondelete='SET NULL'), nullable=True)
#     
#     # Job configuration
#     job_mode = Column(Enum(ScrapeJobMode), nullable=False)
#     status = Column(Enum(ScrapeJobStatus), default=ScrapeJobStatus.PENDING)
#     priority = Column(Integer, default=0)  # Higher number = higher priority
#     
#     # Execution details
#     started_at = Column(DateTime, nullable=True)
#     completed_at = Column(DateTime, nullable=True)
#     duration_seconds = Column(Integer, nullable=True)
#     
#     # Results
#     total_items_found = Column(Integer, default=0)
#     total_items_processed = Column(Integer, default=0)
#     total_items_created = Column(Integer, default=0)
#     total_items_updated = Column(Integer, default=0)
#     total_items_skipped = Column(Integer, default=0)
#     
#     # Error handling
#     error_message = Column(Text, nullable=True)
#     error_details = Column(JSON, nullable=True)
#     retry_count = Column(Integer, default=0)
#     
#     # Configuration snapshot
#     config_snapshot = Column(JSON, nullable=True)  # Snapshot of board config at execution time
#     
#     # Timestamps
#     created_at = Column(DateTime, server_default=func.now())
#     updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
#     
#     # Relationships
#     job_board = relationship("JobBoard", back_populates="scrape_jobs")
#     schedule_config = relationship("ScheduleConfig", back_populates="scrape_jobs")
#     scrape_runs = relationship("ScrapeRun", back_populates="scrape_job")
#     
#     # Indexes
#     __table_args__ = (
#         Index('idx_scrape_job_status', 'status'),
#         Index('idx_scrape_job_mode', 'job_mode'),
#         Index('idx_scrape_job_priority', 'priority'),
#         Index('idx_scrape_job_created', 'created_at'),
#     )


# class ScrapeRun(Base):
#     """Individual scrape run within a job"""
#     __tablename__ = 'autoscraper_scrape_runs'
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     scrape_job_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_scrape_jobs.id', ondelete='CASCADE'), nullable=False)
#     
#     # Run details
#     run_type = Column(String(50), nullable=False)  # 'rss', 'html', 'api'
#     url = Column(String(1000), nullable=False)
#     page_number = Column(Integer, default=1)
#     
#     # Execution details
#     started_at = Column(DateTime, nullable=True)
#     completed_at = Column(DateTime, nullable=True)
#     duration_seconds = Column(Integer, nullable=True)
#     
#     # Results
#     items_found = Column(Integer, default=0)
#     items_processed = Column(Integer, default=0)
#     items_created = Column(Integer, default=0)
#     items_updated = Column(Integer, default=0)
#     items_skipped = Column(Integer, default=0)
#     
#     # HTTP details
#     http_status_code = Column(Integer, nullable=True)
#     response_size_bytes = Column(Integer, nullable=True)
#     
#     # Error handling
#     error_message = Column(Text, nullable=True)
#     error_details = Column(JSON, nullable=True)
#     
#     # Timestamps
#     created_at = Column(DateTime, server_default=func.now())
#     updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
#     
#     # Relationships
#     scrape_job = relationship("ScrapeJob", back_populates="scrape_runs")
#     raw_jobs = relationship("RawJob", back_populates="scrape_run")
#     
#     # Indexes
#     __table_args__ = (
#         Index('idx_scrape_run_type', 'run_type'),
#         Index('idx_scrape_run_created', 'created_at'),
#     )


# class RawJob(Base):
#     """Raw job data extracted from scraping"""
#     __tablename__ = 'autoscraper_raw_jobs'
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     scrape_run_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_scrape_runs.id', ondelete='CASCADE'), nullable=False)
#     
#     # Raw data
#     title = Column(String(500), nullable=True)
#     company = Column(String(255), nullable=True)
#     location = Column(String(255), nullable=True)
#     description = Column(Text, nullable=True)
#     url = Column(String(1000), nullable=True)
#     salary = Column(String(255), nullable=True)
#     job_type = Column(String(100), nullable=True)
#     posted_date = Column(String(255), nullable=True)  # Raw string before parsing
#     
#     # Additional raw fields
#     raw_data = Column(JSON, nullable=True)  # Complete raw data as JSON
#     html_content = Column(Text, nullable=True)  # Raw HTML if needed
#     
#     # Processing status
#     is_processed = Column(Boolean, default=False)
#     is_duplicate = Column(Boolean, default=False)
#     checksum = Column(String(64), nullable=True)  # For deduplication
#     
#     # Timestamps
#     created_at = Column(DateTime, server_default=func.now())
#     updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
#     
#     # Relationships
#     scrape_run = relationship("ScrapeRun", back_populates="raw_jobs")
#     normalized_job = relationship("NormalizedJob", back_populates="raw_job", uselist=False)
#     
#     # Indexes
#     __table_args__ = (
#         Index('idx_raw_job_processed', 'is_processed'),
#         Index('idx_raw_job_duplicate', 'is_duplicate'),
#         Index('idx_raw_job_checksum', 'checksum'),
#         Index('idx_raw_job_created', 'created_at'),
#     )


# class NormalizedJob(Base):
#     """Normalized and cleaned job data"""
#     __tablename__ = 'autoscraper_normalized_jobs'
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     raw_job_id = Column(UUID(as_uuid=True), ForeignKey('autoscraper_raw_jobs.id', ondelete='CASCADE'), nullable=False)
#     
#     # Normalized fields
#     title = Column(String(500), nullable=False)
#     company = Column(String(255), nullable=True)
#     location = Column(String(255), nullable=True)
#     description = Column(Text, nullable=True)
#     url = Column(String(1000), nullable=True)
#     
#     # Parsed salary information
#     salary_min = Column(Integer, nullable=True)
#     salary_max = Column(Integer, nullable=True)
#     salary_currency = Column(String(10), default='USD')
#     salary_period = Column(String(20), nullable=True)  # hourly, monthly, yearly
#     
#     # Parsed job details
#     job_type = Column(String(100), nullable=True)  # full-time, part-time, contract
#     experience_level = Column(String(50), nullable=True)
#     remote_allowed = Column(Boolean, default=False)
#     
#     # Parsed dates
#     posted_date = Column(DateTime, nullable=True)
#     application_deadline = Column(DateTime, nullable=True)
#     
#     # Skills and requirements
#     skills_required = Column(JSON, nullable=True)  # Array of skills
#     education_required = Column(String(100), nullable=True)
#     
#     # Processing metadata
#     normalization_confidence = Column(Float, default=0.0)  # 0.0 to 1.0
#     normalization_method = Column(String(50), nullable=True)  # 'rule_based', 'ml', 'hybrid'
#     
#     # Integration status
#     is_published = Column(Boolean, default=False)
#     published_at = Column(DateTime, nullable=True)
#     job_post_id = Column(UUID(as_uuid=True), ForeignKey('job_posts.id', ondelete='SET NULL'), nullable=True)
#     
#     # Timestamps
#     created_at = Column(DateTime, server_default=func.now())
#     updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
#     
#     # Relationships
#     raw_job = relationship("RawJob", back_populates="normalized_job")
#     job_post = relationship("JobPost")  # Reference to main job_posts table
#     
#     # Indexes
#     __table_args__ = (
#         Index('idx_normalized_job_published', 'is_published'),
#         Index('idx_normalized_job_posted_date', 'posted_date'),
#         Index('idx_normalized_job_created', 'created_at'),
#     )


# class EngineState(Base):
#     """Global engine state management"""
#     __tablename__ = 'autoscraper_engine_state'
#     
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     
#     # Engine status
#     status = Column(Enum(EngineStatus), default=EngineStatus.IDLE)
#     last_heartbeat = Column(DateTime, nullable=True)
#     
#     # Current execution state
#     active_jobs_count = Column(Integer, default=0)
#     queued_jobs_count = Column(Integer, default=0)
#     total_jobs_processed = Column(Integer, default=0)
#     
#     # Performance metrics
#     average_job_duration = Column(Float, default=0.0)  # seconds
#     success_rate = Column(Float, default=0.0)  # 0.0 to 1.0
#     
#     # Resource usage
#     memory_usage_mb = Column(Float, default=0.0)
#     cpu_usage_percent = Column(Float, default=0.0)
#     
#     # Configuration
#     max_concurrent_jobs = Column(Integer, default=5)
#     maintenance_mode = Column(Boolean, default=False)
#     
#     # Error tracking
#     last_error_message = Column(Text, nullable=True)
#     last_error_at = Column(DateTime, nullable=True)
#     consecutive_errors = Column(Integer, default=0)
#     
#     # Timestamps
#     created_at = Column(DateTime, server_default=func.now())
#     updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
#     
#     # Indexes
#     __table_args__ = (
#         Index('idx_engine_status', 'status'),
#         Index('idx_engine_heartbeat', 'last_heartbeat'),
#     )