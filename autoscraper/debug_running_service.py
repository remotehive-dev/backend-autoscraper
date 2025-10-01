#!/usr/bin/env python3
"""
Debug script to test the running service's database connection and queries
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from config.settings import get_settings
from app.models.mongodb_models import JobBoard

async def test_running_service_connection():
    """
    Test the exact same connection method used by the running service
    """
    print("=== Testing Running Service Database Connection ===")
    
    # Get settings exactly like the service does
    settings = get_settings()
    print(f"MongoDB URL: {settings.MONGODB_URL}")
    print(f"Database Name: {settings.MONGODB_DATABASE_NAME}")
    
    try:
        # Create client exactly like the service does
        client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=20000,
            maxPoolSize=50,
            minPoolSize=5,
            retryWrites=True
        )
        
        # Get database
        database = client[settings.MONGODB_DATABASE_NAME]
        
        # Test connection
        await client.admin.command('ping')
        print("✓ MongoDB connection successful")
        
        # List collections
        collections = await database.list_collection_names()
        print(f"✓ Collections found: {collections}")
        
        # Count documents in job_boards collection directly
        job_boards_count = await database.job_boards.count_documents({})
        print(f"✓ Direct collection count: {job_boards_count} job boards")
        
        # Sample a document
        if job_boards_count > 0:
            sample_doc = await database.job_boards.find_one({})
            print(f"✓ Sample document: {sample_doc}")
        
        # Initialize Beanie exactly like the service does
        from app.models.mongodb_models import (
            JobBoard, ScheduleConfig, ScrapeJob, ScrapeRun, RawJob, NormalizedJob,
            EngineState, ScrapingMetrics, JobPosting, ScrapingSession
        )
        
        await init_beanie(
            database=database,
            document_models=[
                JobBoard, ScheduleConfig, ScrapeJob, ScrapeRun, RawJob, NormalizedJob,
                EngineState, ScrapingMetrics, JobPosting, ScrapingSession
            ]
        )
        print("✓ Beanie initialized successfully")
        
        # Test Beanie queries
        total_count = await JobBoard.count()
        print(f"✓ Beanie total count: {total_count}")
        
        # Test the exact query used by the API
        skip = 0
        limit = 10
        active_only = False
        
        query = {}
        if active_only:
            query["is_active"] = True
            
        job_boards = await JobBoard.find(query).skip(skip).limit(limit).to_list()
        print(f"✓ API query result: {len(job_boards)} job boards found")
        
        if job_boards:
            print(f"✓ First job board: {job_boards[0].name}")
        else:
            print("⚠️ No job boards returned by API query")
            
            # Debug: Check if there are any documents at all
            any_docs = await JobBoard.find().limit(1).to_list()
            if any_docs:
                print(f"✓ But Beanie can find documents: {any_docs[0].name}")
            else:
                print("✗ Beanie cannot find any documents")
        
        # Test with different query approaches
        print("\n=== Testing Different Query Approaches ===")
        
        # Method 1: Direct find
        method1 = await JobBoard.find().to_list()
        print(f"Method 1 (direct find): {len(method1)} results")
        
        # Method 2: Find with empty dict
        method2 = await JobBoard.find({}).to_list()
        print(f"Method 2 (find with empty dict): {len(method2)} results")
        
        # Method 3: Find all
        method3 = await JobBoard.find_all().to_list()
        print(f"Method 3 (find_all): {len(method3)} results")
        
        # Method 4: Aggregate
        method4_cursor = JobBoard.aggregate([{"$match": {}}])
        method4 = await method4_cursor.to_list(length=None)
        print(f"Method 4 (aggregate): {len(method4)} results")
        
        await client.close()
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_running_service_connection())