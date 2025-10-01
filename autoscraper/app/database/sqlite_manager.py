#!/usr/bin/env python3
"""
SQLite Database Manager for AutoScraper Service
Handles SQLite connections and database operations
"""

import os
from contextlib import contextmanager
from typing import Dict, Any, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

from config.settings import get_settings
from app.models.models import Base

settings = get_settings()


class SQLiteManager:
    """SQLite database manager for autoscraper service"""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
    
    def initialize(self):
        """Initialize SQLite database connection"""
        if self._initialized:
            return
        
        try:
            # Create SQLite engine
            database_url = settings.DATABASE_URL
            logger.info(f"Connecting to SQLite database: {database_url}")
            
            self.engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},  # Allow multiple threads
                echo=False  # Set to True for SQL debugging
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # Create all tables
            Base.metadata.create_all(bind=self.engine)
            
            self._initialized = True
            logger.info("SQLite database initialized for autoscraper service")
            
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get SQLite database session"""
        if not self._initialized:
            self.initialize()
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_session_sync(self) -> Session:
        """Get SQLite database session (synchronous)"""
        if not self._initialized:
            self.initialize()
        return self.SessionLocal()
    
    def close(self):
        """Close SQLite connections"""
        if self.engine:
            self.engine.dispose()
            logger.info("SQLite connections closed")
    
    def health_check(self) -> Dict[str, Any]:
        """Check SQLite database health"""
        try:
            with self.get_session() as session:
                # Test connection with a simple query
                result = session.execute(text("SELECT 1"))
                result.fetchone()
                
                return {
                    "status": "healthy",
                    "database_type": "sqlite",
                    "database_url": settings.DATABASE_URL
                }
        except Exception as e:
            logger.error(f"SQLite health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "database_type": "sqlite"
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get SQLite database metrics"""
        try:
            if not self._initialized:
                return {
                    "database_type": "sqlite",
                    "initialized": False,
                    "error": "Database not initialized"
                }
            
            with self.get_session() as session:
                # Get table counts
                from app.models.models import JobBoard, ScrapeJob, RawJob, NormalizedJob
                
                table_stats = {
                    "job_boards": session.query(JobBoard).count(),
                    "scrape_jobs": session.query(ScrapeJob).count(),
                    "raw_jobs": session.query(RawJob).count(),
                    "normalized_jobs": session.query(NormalizedJob).count()
                }
                
                return {
                    "database_type": "sqlite",
                    "database_url": settings.DATABASE_URL,
                    "table_stats": table_stats,
                    "initialized": self._initialized,
                    "connection_status": "connected" if self.engine else "disconnected"
                }
        except Exception as e:
            logger.error(f"Failed to get SQLite metrics: {e}")
            return {
                "error": str(e),
                "database_type": "sqlite",
                "initialized": self._initialized
            }


# Create global SQLite manager
sqlite_manager = SQLiteManager()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database session"""
    with sqlite_manager.get_session() as session:
        yield session


def get_db_session_context():
    """Get database session context manager"""
    return sqlite_manager.get_session()