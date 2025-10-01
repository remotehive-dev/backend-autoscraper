"""Job-related models for the RemoteHive application"""

# SQLAlchemy imports commented out - using MongoDB instead
# from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, Float, JSON, UniqueConstraint, Table, Index
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import relationship
# from sqlalchemy.sql import func
# from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from enum import Enum as PyEnum
import uuid

# Import from MongoDB models to avoid duplication
# from backend.database.models import JobPost, Base  # Using MongoDB models instead
from backend.models.mongodb_models import JobPost
# Base is not needed for MongoDB models
from backend.models.scraping_session import ScrapingSession

# Re-export the models for easy importing
__all__ = ['JobPost', 'ScrapingSession']