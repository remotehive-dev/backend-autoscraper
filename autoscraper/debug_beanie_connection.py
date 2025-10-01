#!/usr/bin/env python3
"""
Debug script to test Beanie initialization and MongoDB connection
This script will replicate the exact same setup as the running service
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from datetime import datetime

async def debug_beanie_connection():
    """Debug Beanie connection and model initialization"""
    
    print("=== Beanie Connection Debug ===")
    print(f"Timestamp: {datetime.now()}")
    print()
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get MongoDB connection details
    mongodb_url = os.getenv('MONGODB_URL')
    mongodb_database = os.getenv('MONGODB_DATABASE_NAME', 'remotehive_autoscraper')
    
    print(f"MongoDB URL: {mongodb_url[:50]}..." if mongodb_url else "MongoDB URL: Not found")
    print(f"Database Name: {mongodb_database}")
    print()
    
    if not mongodb_url:
        print("❌ ERROR: MONGODB_URL not found in environment variables")
        return
    
    try:
        # Connect to MongoDB (same as service)
        print("🔗 Connecting to MongoDB...")
        client = AsyncIOMotorClient(mongodb_url)
        database = client[mongodb_database]
        
        # Test connection
        await client.admin.command('ping')
        print("✅ Successfully connected to MongoDB")
        print()
        
        # Import all MongoDB models (same as service)
        print("📦 Importing MongoDB models...")
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
        
        print(f"Models to initialize: {[model.__name__ for model in document_models]}")
        print()
        
        # Initialize Beanie (same as service)
        print("🚀 Initializing Beanie...")
        await init_beanie(
            database=database,
            document_models=document_models
        )
        print("✅ Beanie initialized successfully")
        print()
        
        # Test JobBoard model queries
        print("🔍 Testing JobBoard model queries...")
        
        # Count all job boards using Beanie
        total_count = await JobBoard.count()
        print(f"📊 Total job boards (Beanie): {total_count}")
        
        # Count active job boards using Beanie
        active_count = await JobBoard.find({"is_active": True}).count()
        print(f"📊 Active job boards (Beanie): {active_count}")
        
        # Test the exact API query using Beanie
        print("\n🔍 Testing exact API query using Beanie:")
        query_filter = {}
        job_boards = await JobBoard.find(query_filter).skip(0).limit(10).to_list()
        print(f"API query returned: {len(job_boards)} job boards")
        
        if job_boards:
            print("\nFirst result:")
            jb = job_boards[0]
            print(f"  - ID: {jb.id}")
            print(f"  - Name: {jb.name}")
            print(f"  - Type: {jb.type}")
            print(f"  - Base URL: {jb.base_url}")
            print(f"  - Is Active: {jb.is_active}")
            print(f"  - Region: {getattr(jb, 'region', 'N/A')}")
        
        # Test active only query
        print("\n🔍 Testing active-only query using Beanie:")
        active_query_filter = {"is_active": True}
        active_job_boards = await JobBoard.find(active_query_filter).skip(0).limit(10).to_list()
        print(f"Active-only query returned: {len(active_job_boards)} job boards")
        
        # Test direct collection access
        print("\n🔍 Testing direct collection access:")
        collection = database['job_boards']
        direct_count = await collection.count_documents({})
        print(f"Direct collection count: {direct_count}")
        
        direct_docs = await collection.find({}).limit(5).to_list(length=5)
        print(f"Direct collection query returned: {len(direct_docs)} documents")
        
        if direct_docs:
            print("First direct document:")
            doc = direct_docs[0]
            print(f"  - ID: {doc.get('_id')}")
            print(f"  - Name: {doc.get('name')}")
            print(f"  - Type: {doc.get('type')}")
            print(f"  - Is Active: {doc.get('is_active')}")
        
        print()
        print("✅ Beanie connection test complete!")
        
    except Exception as e:
        print(f"❌ Error in Beanie connection test: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'client' in locals():
            client.close()
            print("🔌 MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(debug_beanie_connection())