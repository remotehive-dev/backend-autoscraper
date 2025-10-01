#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.append('/Users/ranjeettiwary/Downloads/developer/RemoteHive_Migration_Package/autoscraper-service')

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.mongodb_models import JobBoard, JobBoardType
from config.settings import settings

async def check_job_boards():
    """Check job boards in MongoDB database"""
    try:
        # Initialize MongoDB connection
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        database = client[settings.MONGODB_DATABASE_NAME]
        
        # Initialize Beanie with JobBoard model
        await init_beanie(database=database, document_models=[JobBoard])
        
        # Count total job boards
        total_count = await JobBoard.count()
        print(f"Total job boards in MongoDB: {total_count}")
        
        # Count active job boards
        active_count = await JobBoard.find({"is_active": True}).count()
        print(f"Active job boards: {active_count}")
        
        # Count inactive job boards
        inactive_count = await JobBoard.find({"is_active": False}).count()
        print(f"Inactive job boards: {inactive_count}")
        
        # Get sample job boards
        sample_boards = await JobBoard.find().limit(10).to_list()
        print(f"\nSample job boards (first 10):")
        for i, board in enumerate(sample_boards, 1):
            print(f"  {i}. {board.name} (Type: {board.type}, Active: {board.is_active})")
        
        # Count by type
        print(f"\nJob boards by type:")
        for job_type in JobBoardType:
            type_count = await JobBoard.find({"type": job_type}).count()
            if type_count > 0:
                print(f"  {job_type.value}: {type_count}")
        
        # Check if there are any collections in the database
        collections = await database.list_collection_names()
        print(f"\nAll collections in database: {collections}")
        
        # Close connection
        client.close()
        
    except Exception as e:
        print(f"Error checking job boards: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_job_boards())