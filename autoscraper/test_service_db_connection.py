#!/usr/bin/env python3
"""
Test the exact database connection used by the running autoscraper service
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the autoscraper-service directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import get_settings
from app.database.database import DatabaseManager
from app.models.mongodb_models import JobBoard

async def test_service_connection():
    """Test the exact same database connection logic used by the service"""
    
    print("=== Testing Service Database Connection ===")
    
    # 1. Load settings (same as service)
    print("\n1. Loading settings...")
    settings = get_settings()
    print(f"   MONGODB_URL: {settings.MONGODB_URL}")
    print(f"   MONGODB_DATABASE_NAME: {settings.MONGODB_DATABASE_NAME}")
    
    # 2. Initialize DatabaseManager (same as service)
    print("\n2. Initializing DatabaseManager...")
    try:
        db_manager = DatabaseManager()
        await db_manager.initialize()
        print("   ✓ DatabaseManager initialized successfully")
        
        # 3. Test database connection
        print("\n3. Testing database connection...")
        health_check = await db_manager.health_check()
        print(f"   ✓ Health check: {health_check}")
        
        # 4. Test JobBoard model queries (same as API endpoint)
        print("\n4. Testing JobBoard queries...")
        
        # Count all job boards
        total_count = await JobBoard.find().count()
        print(f"   ✓ Total JobBoard count: {total_count}")
        
        # Test with empty filter (same as API when active_only=False)
        query_filter = {}
        filtered_count = await JobBoard.find(query_filter).count()
        print(f"   ✓ Empty filter count: {filtered_count}")
        
        # Test pagination (same as API)
        job_boards = await JobBoard.find(query_filter).limit(5).to_list()
        print(f"   ✓ Paginated results: {len(job_boards)} items")
        
        if job_boards:
            first_job = job_boards[0]
            print(f"   ✓ First job board: {first_job.name}")
            print(f"   ✓ First job board active: {first_job.is_active}")
        
        # 5. Test database and collection info
        print("\n5. Database and collection info...")
        from app.database.mongodb_manager import autoscraper_mongodb_manager
        
        if autoscraper_mongodb_manager.database is not None:
            db_name = autoscraper_mongodb_manager.database.name
            print(f"   ✓ Connected database name: {db_name}")
            
            collections = await autoscraper_mongodb_manager.database.list_collection_names()
            print(f"   ✓ Available collections: {len(collections)}")
            print(f"   ✓ Collections: {collections}")
            
            if 'job_boards' in collections:
                print("   ✓ job_boards collection exists")
                
                # Direct collection access
                job_boards_collection = autoscraper_mongodb_manager.database.job_boards
                direct_count = await job_boards_collection.count_documents({})
                print(f"   ✓ Direct collection count: {direct_count}")
                
                # Sample document
                sample_doc = await job_boards_collection.find_one({})
                if sample_doc:
                    print(f"   ✓ Sample document name: {sample_doc.get('name', 'N/A')}")
                    print(f"   ✓ Sample document active: {sample_doc.get('is_active', 'N/A')}")
                    print(f"   ✓ Sample document keys: {list(sample_doc.keys())}")
                else:
                    print("   ✗ No documents found in collection")
                    
                # Check if there are any documents at all
                all_docs = await job_boards_collection.find({}).limit(3).to_list(length=3)
                print(f"   ✓ Direct query found {len(all_docs)} documents")
                
            else:
                print("   ✗ job_boards collection NOT found")
        else:
            print("   ✗ Database connection is None")
        
        # 6. Compare with direct Motor connection (like our debug script)
        print("\n6. Comparing with direct Motor connection...")
        from motor.motor_asyncio import AsyncIOMotorClient
        
        direct_client = AsyncIOMotorClient(settings.MONGODB_URL)
        direct_db = direct_client[settings.MONGODB_DATABASE_NAME]
        direct_collection = direct_db.job_boards
        
        direct_motor_count = await direct_collection.count_documents({})
        print(f"   ✓ Direct Motor count: {direct_motor_count}")
        
        if direct_motor_count > 0:
            sample_motor_doc = await direct_collection.find_one({})
            print(f"   ✓ Direct Motor sample: {sample_motor_doc.get('name', 'N/A')}")
        
        direct_client.close()
        
        # Cleanup
        await db_manager.close()
        print("\n=== Test Complete ===")
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_service_connection())