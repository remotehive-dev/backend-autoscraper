#!/usr/bin/env python3
"""
Compare direct MongoDB connection vs service connection
to identify why the service sees 0 documents while direct connection sees 735
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_direct_vs_service():
    """Compare direct MongoDB access vs service access"""
    
    mongodb_url = os.getenv("MONGODB_URL")
    database_name = os.getenv("MONGODB_DATABASE_NAME", "remotehive_autoscraper")
    
    print(f"Testing with:")
    print(f"MongoDB URL: {mongodb_url}")
    print(f"Database Name: {database_name}")
    print("=" * 60)
    
    # 1. Direct PyMongo connection (synchronous)
    print("\n1. DIRECT PYMONGO CONNECTION:")
    try:
        sync_client = MongoClient(mongodb_url)
        sync_db = sync_client[database_name]
        
        # List all databases
        print(f"Available databases: {sync_client.list_database_names()}")
        
        # List all collections in the target database
        collections = sync_db.list_collection_names()
        print(f"Collections in '{database_name}': {collections}")
        
        # Check job_boards collection
        if "job_boards" in collections:
            job_boards_count = sync_db.job_boards.count_documents({})
            print(f"job_boards count (direct): {job_boards_count}")
            
            # Get a sample document
            sample_doc = sync_db.job_boards.find_one()
            if sample_doc:
                print(f"Sample document keys: {list(sample_doc.keys())}")
                print(f"Sample _id: {sample_doc.get('_id')}")
            else:
                print("No sample document found")
        else:
            print("job_boards collection not found!")
            
        sync_client.close()
        
    except Exception as e:
        print(f"Direct connection error: {e}")
    
    # 2. Motor async connection (like the service uses)
    print("\n2. MOTOR ASYNC CONNECTION (Service-like):")
    try:
        async_client = AsyncIOMotorClient(mongodb_url)
        async_db = async_client[database_name]
        
        # List all databases
        db_names = await async_client.list_database_names()
        print(f"Available databases: {db_names}")
        
        # List all collections in the target database
        collections = await async_db.list_collection_names()
        print(f"Collections in '{database_name}': {collections}")
        
        # Check job_boards collection
        if "job_boards" in collections:
            job_boards_count = await async_db.job_boards.count_documents({})
            print(f"job_boards count (async): {job_boards_count}")
            
            # Get a sample document
            sample_doc = await async_db.job_boards.find_one()
            if sample_doc:
                print(f"Sample document keys: {list(sample_doc.keys())}")
                print(f"Sample _id: {sample_doc.get('_id')}")
            else:
                print("No sample document found")
        else:
            print("job_boards collection not found!")
            
        async_client.close()
        
    except Exception as e:
        print(f"Async connection error: {e}")
    
    # 3. Test with service's database manager
    print("\n3. SERVICE DATABASE MANAGER:")
    try:
        # Import the service's database manager
        import sys
        sys.path.append('/Users/ranjeettiwary/Downloads/developer/RemoteHive_Migration_Package/autoscraper-service')
        
        from app.database.mongodb_manager import get_autoscraper_mongodb_manager
        from app.models.mongodb_models import JobBoard
        
        # Get the manager
        manager = await get_autoscraper_mongodb_manager()
        print(f"Manager obtained: {manager}")
        print(f"Manager connected: {manager.is_connected}")
        
        # Test direct collection access through service
        service_db = manager.get_database()
        print(f"Service database name: {service_db.name}")
        service_collection = service_db.job_boards
        service_direct_count = await service_collection.count_documents({})
        print(f"Service direct collection count: {service_direct_count}")
        
        # Test Beanie model access
        try:
            beanie_count = await JobBoard.count()
            print(f"Beanie JobBoard.count(): {beanie_count}")
            
            # Try to find documents
            docs = await JobBoard.find().limit(1).to_list()
            print(f"Beanie JobBoard.find().limit(1): {len(docs)} documents")
            
        except Exception as beanie_error:
            print(f"Beanie error: {beanie_error}")
        
    except Exception as e:
        print(f"Service manager error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")

if __name__ == "__main__":
    asyncio.run(test_direct_vs_service())