#!/usr/bin/env python3
"""
Debug AutoScraper MongoDB Connection
Tests the exact same connection logic used by the autoscraper service
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the autoscraper-service directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from config.settings import get_settings
from app.models.mongodb_models import JobBoard
from app.database.mongodb_manager import AutoScraperMongoDBManager

async def debug_connection():
    """Debug the MongoDB connection and query logic"""
    
    print("=== AutoScraper MongoDB Connection Debug ===")
    
    # 1. Test settings loading
    print("\n1. Loading settings...")
    settings = get_settings()
    print(f"   MONGODB_URL: {settings.MONGODB_URL}")
    print(f"   MONGODB_DATABASE_NAME: {settings.MONGODB_DATABASE_NAME}")
    
    # 2. Test direct MongoDB connection (using settings connection string)
    print("\n2. Testing direct MongoDB connection...")
    try:
        direct_client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000
        )
        direct_db = direct_client[settings.MONGODB_DATABASE_NAME]
        
        # Test connection
        await direct_client.admin.command('ping')
        print("   ✓ Direct connection successful")
        
        # Count job boards directly
        direct_count = await direct_db.job_boards.count_documents({})
        print(f"   ✓ Direct count: {direct_count} job boards")
        
        # Sample document
        sample_doc = await direct_db.job_boards.find_one({})
        if sample_doc:
            print(f"   ✓ Sample document keys: {list(sample_doc.keys())}")
            print(f"   ✓ Sample name: {sample_doc.get('name', 'N/A')}")
            print(f"   ✓ Sample is_active: {sample_doc.get('is_active', 'N/A')}")
        
        direct_client.close()
        
    except Exception as e:
        print(f"   ✗ Direct connection failed: {e}")
        return
    
    # 3. Test AutoScraper MongoDB Manager
    print("\n3. Testing AutoScraper MongoDB Manager...")
    try:
        manager = AutoScraperMongoDBManager()
        
        # Connect using settings
        success = await manager.connect(
            connection_string=settings.MONGODB_URL,
            database_name=settings.MONGODB_DATABASE_NAME
        )
        
        if success:
            print("   ✓ Manager connection successful")
            print(f"   ✓ Connected to database: {manager.database_name}")
            
            # Test connection info
            connection_info = await manager.test_connection()
            print(f"   ✓ Connection test: {connection_info.get('connected', False)}")
            print(f"   ✓ Collections: {connection_info.get('collections_count', 0)}")
            
        else:
            print("   ✗ Manager connection failed")
            return
            
    except Exception as e:
        print(f"   ✗ Manager connection error: {e}")
        return
    
    # 4. Test Beanie model queries
    print("\n4. Testing Beanie JobBoard model queries...")
    try:
        # Count all job boards using Beanie
        total_count = await JobBoard.find().count()
        print(f"   ✓ Total JobBoard count: {total_count}")
        
        # Test different query filters
        active_true_count = await JobBoard.find(JobBoard.is_active == True).count()
        print(f"   ✓ Active (True) count: {active_true_count}")
        
        active_false_count = await JobBoard.find(JobBoard.is_active == False).count()
        print(f"   ✓ Active (False) count: {active_false_count}")
        
        # Test with empty filter (like the API does when active_only=False)
        empty_filter_count = await JobBoard.find({}).count()
        print(f"   ✓ Empty filter count: {empty_filter_count}")
        
        # Test pagination (like the API does)
        paginated_results = await JobBoard.find({}).limit(10).to_list()
        print(f"   ✓ Paginated results (limit 10): {len(paginated_results)} items")
        
        if paginated_results:
            first_result = paginated_results[0]
            print(f"   ✓ First result name: {first_result.name}")
            print(f"   ✓ First result is_active: {first_result.is_active}")
            print(f"   ✓ First result type: {type(first_result)}")
        
        # Test the exact query logic from the API
        print("\n5. Testing exact API query logic...")
        
        # Simulate active_only=False (empty filter)
        query_filter = {}
        api_results_false = await JobBoard.find(query_filter).limit(10).to_list()
        print(f"   ✓ API simulation (active_only=False): {len(api_results_false)} results")
        
        # Simulate active_only=True
        query_filter = {"is_active": True}
        api_results_true = await JobBoard.find(query_filter).limit(10).to_list()
        print(f"   ✓ API simulation (active_only=True): {len(api_results_true)} results")
        
        # Test raw motor collection access
        print("\n6. Testing raw motor collection access...")
        motor_collection = manager.database.job_boards
        motor_count = await motor_collection.count_documents({})
        print(f"   ✓ Motor collection count: {motor_count}")
        
        motor_docs = await motor_collection.find({}).limit(5).to_list(length=5)
        print(f"   ✓ Motor collection docs: {len(motor_docs)} items")
        
        if motor_docs:
            print(f"   ✓ Motor doc sample: {motor_docs[0].get('name', 'N/A')}")
        
    except Exception as e:
        print(f"   ✗ Beanie query error: {e}")
        import traceback
        traceback.print_exc()
    
    # 7. Test database and collection names
    print("\n7. Verifying database and collection names...")
    try:
        current_db_name = manager.database.name
        print(f"   ✓ Current database name: {current_db_name}")
        
        collections = await manager.database.list_collection_names()
        print(f"   ✓ Available collections: {collections}")
        
        if 'job_boards' in collections:
            print("   ✓ job_boards collection exists")
        else:
            print("   ✗ job_boards collection NOT found")
            
    except Exception as e:
        print(f"   ✗ Database verification error: {e}")
    
    # Cleanup
    await manager.disconnect()
    print("\n=== Debug Complete ===")

if __name__ == "__main__":
    asyncio.run(debug_connection())