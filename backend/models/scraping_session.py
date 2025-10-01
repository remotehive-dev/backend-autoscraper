from beanie import Document
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import Field, ConfigDict, computed_field
# from bson import ObjectId  # Removed to fix Pydantic schema generation

class SessionStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class WebsiteStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ScrapingSession(Document):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    session_id: str = Field(..., index=True)
    name: str
    status: SessionStatus = SessionStatus.CREATED
    
    # Website and progress tracking
    total_websites: int = 0
    processed_websites: int = 0
    successful_scrapes: int = 0
    failed_scrapes: int = 0
    
    # Configuration and data
    config: Optional[Dict[str, Any]] = None  # Scraping configuration
    website_ids: Optional[List[str]] = None  # List of website IDs to scrape
    memory_upload_id: Optional[str] = None  # Reference to memory upload
    
    # Timing information
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    resumed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Performance metrics
    average_response_time: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    
    # Results and logging
    results_summary: Optional[Dict[str, Any]] = None  # Summary of scraped data
    error_log: Optional[str] = None  # Error messages and logs
    
    # Metadata
    user_id: Optional[str] = None  # User who created the session
    website_id: Optional[str] = None  # Associated website
    tags: Optional[List[str]] = None  # Custom tags for organization
    notes: Optional[str] = None  # User notes
    
    class Settings:
        name = "scraping_sessions"
    # ml_training_data = relationship("MLTrainingData", back_populates="session")  # Avoiding circular import
    # metrics = relationship("ScrapingMetrics", back_populates="session")  # Avoiding circular import
    
    def __repr__(self):
        return f"<ScrapingSession(id='{self.id}', name='{self.name}', status='{self.status.value}')>"
    
    @computed_field
    @property
    def progress_percentage(self) -> float:
        """Calculate progress percentage"""
        if self.total_websites == 0:
            return 0.0
        return (self.processed_websites / self.total_websites) * 100
    
    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if session is currently active"""
        return self.status in [SessionStatus.RUNNING, SessionStatus.PAUSED]
    
    @computed_field
    @property
    def is_completed(self) -> bool:
        """Check if session is completed"""
        return self.status in [SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED]
    
    @computed_field
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate session duration in seconds"""
        if not self.started_at:
            return None
        
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status.value,
            'total_websites': self.total_websites,
            'processed_websites': self.processed_websites,
            'successful_scrapes': self.successful_scrapes,
            'failed_scrapes': self.failed_scrapes,
            'progress_percentage': self.progress_percentage,
            'config': self.config,
            'website_ids': self.website_ids,
            'memory_upload_id': self.memory_upload_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'paused_at': self.paused_at.isoformat() if self.paused_at else None,
            'resumed_at': self.resumed_at.isoformat() if self.resumed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'average_response_time': self.average_response_time,
            'success_rate': self.success_rate,
            'error_rate': self.error_rate,
            'results_summary': self.results_summary,
            'error_log': self.error_log,
            'user_id': self.user_id,
            'tags': self.tags,
            'notes': self.notes,
            'duration_seconds': self.duration_seconds,
            'is_active': self.is_active,
            'is_completed': self.is_completed
        }

class ScrapingResult(Document):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    session_id: str = Field(..., index=True)
    website_id: str
    
    # Request information
    url: str
    success: bool = False
    status_code: Optional[int] = None
    response_time: float = 0.0
    
    # Scraped data
    extracted_data: Optional[Dict[str, Any]] = None  # The actual scraped data
    selectors_used: Optional[List[str]] = None  # List of selectors that were used
    html_content: Optional[str] = None  # Partial HTML content for analysis
    
    # Error handling
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    retry_count: int = 0
    
    # Additional metadata
    screenshot_path: Optional[str] = None
    user_agent: Optional[str] = None
    scraping_method: Optional[str] = None  # 'requests' or 'selenium'
    
    # Timing
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Settings:
        name = "scraping_results"
    
    def __repr__(self):
        return f"<ScrapingResult(id={self.id}, session_id='{self.session_id}', url='{self.url}', success={self.success})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'website_id': self.website_id,
            'url': self.url,
            'success': self.success == 'true',  # Convert string back to boolean
            'status_code': self.status_code,
            'response_time': self.response_time,
            'extracted_data': self.extracted_data,
            'selectors_used': self.selectors_used,
            'html_content': self.html_content,
            'error_message': self.error_message,
            'error_type': self.error_type,
            'retry_count': self.retry_count,
            'screenshot_path': self.screenshot_path,
            'user_agent': self.user_agent,
            'scraping_method': self.scraping_method,
            'scraped_at': self.scraped_at.isoformat() if self.scraped_at else None
        }

class SessionWebsite(Document):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    session_id: str = Field(..., index=True)
    website_id: str
    
    # Processing status
    status: WebsiteStatus = WebsiteStatus.PENDING
    priority: int = 0  # Higher number = higher priority
    
    # Timing information
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Results reference
    result_id: Optional[str] = None  # Reference to ScrapingResult
    
    # Error handling and retries
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    
    class Settings:
        name = "session_websites"
    
    def __repr__(self):
        return f"<SessionWebsite(id={self.id}, session_id='{self.session_id}', website_id={self.website_id}, status='{self.status}')>"
    
    @computed_field
    @property
    def is_pending(self) -> bool:
        return self.status == WebsiteStatus.PENDING
    
    @computed_field
    @property
    def is_processing(self) -> bool:
        return self.status == WebsiteStatus.PROCESSING
    
    @computed_field
    @property
    def is_completed(self) -> bool:
        return self.status in [WebsiteStatus.COMPLETED, WebsiteStatus.FAILED]
    
    @computed_field
    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries and self.status == WebsiteStatus.FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'website_id': self.website_id,
            'status': self.status.value,
            'priority': self.priority,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result_id': self.result_id,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'last_error': self.last_error,
            'is_pending': self.is_pending,
            'is_processing': self.is_processing,
            'is_completed': self.is_completed,
            'can_retry': self.can_retry
        }