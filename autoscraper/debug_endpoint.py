#!/usr/bin/env python3
"""
Temporary debug endpoint to test database connection from within the running service
"""

from fastapi import APIRouter, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from app.models.mongodb_models import JobBoard
from config.settings import get_settings
import asyncio

router = APIRouter()

@router.get("/debug/database-connection")
async def debug_database_connection():
    """Debug database connection and collection access"""
    try:
        settings = get_settings()
        
        # Get the current database connection from the running service
        from app.database.database import get_mongodb_manager
        db_manager = await get_mongodb_manager()
        
        if not db_manager:
            return {"error": "Database manager not initialized"}
        
        # Get database info
        database = db_manager.get_database()
        client = db_manager.get_client()
        
        # Test direct collection access
        collections = await database.list_collection_names()
        job_boards_collection = database.job_boards
        direct_count = await job_boards_collection.count_documents({})
        
        # Test Beanie model access
        beanie_count = await JobBoard.count()
        
        # Get sample documents
        sample_direct = await job_boards_collection.find_one({})
        sample_beanie = await JobBoard.find_one()
        
        return {
            "database_name": database.name,
            "collections": collections,
            "direct_collection_count": direct_count,
            "beanie_model_count": beanie_count,
            "sample_direct_doc": {
                "_id": str(sample_direct["_id"]) if sample_direct else None,
                "name": sample_direct.get("name") if sample_direct else None,
                "is_active": sample_direct.get("is_active") if sample_direct else None
            } if sample_direct else None,
            "sample_beanie_doc": {
                "id": str(sample_beanie.id) if sample_beanie else None,
                "name": sample_beanie.name if sample_beanie else None,
                "is_active": sample_beanie.is_active if sample_beanie else None
            } if sample_beanie else None,
            "jobboard_collection_name": JobBoard.get_collection_name(),
            "settings_db_name": settings.MONGODB_DATABASE_NAME,
            "settings_url": settings.MONGODB_URL[:50] + "..."
        }
        
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}