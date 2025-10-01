# Removed TaskResult import to avoid circular import
# from backend.tasks import TaskResult
from backend.models.scraping_session import ScrapingSession, ScrapingResult, SessionWebsite

__all__ = [
    # "TaskResult",  # Commented out to avoid circular import
    "ScrapingSession",
    "ScrapingResult",
    "SessionWebsite"
]