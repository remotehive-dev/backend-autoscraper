import os
import time
import threading
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging
from typing import Generator, Dict, Any, Optional

# Import MongoDB manager
from backend.database.mongodb_manager import MongoDBManager
from backend.core.config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """MongoDB database manager for RemoteHive application."""
    def __init__(self):
        self.mongodb_manager = None  # Will be created during initialization
        self._metrics = {
            'total_connections': 0,
            'failed_connections': 0,
            'query_count': 0,
            'slow_queries': 0,
            'last_health_check': None,
            'uptime_start': datetime.now()
        }
        self._lock = threading.Lock()
        self._initialized = False
    

    
    async def initialize(self) -> None:
        """Initialize MongoDB connection with current environment variables."""
        if self._initialized:
            logger.info("Database manager already initialized")
            return
        
        try:
            # Debug logging
            logger.info(f"Initializing with MONGODB_URL: {settings.MONGODB_URL[:50]}...")
            logger.info(f"Initializing with MONGODB_DATABASE_NAME: {settings.MONGODB_DATABASE_NAME}")
            
            # Create a fresh MongoDB manager instance
            self.mongodb_manager = MongoDBManager()
            
            # Connect using current environment variables from settings
            success = await self.mongodb_manager.connect(
                connection_string=settings.MONGODB_URL,
                database_name=settings.MONGODB_DATABASE_NAME
            )
            
            if not success:
                raise ConnectionError("Failed to connect to MongoDB")
            
            self._initialized = True
            logger.info(f"Database manager initialized successfully with URL: {settings.MONGODB_URL[:50]}...")
            
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {e}")
            self._initialized = False
            raise
    
    async def create_tables(self):
        """Initialize MongoDB collections and indexes."""
        if not self.mongodb_manager:
            raise Exception("MongoDB manager not initialized. Call initialize() first.")
        try:
            await self.mongodb_manager.create_indexes()
            logger.info("MongoDB collections and indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating MongoDB collections: {e}")
            raise
    
    async def drop_tables(self):
        """Drop MongoDB database."""
        if not self.mongodb_manager:
            raise Exception("MongoDB manager not initialized. Call initialize() first.")
        try:
            await self.mongodb_manager.drop_database()
            logger.info("MongoDB database dropped successfully")
        except Exception as e:
            logger.error(f"Error dropping MongoDB database: {e}")
            raise
    
    def get_session(self):
        """Get MongoDB database instance with connection tracking."""
        if not self.mongodb_manager:
            raise Exception("MongoDB manager not initialized. Call initialize() first.")
        
        with self._lock:
            self._metrics['total_connections'] += 1
        
        try:
            db = self.mongodb_manager.get_database()
            if db is None:
                with self._lock:
                    self._metrics['failed_connections'] += 1
                raise Exception("Failed to get MongoDB database")
            return db
        except Exception as e:
            with self._lock:
                self._metrics['failed_connections'] += 1
            logger.error(f"Error getting MongoDB session: {e}")
            raise
    

    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around MongoDB operations."""
        db = None
        try:
            db = self.get_session()
            with self._lock:
                self._metrics['query_count'] += 1
            yield db
        except Exception as e:
            logger.error(f"MongoDB session error: {e}")
            # MongoDB doesn't have traditional rollback, but we can log the error
            raise
        finally:
            # MongoDB connections are managed by the driver
            # No explicit cleanup needed for database object
            if db:
                logger.debug("MongoDB session completed")
    

    
    async def health_check(self) -> Dict[str, Any]:
        """Enhanced health check for MongoDB connection."""
        if not self.mongodb_manager:
            return {
                'status': 'unhealthy',
                'error': 'MongoDB manager not initialized',
                'timestamp': time.time(),
                'metrics': self.get_metrics()
            }
        
        try:
            start_time = time.time()
            
            # Test MongoDB connectivity
            health_status = await self.mongodb_manager.test_connection()
            
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Get performance metrics
            metrics = self.get_metrics()
            
            with self._lock:
                self._metrics['last_health_check'] = datetime.now()
            
            return {
                'status': 'healthy' if health_status.get('connected', False) else 'unhealthy',
                'response_time_ms': round(response_time, 2),
                'mongodb_status': health_status,
                'metrics': metrics,
                'timestamp': time.time(),
                'database_type': 'mongodb'
            }
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time(),
                'metrics': self.get_metrics()
            }
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get MongoDB connection statistics for monitoring."""
        if not self.mongodb_manager:
            return {}
        
        try:
            # MongoDB doesn't have traditional connection pools like SQLAlchemy
            # But we can return connection info from the client
            client = self.mongodb_manager.get_client()
            if client:
                return {
                    'active_connections': len(client.nodes),
                    'database_name': self.mongodb_manager.get_database().name,
                    'client_info': str(client.address) if hasattr(client, 'address') else 'N/A'
                }
            return {}
        except Exception as e:
            logger.warning(f"Could not get MongoDB connection stats: {e}")
            return {}
    
    def optimize_connection(self, db) -> None:
        """Optimize MongoDB connection settings for performance."""
        try:
            # MongoDB optimization is handled at the client level
            # Most optimizations are done during connection setup
            logger.debug("MongoDB connection optimization handled at client level")
        except Exception as e:
            logger.warning(f"Could not optimize MongoDB connection: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get database performance metrics."""
        with self._lock:
            uptime = datetime.now() - self._metrics['uptime_start']
            return {
                'total_connections': self._metrics['total_connections'],
                'failed_connections': self._metrics['failed_connections'],
                'query_count': self._metrics['query_count'],
                'slow_queries': self._metrics['slow_queries'],
                'success_rate': (
                    (self._metrics['total_connections'] - self._metrics['failed_connections']) / 
                    max(self._metrics['total_connections'], 1)
                ) * 100,
                'uptime_seconds': uptime.total_seconds(),
                'last_health_check': self._metrics['last_health_check'].isoformat() if self._metrics['last_health_check'] else None
            }
    
    def reset_metrics(self) -> None:
        """Reset performance metrics (useful for monitoring)."""
        with self._lock:
            self._metrics.update({
                'total_connections': 0,
                'failed_connections': 0,
                'query_count': 0,
                'slow_queries': 0,
                'uptime_start': datetime.now()
            })
        logger.info("Database metrics reset")
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get detailed MongoDB connection information."""
        if not self.mongodb_manager:
            return {
                'database_type': 'mongodb',
                'database_name': 'N/A',
                'client_address': 'N/A',
                'connection_string': 'Not initialized',
                'status': 'Not initialized'
            }
        
        try:
            client = self.mongodb_manager.get_client()
            db = self.mongodb_manager.get_database()
            return {
                'database_type': 'mongodb',
                'database_name': db.name if db else 'N/A',
                'client_address': str(client.address) if client and hasattr(client, 'address') else 'N/A',
                'connection_string': 'mongodb://***:***@***',  # Masked for security
                'is_connected': client is not None
            }
        except Exception as e:
            logger.warning(f"Could not get MongoDB connection info: {e}")
            return {'error': str(e)}
    
    async def execute_maintenance(self) -> Dict[str, Any]:
        """Execute MongoDB maintenance tasks."""
        try:
            results = {}
            
            # Get database statistics
            db = self.mongodb_manager.get_database()
            if db:
                stats = await db.command('dbStats')
                results['database_size'] = stats.get('dataSize', 0)
                results['index_size'] = stats.get('indexSize', 0)
                results['collections'] = stats.get('collections', 0)
                results['indexes'] = stats.get('indexes', 0)
                
            # MongoDB doesn't need explicit maintenance like ANALYZE
            # But we can check index usage and suggest optimizations
            results['maintenance_type'] = 'mongodb_stats'
            results['status'] = 'completed'
                    
            logger.info(f"MongoDB maintenance completed: {results}")
            return results
        except Exception as e:
            logger.error(f"MongoDB maintenance failed: {e}")
            return {'error': str(e)}
    
    async def close_all_connections(self) -> None:
        """Close all MongoDB connections (for graceful shutdown)."""
        try:
            await self.mongodb_manager.disconnect()
            logger.info("All MongoDB connections closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connections: {e}")

# Global database manager instance
db_manager = DatabaseManager()

def get_db_session():
    """Dependency to get MongoDB database for FastAPI (legacy compatibility)."""
    try:
        db = db_manager.get_session()
        yield db
    except Exception as e:
        logger.error(f"Error getting MongoDB database: {e}")
        raise

def get_mongodb_session():
    """Dependency to get MongoDB database for FastAPI."""
    try:
        db = db_manager.get_session()
        yield db
    except Exception as e:
        logger.error(f"Error getting MongoDB database: {e}")
        raise

async def init_database():
    """Initialize MongoDB and create indexes."""
    try:
        # Force reinitialization by resetting the initialized flag
        db_manager._initialized = False
        db_manager.mongodb_manager = None
        
        await db_manager.initialize()
        await db_manager.create_tables()
        logger.info("MongoDB initialization completed")
    except Exception as e:
        logger.error(f"MongoDB initialization failed: {e}")
        raise

def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    return db_manager