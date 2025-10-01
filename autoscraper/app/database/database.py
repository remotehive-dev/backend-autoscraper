#!/usr/bin/env python3
"""
Database Manager for AutoScraper Service
Handles SQLite connections and database operations
"""

import time
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any
from loguru import logger

from config.settings import get_settings
from .mongodb_manager import autoscraper_mongodb_manager, init_autoscraper_mongodb, get_autoscraper_mongodb_manager, close_autoscraper_mongodb
from app.models.mongodb_models import JobBoard

settings = get_settings()
try:
    from app.utils.metrics import metrics
except ImportError:
    metrics = None


class DatabaseManager:
    """
    Database manager that handles MongoDB connections for AutoScraper service
    Configured to use MongoDB Atlas exclusively
    """
    
    def __init__(self):
        self.mongodb_manager = autoscraper_mongodb_manager
        self._initialized = False
        
    async def initialize(self):
        """Initialize database connections"""
        # Initialize MongoDB Atlas
        await init_autoscraper_mongodb()
        self._initialized = True
        logger.info("DatabaseManager initialized with MongoDB Atlas")
    
    async def get_mongodb_manager(self):
        """Get MongoDB manager"""
        if not self._initialized:
            await self.initialize()
        return self.mongodb_manager
    
    async def get_database(self):
        """Get MongoDB manager (compatibility method)"""
        if not self._initialized:
            await self.initialize()
        return self.mongodb_manager
    
    async def close(self):
        """Close database connections"""
        await close_autoscraper_mongodb()
    
    async def health_check(self) -> dict:
        """Check health of database connections"""
        mongodb_health = await autoscraper_mongodb_manager.test_connection()
        
        return {
            "mongodb": mongodb_health,
            "status": "healthy" if mongodb_health.get("connected") else "unhealthy"
        }
    
    async def get_metrics(self) -> dict:
        """Get database metrics"""
        mongodb_stats = await autoscraper_mongodb_manager.get_collection_stats()
        scraping_summary = await autoscraper_mongodb_manager.get_scraping_summary()
        
        return {
            "mongodb": mongodb_stats,
            "scraping_summary": scraping_summary
        }


# Create global database manager
db_manager = DatabaseManager()


async def get_mongodb_manager():
    """FastAPI dependency to get MongoDB manager"""
    return await get_autoscraper_mongodb_manager()


class MongoDBRetryMixin:
    """Mixin for MongoDB operations with retry logic"""
    
    async def execute_with_retry(self, operation, max_retries: int = 3, delay: float = 1.0):
        """Execute MongoDB operation with retry logic"""
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return await operation()
            except Exception as e:
                last_exception = e
                logger.warning(f"MongoDB operation failed (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"MongoDB operation failed after {max_retries} attempts")
                    raise last_exception


class MongoDBOperationMixin:
    """Mixin for MongoDB operation management"""
    
    async def with_session(self, operation):
        """Execute operation with MongoDB session (for transactions if needed)"""
        try:
            # For simple operations, we don't need sessions
            # MongoDB handles atomicity at document level
            return await operation()
        except Exception as e:
            logger.error(f"MongoDB operation failed: {e}")
            raise


class TransactionManager:
    """Context manager for MongoDB operations"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.mongodb_manager = None
    
    async def __aenter__(self):
        self.mongodb_manager = await self.db_manager.get_mongodb_manager()
        return self.mongodb_manager
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # MongoDB operations are atomic at document level
        if exc_type is not None:
            logger.error(f"MongoDB operation error: {exc_val}")
        return False  # Don't suppress exceptions


async def ensure_indexes():
    """Ensure MongoDB indexes are created"""
    try:
        mongodb_manager = await get_mongodb_manager()
        await mongodb_manager.create_indexes()
        logger.info("MongoDB indexes ensured successfully")
    except Exception as e:
        logger.error(f"Failed to ensure MongoDB indexes: {e}")
        raise


# Cleanup function for graceful shutdown
async def cleanup_database():
    """Cleanup database connections on shutdown"""
    await db_manager.close()