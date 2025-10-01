# Import all task modules to make them available to Celery
from backend.tasks import scraper
from backend.tasks import jobs
from backend.tasks import email
from backend.autoscraper import tasks as autoscraper

# Make tasks discoverable
__all__ = ['scraper', 'jobs', 'email', 'autoscraper']