#!/usr/bin/env python3
"""
Debug script to test the exact database connection used by the running service
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from datetime import datetime

async def debug_service_database():
    """Debug the exact database connection used by the service"""
    
    print("=== Service Database Connection Debug ===")
    print(f"Timestamp: {datetime.now()}")
    print()
    
    # Load settings exactly like the service does
    from config.settings import get_settings
    settings = get_settings()
    
    print(f"Settings loaded from: {settings.__class__.__name__}")
    print(f"MongoDB URL: {settings.MONGODB_URL[:50]}..." if settings.MONGODB_URL else "MongoDB URL: Not found")
    print(f"Database Name: {settings.MONGODB_DATABASE_NAME}")
    print()
    
    try:
        # Connect exactly like the service does
        print("🔗 Connecting to MongoDB (service style)...")
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        database = client[settings.MONGODB_DATABASE_NAME]
        
        # Test connection
        await client.admin.command('ping')
        print("✅ Successfully connected to MongoDB")
        print()
        
        # List all databases
        print("🗄️ Available databases:")
        db_list = await client.list_database_names()
        for db_name in db_list:
            print(f"  - {db_name}")
        print()
        
        # Check current database collections
        print(f"📁 Collections in '{settings.MONGODB_DATABASE_NAME}':")
        collections = await database.list_collection_names()
        for collection_name in collections:
            count = await database[collection_name].count_documents({})
            print(f"  - {collection_name}: {count} documents")
        print()
        
        # Import models exactly like the service does
        print("📦 Importing models (service style)...")
        from app.models.mongodb_models import (
            JobBoard, ScheduleConfig, ScrapeJob, ScrapeRun, 
            RawJob, NormalizedJob, EngineState, ScrapingMetrics,
            JobPosting, ScrapingSession
        )
        
        document_models = [
            JobBoard, ScheduleConfig, ScrapeJob, ScrapeRun,
            RawJob, NormalizedJob, EngineState, ScrapingMetrics,
            JobPosting, ScrapingSession
        ]
        
        # Initialize Beanie exactly like the service does
        print("🚀 Initializing Beanie (service style)...")
        await init_beanie(
            database=database,
            document_models=document_models
        )
        print("✅ Beanie initialized successfully")
        print()
        
        # Test JobBoard queries exactly like the API does
        print("🔍 Testing JobBoard queries (API style):")
        
        # Test 1: Count all job boards
        total_count = await JobBoard.count()
        print(f"📊 Total job boards: {total_count}")
        
        # Test 2: Test the exact API query with empty filter
        print("\n🔍 Testing API query (empty filter):")
        query_filter = {}
        skip = 0
        limit = 10
        
        job_boards = await JobBoard.find(query_filter).skip(skip).limit(limit).to_list()
        print(f"Empty filter query returned: {len(job_boards)} job boards")
        
        if job_boards:
            print("First result:")
            jb = job_boards[0]
            print(f"  - ID: {jb.id}")
            print(f"  - Name: {jb.name}")
            print(f"  - Type: {jb.type}")
            print(f"  - Is Active: {jb.is_active}")
        else:
            print("❌ No results returned from API query!")
        
        # Test 3: Test with different query approaches
        print("\n🔍 Testing different query approaches:")
        
        # Approach 1: Find all
        all_boards = await JobBoard.find().limit(5).to_list()
        print(f"Find all (limit 5): {len(all_boards)} results")
        
        # Approach 2: Find with empty dict
        empty_dict_boards = await JobBoard.find({}).limit(5).to_list()
        print(f"Find with empty dict (limit 5): {len(empty_dict_boards)} results")
        
        # Approach 3: Find with is_active filter
        active_boards = await JobBoard.find({"is_active": True}).limit(5).to_list()
        print(f"Find active boards (limit 5): {len(active_boards)} results")
        
        # Test 4: Direct collection access
        print("\n🔍 Testing direct collection access:")
        job_boards_collection = database['job_boards']
        direct_count = await job_boards_collection.count_documents({})
        print(f"Direct collection count: {direct_count}")
        
        direct_docs = await job_boards_collection.find({}).limit(3).to_list(length=3)
        print(f"Direct collection query: {len(direct_docs)} results")
        
        if direct_docs:
            print("First direct result:")
            doc = direct_docs[0]
            print(f"  - ID: {doc.get('_id')}")
            print(f"  - Name: {doc.get('name')}")
            print(f"  - Type: {doc.get('type')}")
        
        print()
        print("✅ Service database connection test complete!")
        
    except Exception as e:
        print(f"❌ Error in service database test: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'client' in locals():
            client.close()
            print("🔌 MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(debug_service_database())