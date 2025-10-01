#!/usr/bin/env python3
"""
MongoDB Client Factory for AutoScraper Service
Provides singleton access to MongoDB connection manager
"""

from typing import Optional
from .mongodb_manager import AutoScraperMongoDBManager

# Global MongoDB manager instance
_mongodb_manager: Optional[AutoScraperMongoDBManager] = None


async def get_mongodb_client() -> AutoScraperMongoDBManager:
    """
    Get or create MongoDB client manager instance
    
    Returns:
        AutoScraperMongoDBManager: MongoDB connection manager
    """
    global _mongodb_manager
    
    if _mongodb_manager is None:
        _mongodb_manager = AutoScraperMongoDBManager()
        # Connect to MongoDB
        await _mongodb_manager.connect()
    
    return _mongodb_manager


async def close_mongodb_client():
    """
    Close MongoDB client connection
    """
    global _mongodb_manager
    
    if _mongodb_manager is not None:
        await _mongodb_manager.disconnect()
        _mongodb_manager = None