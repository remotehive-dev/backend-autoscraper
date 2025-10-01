#!/usr/bin/env python3
"""
Debug script to test the exact API endpoint logic
"""

import asyncio
import os
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from config.settings import get_settings
from app.models.mongodb_models import JobBoard, ScheduleConfig, ScrapeJob, ScrapeRun, RawJob, NormalizedJob, EngineState, ScrapingMetrics, JobPosting, ScrapingSession

async def test_api_endpoint_logic():
    """Test the exact logic used in the API endpoint"""
    print("=== Testing API Endpoint Logic ===")
    
    try:
        # Load settings
        settings = get_settings()
        print(f"✓ Settings loaded")
        print(f"  MongoDB URL: {settings.MONGODB_URL[:50]}...")
        print(f"  Database Name: {settings.MONGODB_DATABASE_NAME}")
        
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        database = client[settings.MONGODB_DATABASE_NAME]
        print(f"✓ Connected to MongoDB Atlas")
        
        # List collections
        collections = await database.list_collection_names()
        print(f"✓ Collections found: {collections}")
        
        # Direct collection count
        job_boards_collection = database.job_boards
        direct_count = await job_boards_collection.count_documents({})
        print(f"✓ Direct collection count: {direct_count}")
        
        # Initialize Beanie with all models
        await init_beanie(
            database=database,
            document_models=[
                JobBoard,
                ScheduleConfig,
                ScrapeJob,
                ScrapeRun,
                RawJob,
                NormalizedJob,
                EngineState,
                ScrapingMetrics,
                JobPosting,
                ScrapingSession
            ]
        )
        print(f"✓ Beanie initialized with all models")
        
        # Test the exact API query logic
        print("\n=== Testing API Query Logic ===")
        
        # Parameters from API
        limit = 10
        skip = 0
        active_only = False
        search = None
        
        # Build query (same as API)
        query = {}
        if active_only:
            query["is_active"] = True
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"url": {"$regex": search, "$options": "i"}}
            ]
        
        print(f"Query filter: {query}")
        
        # Execute query using Beanie
        job_boards = await JobBoard.find(query).skip(skip).limit(limit).to_list()
        print(f"✓ Beanie query result: {len(job_boards)} job boards")
        
        if job_boards:
            print(f"  First job board: {job_boards[0].name}")
            print(f"  Sample data: {job_boards[0].dict()}")
        
        # Test total count
        total_count = await JobBoard.find(query).count()
        print(f"✓ Total count with query: {total_count}")
        
        # Test without any query
        all_job_boards = await JobBoard.find().limit(5).to_list()
        print(f"✓ All job boards (limit 5): {len(all_job_boards)}")
        
        if all_job_boards:
            print(f"  Names: {[jb.name for jb in all_job_boards]}")
        
        # Test direct MongoDB query
        print("\n=== Testing Direct MongoDB Query ===")
        cursor = job_boards_collection.find(query).skip(skip).limit(limit)
        direct_results = await cursor.to_list(length=None)
        print(f"✓ Direct MongoDB query: {len(direct_results)} results")
        
        if direct_results:
            print(f"  First result name: {direct_results[0].get('name', 'N/A')}")
        
        await client.close()
        print("\n✓ Connection closed")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_api_endpoint_logic())