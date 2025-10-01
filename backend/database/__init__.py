# Import from database.py to avoid circular imports
from backend.database.database import DatabaseManager, get_db_session, init_database, get_mongodb_session

# Alias for backward compatibility
get_database = get_mongodb_session
from backend.models.mongodb_models import (
    User, UserRole, JobSeeker, Employer, JobPost, JobApplication, 
    SeoSettings, Review, Ad, ContactSubmission, ContactInformation,
    PaymentGateway, Transaction, Refund, JobStatus, ApplicationStatus,
    ContactStatus, Priority
)
from backend.database.mongodb_models import LoginAttempt, UserSession, EmailVerificationToken, PasswordResetToken
from backend.models.tasks import TaskResult
from backend.models.scraping_session import ScrapingSession, ScrapingResult, SessionWebsite

__all__ = [
    'DatabaseManager',
    'get_db_session',
    'get_database',
    'init_database',
    'User',
    'UserRole',
    'JobSeeker', 
    'Employer',
    'JobPost',
    'JobApplication',
    'SeoSettings',
    'Review',
    'Ad',
    'ContactSubmission',
    'ContactInformation',
    'PaymentGateway',
    'Transaction',
    'Refund',
    'JobStatus',
    'ApplicationStatus',
    'ContactStatus',
    'Priority',
    'TaskResult',
    'ScrapingSession',
    'ScrapingResult',
    'SessionWebsite',
    'LoginAttempt',
    'UserSession',
    'EmailVerificationToken',
    'PasswordResetToken'
]