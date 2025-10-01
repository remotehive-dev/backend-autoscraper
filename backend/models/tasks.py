from beanie import Document
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import Field, computed_field

from backend.core.enums import ScraperStatus

class TaskResult(Document):
    """Model for tracking Celery task execution results"""
    
    task_id: str = Field(..., index=True)
    status: ScraperStatus
    result: Optional[Dict[str, Any]] = None  # Task result data
    error_message: Optional[str] = None
    
    # Timing information
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Settings:
        name = "task_results"
    
    def __repr__(self):
        return f"<TaskResult(task_id='{self.task_id}', status='{self.status.value}')>"
    
    @computed_field
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate task duration in seconds"""
        if not self.started_at or not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task result to dictionary"""
        return {
            "task_id": self.task_id,
            "status": self.status.value if self.status else None,
            "result": self.result,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds
        }