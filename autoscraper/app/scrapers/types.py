from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime


class ScrapingEngine(Enum):
    """Available scraping engines"""
    SCRAPY = "scrapy"
    BEAUTIFULSOUP = "beautifulsoup"
    SELENIUM = "selenium"
    PLAYWRIGHT = "playwright"


class ScrapingStatus(Enum):
    """Status of scraping operation"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Priority levels for job queue"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


@dataclass
class ScrapingResult:
    """Result of a scraping operation"""
    status: ScrapingStatus
    jobs: List[Dict[str, Any]]
    total_found: int
    pages_scraped: int
    errors: List[str]
    execution_time: float
    job_board_name: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class JobData:
    """Structured job data"""
    title: str
    company: str
    location: str
    description: str
    url: str
    salary: Optional[str] = None
    job_type: Optional[str] = None
    posted_date: Optional[datetime] = None
    requirements: List[str] = None
    benefits: List[str] = None
    source: str = ""
    
    def __post_init__(self):
        if self.requirements is None:
            self.requirements = []
        if self.benefits is None:
            self.benefits = []


@dataclass
class ScrapingMetrics:
    """Metrics for scraping operations"""
    total_jobs_scraped: int = 0
    successful_scrapes: int = 0
    failed_scrapes: int = 0
    average_scrape_time: float = 0.0
    total_errors: int = 0
    duplicate_jobs_filtered: int = 0
    last_scrape_time: Optional[datetime] = None
    
    def update_success(self, execution_time: float, jobs_count: int):
        """Update metrics for successful scrape"""
        self.successful_scrapes += 1
        self.total_jobs_scraped += jobs_count
        self.average_scrape_time = (
            (self.average_scrape_time * (self.successful_scrapes - 1) + execution_time) 
            / self.successful_scrapes
        )
        self.last_scrape_time = datetime.utcnow()
    
    def update_failure(self, error_count: int = 1):
        """Update metrics for failed scrape"""
        self.failed_scrapes += 1
        self.total_errors += error_count
        self.last_scrape_time = datetime.utcnow()


@dataclass
class QueuedJob:
    """Represents a job in the scraping queue"""
    id: str
    job_board_id: str
    job_board_name: str
    query: str
    location: str
    priority: JobPriority
    max_pages: int
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: ScrapingStatus = ScrapingStatus.PENDING
    result: Optional[ScrapingResult] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3