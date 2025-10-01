#!/usr/bin/env python3
"""
MongoDB Connection Manager
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
from backend.models.mongodb_models import (
    User, ContactSubmission, ContactInformation, SeoSettings, Review, Ad,
    JobSeeker, Employer, JobPost, JobApplication, PaymentGateway, Transaction, Refund,
    SavedJob, EmailVerificationToken, PasswordResetToken
)
from backend.models.tasks import TaskResult
from backend.models.scraping_session import ScrapingSession, ScrapingResult, SessionWebsite
from backend.database.mongodb_models import LoginAttempt, UserSession

logger = logging.getLogger(__name__)


class MongoDBManager:
    """
    MongoDB connection manager using Beanie ODM
    Handles connection to MongoDB Atlas and document operations
    """
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database = None
        self.is_connected = False
        self.connection_string = None
        self.database_name = None
        
    async def connect(self, connection_string: Optional[str] = None, database_name: Optional[str] = None) -> bool:
        """
        Connect to MongoDB Atlas
        
        Args:
            connection_string: MongoDB connection string (defaults to env var)
            database_name: Database name (defaults to env var)
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Use provided connection string or get from environment
            self.connection_string = connection_string or os.getenv("MONGODB_URL")
            
            if not self.connection_string:
                raise ValueError("MONGODB_URL environment variable is required")
            
            self.database_name = database_name or os.getenv("MONGODB_DATABASE_NAME", "remotehive_main")
            
            logger.info(f"Connecting to MongoDB Atlas database: {self.database_name}")
            logger.info(f"Connection string: {self.connection_string[:50]}...")
            
            # Parse connection string to determine if it's Atlas or local
            is_atlas = "mongodb+srv://" in self.connection_string or "mongodb.net" in self.connection_string
            
            if is_atlas:
                # Atlas connection settings - use certifi for proper SSL certificates
                logger.info("Connecting to MongoDB Atlas")
                import certifi
                self.client = AsyncIOMotorClient(
                    self.connection_string,
                    serverSelectionTimeoutMS=30000,
                    connectTimeoutMS=30000,
                    socketTimeoutMS=30000,
                    maxPoolSize=50,
                    minPoolSize=5,
                    maxIdleTimeMS=30000,
                    retryWrites=True,
                    tls=True,
                    tlsCAFile=certifi.where()  # Use certifi CA bundle for proper SSL verification
                )
            else:
                # Local MongoDB connection settings
                logger.info("Connecting to local MongoDB instance")
                self.client = AsyncIOMotorClient(
                    self.connection_string,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=5000,
                    maxPoolSize=10,
                    minPoolSize=1
                )
            
            # Get database
            self.database = self.client[self.database_name]
            
            # Test connection
            logger.info("Testing MongoDB connection...")
            await self.client.admin.command('ping')
            logger.info("MongoDB ping successful")
            
            # Initialize Beanie with document models
            await init_beanie(
                database=self.database,
                document_models=[
                    User, ContactSubmission, ContactInformation, SeoSettings, Review, Ad,
                    JobSeeker, Employer, JobPost, JobApplication, PaymentGateway, Transaction, Refund,
                    SavedJob, TaskResult, ScrapingSession, ScrapingResult, SessionWebsite,
                    LoginAttempt, UserSession, EmailVerificationToken, PasswordResetToken
                ]
            )
            
            self.is_connected = True
            connection_type = "MongoDB Atlas" if is_atlas else "local MongoDB"
            logger.info(f"Successfully connected to {connection_type} database: {self.database_name}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
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
            # User indexes
            await self.database.users.create_index([("email", 1)], unique=True)
            await self.database.users.create_index([("clerk_user_id", 1)], unique=True, sparse=True)
            
            # Job posts indexes
            await self.database.job_posts.create_index([("employer_id", 1), ("status", 1)])
            await self.database.job_posts.create_index([("created_at", -1)])
            await self.database.job_posts.create_index([("published_at", -1)])
            await self.database.job_posts.create_index([("is_remote", 1), ("status", 1)])
            
            # Job applications indexes
            await self.database.job_applications.create_index([("job_post_id", 1), ("job_seeker_id", 1)], unique=True)
            await self.database.job_applications.create_index([("status", 1), ("created_at", -1)])
            
            # Employer indexes
            await self.database.employers.create_index([("company_email", 1)], unique=True)
            await self.database.employers.create_index([("employer_number", 1)], unique=True, sparse=True)
            
            # Job seeker indexes
            await self.database.job_seekers.create_index([("user_id", 1)], unique=True)
            
            # Contact submissions indexes
            await self.database.contact_submissions.create_index([("status", 1), ("created_at", -1)])
            
            # Scraper indexes
            await self.database.scraper_configs.create_index([("user_id", 1), ("is_active", 1)])
            await self.database.scraper_logs.create_index([("scraper_config_id", 1), ("created_at", -1)])
            
            logger.info("Successfully created custom indexes")
            
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
            async with mongodb_manager.transaction() as session:
                # Perform operations within transaction
                await User.find_one({"email": "test@example.com"}).session(session)
        """
        async with await self.client.start_session() as session:
            async with session.start_transaction():
                try:
                    yield session
                except Exception:
                    await session.abort_transaction()
                    raise
    
    async def drop_database(self, confirm_database_name: str):
        """
        Drop the entire database (use with extreme caution)
        
        Args:
            confirm_database_name: Must match the actual database name for safety
        """
        if confirm_database_name != self.database_name:
            raise ValueError(f"Database name confirmation failed. Expected: {self.database_name}")
        
        await self.client.drop_database(self.database_name)
        logger.warning(f"Database {self.database_name} has been dropped")
    
    async def backup_collection(self, collection_name: str, output_file: str):
        """
        Backup a collection to a JSON file
        
        Args:
            collection_name: Name of the collection to backup
            output_file: Path to output JSON file
        """
        import json
        from bson import json_util
        
        collection = self.database[collection_name]
        documents = []
        
        async for doc in collection.find():
            documents.append(doc)
        
        with open(output_file, 'w') as f:
            json.dump(documents, f, default=json_util.default, indent=2)
        
        logger.info(f"Backed up {len(documents)} documents from {collection_name} to {output_file}")
    
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
    
    async def health_check(self) -> dict:
        """
        Comprehensive health check for MongoDB connection
        
        Returns:
            dict: Health status and connection information
        """
        import time
        
        try:
            start_time = time.time()
            
            # Test connection
            connection_status = await self.test_connection()
            
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            if connection_status.get("connected", False):
                return {
                    "status": "healthy",
                    "database_type": "mongodb",
                    "response_time_ms": round(response_time, 2),
                    "database_name": self.database_name,
                    "connection_info": connection_status
                }
            else:
                return {
                    "status": "unhealthy",
                    "database_type": "mongodb",
                    "response_time_ms": round(response_time, 2),
                    "error": connection_status.get("error", "Unknown connection error")
                }
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "database_type": "mongodb",
                "error": str(e)
            }
    
    def get_connection_info(self) -> dict:
        """
        Get connection information
        
        Returns:
            dict: Connection information
        """
        return {
            "database_name": self.database_name,
            "is_connected": self.is_connected,
            "connection_string": self.connection_string if self.connection_string else "Not set"
        }


# Global MongoDB manager instance
mongodb_manager = MongoDBManager()


async def get_mongodb_manager() -> MongoDBManager:
    """
    Dependency function to get MongoDB manager instance
    
    Returns:
        MongoDBManager: The global MongoDB manager instance
    """
    if not mongodb_manager.is_connected:
        await mongodb_manager.connect()
    return mongodb_manager


async def init_mongodb():
    """
    Initialize MongoDB connection on application startup
    """
    # Force disconnect any existing connection first
    if mongodb_manager.is_connected:
        await mongodb_manager.disconnect()
        logger.info("Disconnected existing MongoDB connection")
    
    # Connect with fresh environment variables
    success = await mongodb_manager.connect()
    if success:
        await mongodb_manager.create_indexes()
        logger.info("MongoDB initialization completed successfully")
    else:
        logger.error("Failed to initialize MongoDB connection")
        raise Exception("MongoDB connection failed")


async def close_mongodb():
    """
    Close MongoDB connection on application shutdown
    """
    await mongodb_manager.disconnect()
    logger.info("MongoDB connection closed")