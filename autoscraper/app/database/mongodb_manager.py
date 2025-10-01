#!/usr/bin/env python3
"""
MongoDB Connection Manager for AutoScraper Service
Handles MongoDB Atlas connections and database operations using Beanie ODM
"""

import os
import asyncio
from typing import Optional, List, Type, Any
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie, Document
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import logging
from contextlib import asynccontextmanager

# Import all document models
from app.models.mongodb_models import (
    JobBoard, ScheduleConfig, ScrapeJob, ScrapeRun, RawJob, NormalizedJob,
    EngineState, ScrapingMetrics, JobPosting, ScrapingSession
)

logger = logging.getLogger(__name__)


class AutoScraperMongoDBManager:
    """
    MongoDB connection manager for AutoScraper service using Beanie ODM
    Handles connection to MongoDB Atlas and document operations
    """
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database = None
        self.is_connected = False
        self.connection_string = None
        self.database_name = None
        
    async def connect(self, mongodb_url: str = None, database_name: str = None) -> bool:
        """
        Connect to MongoDB Atlas using Beanie ODM
        
        Args:
            mongodb_url: MongoDB connection URL (optional, will use settings if not provided)
            database_name: Database name (optional, will use settings if not provided)
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Import settings here to avoid circular imports
            from config.settings import get_settings
            settings = get_settings()
            
            # Use provided parameters or fall back to settings
            self.connection_string = mongodb_url or settings.MONGODB_URL
            
            self.database_name = database_name or settings.MONGODB_DATABASE_NAME
            
            # Create MongoDB client
            self.client = AsyncIOMotorClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=10000,  # 10 second connection timeout
                socketTimeoutMS=20000,   # 20 second socket timeout
                maxPoolSize=50,          # Maximum connection pool size
                minPoolSize=5,           # Minimum connection pool size
                retryWrites=True
            )
            
            # Get database
            self.database = self.client[self.database_name]
            
            # Test connection
            await self.client.admin.command('ping')
            
            # Initialize Beanie with document models
            await init_beanie(
                database=self.database,
                document_models=[
                    JobBoard, ScheduleConfig, ScrapeJob, ScrapeRun, RawJob, NormalizedJob,
                    EngineState, ScrapingMetrics, JobPosting, ScrapingSession
                ]
            )
            
            self.is_connected = True
            logger.info(f"Successfully connected to MongoDB Atlas database: {self.database_name}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB Atlas: {e}")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """
        Disconnect from MongoDB Atlas
        """
        if self.client:
            self.client.close()
            self.is_connected = False
            logger.info("Disconnected from MongoDB Atlas")
    
    async def test_connection(self) -> dict:
        """
        Test MongoDB connection and return status information
        
        Returns:
            dict: Connection status and database information
        """
        try:
            if not self.client:
                return {
                    "connected": False,
                    "error": "No client connection established"
                }
            
            # Test ping
            ping_result = await self.client.admin.command('ping')
            
            # Get server info
            server_info = await self.client.server_info()
            
            # Get database stats
            db_stats = await self.database.command("dbStats")
            
            # List collections
            collections = await self.database.list_collection_names()
            
            return {
                "connected": True,
                "database_name": self.database_name,
                "server_version": server_info.get("version"),
                "ping_ok": ping_result.get("ok") == 1,
                "collections_count": len(collections),
                "collections": collections,
                "database_size_mb": round(db_stats.get("dataSize", 0) / (1024 * 1024), 2),
                "storage_size_mb": round(db_stats.get("storageSize", 0) / (1024 * 1024), 2),
                "indexes_count": db_stats.get("indexes", 0),
                "objects_count": db_stats.get("objects", 0)
            }
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                "connected": False,
                "error": str(e)
            }
    
    async def create_indexes(self):
        """
        Create additional custom indexes for better performance
        """
        try:
            # Job boards indexes - handle existing indexes gracefully
            try:
                await self.database.job_boards.create_index([("name", 1)], unique=True)
            except Exception as e:
                if "already exists" in str(e) or "duplicate key" in str(e):
                    logger.info("Job boards name index already exists, skipping")
                else:
                    logger.warning(f"Failed to create job boards name index: {e}")
            
            try:
                await self.database.job_boards.create_index([("type", 1), ("is_active", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Job boards type/active index already exists, skipping")
                else:
                    logger.warning(f"Failed to create job boards type/active index: {e}")
            
            # Schedule configs indexes - handle existing indexes gracefully
            try:
                await self.database.schedule_configs.create_index([("name", 1)], unique=True)
            except Exception as e:
                if "already exists" in str(e) or "duplicate key" in str(e):
                    logger.info("Schedule configs name index already exists, skipping")
            
            try:
                await self.database.schedule_configs.create_index([("is_active", 1), ("next_run_at", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Schedule configs active/next_run index already exists, skipping")
            
            # Scrape jobs indexes - handle existing indexes gracefully
            try:
                await self.database.scrape_jobs.create_index([("job_id", 1)], unique=True)
            except Exception as e:
                if "already exists" in str(e) or "duplicate key" in str(e):
                    logger.info("Scrape jobs job_id index already exists, skipping")
            
            try:
                await self.database.scrape_jobs.create_index([("status", 1), ("priority", -1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Scrape jobs status/priority index already exists, skipping")
            
            try:
                await self.database.scrape_jobs.create_index([("job_board_id", 1), ("status", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Scrape jobs job_board_id/status index already exists, skipping")
            
            try:
                await self.database.scrape_jobs.create_index([("scheduled_at", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Scrape jobs scheduled_at index already exists, skipping")
            
            # Scrape runs indexes - handle existing indexes gracefully
            try:
                await self.database.scrape_runs.create_index([("run_id", 1)], unique=True)
            except Exception as e:
                if "already exists" in str(e) or "duplicate key" in str(e):
                    logger.info("Scrape runs run_id index already exists, skipping")
            
            try:
                await self.database.scrape_runs.create_index([("scrape_job_id", 1), ("page_number", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Scrape runs scrape_job_id/page_number index already exists, skipping")
            
            try:
                await self.database.scrape_runs.create_index([("status", 1), ("created_at", -1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Scrape runs status/created_at index already exists, skipping")
            
            # Raw jobs indexes - handle existing indexes gracefully
            try:
                await self.database.raw_jobs.create_index([("job_id", 1)], unique=True)
            except Exception as e:
                if "already exists" in str(e) or "duplicate key" in str(e):
                    logger.info("Raw jobs job_id index already exists, skipping")
                else:
                    logger.warning(f"Failed to create raw jobs job_id index: {e}")
            
            try:
                await self.database.raw_jobs.create_index([("scrape_run_id", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Raw jobs scrape_run_id index already exists, skipping")
                else:
                    logger.warning(f"Failed to create raw jobs scrape_run_id index: {e}")
            
            try:
                await self.database.raw_jobs.create_index([("job_board_id", 1), ("is_processed", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Raw jobs job_board_id/is_processed index already exists, skipping")
                else:
                    logger.warning(f"Failed to create raw jobs job_board_id/is_processed index: {e}")
            
            try:
                await self.database.raw_jobs.create_index([("content_hash", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Raw jobs content_hash index already exists, skipping")
                else:
                    logger.warning(f"Failed to create raw jobs content_hash index: {e}")
            
            try:
                await self.database.raw_jobs.create_index([("url_hash", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Raw jobs url_hash index already exists, skipping")
                else:
                    logger.warning(f"Failed to create raw jobs url_hash index: {e}")
            
            # Normalized jobs indexes - handle existing indexes gracefully
            try:
                await self.database.normalized_jobs.create_index([("job_id", 1)], unique=True)
            except Exception as e:
                if "already exists" in str(e) or "duplicate key" in str(e):
                    logger.info("Normalized jobs job_id index already exists, skipping")
            
            try:
                await self.database.normalized_jobs.create_index([("raw_job_id", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Normalized jobs raw_job_id index already exists, skipping")
            
            try:
                await self.database.normalized_jobs.create_index([("job_board_id", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Normalized jobs job_board_id index already exists, skipping")
            
            try:
                await self.database.normalized_jobs.create_index([("content_hash", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Normalized jobs content_hash index already exists, skipping")
            
            try:
                await self.database.normalized_jobs.create_index([("exported_to_main_db", 1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Normalized jobs exported_to_main_db index already exists, skipping")
            
            try:
                await self.database.normalized_jobs.create_index([("title", "text"), ("company", "text"), ("description", "text")])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Normalized jobs text search index already exists, skipping")
            
            # Engine states indexes - handle existing indexes gracefully
            try:
                await self.database.engine_states.create_index([("engine_name", 1)], unique=True)
            except Exception as e:
                if "already exists" in str(e) or "duplicate key" in str(e):
                    logger.info("Engine states engine_name index already exists, skipping")
            
            try:
                await self.database.engine_states.create_index([("is_active", 1), ("last_heartbeat", -1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Engine states is_active/last_heartbeat index already exists, skipping")
            
            # Scraping metrics indexes - handle existing indexes gracefully
            try:
                await self.database.scraping_metrics.create_index([("date", 1), ("job_board_id", 1)], unique=True)
            except Exception as e:
                if "already exists" in str(e) or "duplicate key" in str(e):
                    logger.info("Scraping metrics date/job_board_id index already exists, skipping")
            
            try:
                await self.database.scraping_metrics.create_index([("date", -1)])
            except Exception as e:
                if "already exists" in str(e):
                    logger.info("Scraping metrics date index already exists, skipping")
            
            logger.info("Successfully created custom indexes for AutoScraper service")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
    
    async def get_collection_stats(self) -> dict:
        """
        Get statistics for all collections
        
        Returns:
            dict: Collection statistics
        """
        try:
            collections = await self.database.list_collection_names()
            stats = {}
            
            for collection_name in collections:
                collection_stats = await self.database.command("collStats", collection_name)
                stats[collection_name] = {
                    "count": collection_stats.get("count", 0),
                    "size_mb": round(collection_stats.get("size", 0) / (1024 * 1024), 2),
                    "storage_size_mb": round(collection_stats.get("storageSize", 0) / (1024 * 1024), 2),
                    "indexes": collection_stats.get("nindexes", 0),
                    "avg_obj_size": collection_stats.get("avgObjSize", 0)
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}
    
    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for MongoDB transactions
        
        Usage:
            async with autoscraper_mongodb_manager.transaction() as session:
                # Perform operations within transaction
                await JobBoard.find_one({"name": "Indeed"}).session(session)
        """
        async with await self.client.start_session() as session:
            async with session.start_transaction():
                try:
                    yield session
                except Exception:
                    await session.abort_transaction()
                    raise
    
    async def cleanup_old_data(self, days_to_keep: int = 30):
        """
        Clean up old scraping data to manage storage
        
        Args:
            days_to_keep: Number of days of data to keep
        """
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        try:
            # Clean up old scrape runs
            deleted_runs = await ScrapeRun.find(
                ScrapeRun.created_at < cutoff_date
            ).delete()
            
            # Clean up old raw jobs
            deleted_raw = await RawJob.find(
                RawJob.created_at < cutoff_date,
                RawJob.is_processed == True
            ).delete()
            
            # Clean up old scraping metrics (keep aggregated data longer)
            metrics_cutoff = datetime.utcnow() - timedelta(days=days_to_keep * 3)
            deleted_metrics = await ScrapingMetrics.find(
                ScrapingMetrics.date < metrics_cutoff
            ).delete()
            
            logger.info(f"Cleanup completed: {deleted_runs.deleted_count} runs, {deleted_raw.deleted_count} raw jobs, {deleted_metrics.deleted_count} metrics")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    async def get_scraping_summary(self) -> dict:
        """
        Get a summary of scraping activities
        
        Returns:
            dict: Scraping summary statistics
        """
        try:
            # Count active job boards
            active_boards = await JobBoard.find(JobBoard.is_active == True).count()
            
            # Count active schedules
            active_schedules = await ScheduleConfig.find(ScheduleConfig.is_active == True).count()
            
            # Count jobs by status
            pending_jobs = await ScrapeJob.find(ScrapeJob.status == "pending").count()
            running_jobs = await ScrapeJob.find(ScrapeJob.status == "running").count()
            completed_jobs = await ScrapeJob.find(ScrapeJob.status == "completed").count()
            failed_jobs = await ScrapeJob.find(ScrapeJob.status == "failed").count()
            
            # Count raw and normalized jobs
            total_raw_jobs = await RawJob.find().count()
            processed_raw_jobs = await RawJob.find(RawJob.is_processed == True).count()
            total_normalized_jobs = await NormalizedJob.find().count()
            exported_jobs = await NormalizedJob.find(NormalizedJob.exported_to_main_db == True).count()
            
            # Get engine status
            active_engines = await EngineState.find(EngineState.status == "running").count()
            
            return {
                "job_boards": {
                    "active": active_boards,
                    "total": await JobBoard.find().count()
                },
                "schedules": {
                    "active": active_schedules,
                    "total": await ScheduleConfig.find().count()
                },
                "scrape_jobs": {
                    "pending": pending_jobs,
                    "running": running_jobs,
                    "completed": completed_jobs,
                    "failed": failed_jobs,
                    "total": pending_jobs + running_jobs + completed_jobs + failed_jobs
                },
                "raw_jobs": {
                    "total": total_raw_jobs,
                    "processed": processed_raw_jobs,
                    "unprocessed": total_raw_jobs - processed_raw_jobs
                },
                "normalized_jobs": {
                    "total": total_normalized_jobs,
                    "exported": exported_jobs,
                    "pending_export": total_normalized_jobs - exported_jobs
                },
                "engines": {
                    "active": active_engines,
                    "total": await EngineState.find().count()
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get scraping summary: {e}")
            return {}
    
    def get_client(self) -> AsyncIOMotorClient:
        """
        Get the MongoDB client instance
        
        Returns:
            AsyncIOMotorClient: The MongoDB client
        """
        return self.client
    
    def get_database(self):
        """
        Get the database instance
        
        Returns:
            Database: The MongoDB database
        """
        return self.database
    
    def is_healthy(self) -> bool:
        """
        Check if the connection is healthy
        
        Returns:
            bool: True if connection is healthy
        """
        return self.is_connected and self.client is not None


# Global MongoDB manager instance for AutoScraper service
autoscraper_mongodb_manager = AutoScraperMongoDBManager()


async def get_autoscraper_mongodb_manager() -> AutoScraperMongoDBManager:
    """
    Dependency function to get AutoScraper MongoDB manager instance
    
    Returns:
        AutoScraperMongoDBManager: The global AutoScraper MongoDB manager instance
    """
    if not autoscraper_mongodb_manager.is_connected:
        await autoscraper_mongodb_manager.connect()
    return autoscraper_mongodb_manager


async def init_autoscraper_mongodb():
    """
    Initialize MongoDB connection for AutoScraper service on application startup
    """
    success = await autoscraper_mongodb_manager.connect()
    if success:
        await autoscraper_mongodb_manager.create_indexes()
        logger.info("AutoScraper MongoDB initialization completed successfully")
    else:
        logger.error("Failed to initialize AutoScraper MongoDB connection")
        raise Exception("AutoScraper MongoDB connection failed")


async def close_autoscraper_mongodb():
    """
    Close MongoDB connection for AutoScraper service on application shutdown
    """
    await autoscraper_mongodb_manager.disconnect()
    logger.info("AutoScraper MongoDB connection closed")