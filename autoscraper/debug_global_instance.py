#!/usr/bin/env python3
"""
Debug script to test the exact same global MongoDB manager instance used by the service
"""

import asyncio
import os
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
os.chdir(current_dir)

# Import the exact same global instance used by the service
from app.database.mongodb_manager import autoscraper_mongodb_manager, init_autoscraper_mongodb
from app.models.mongodb_models import JobBoard
from config.settings import get_settings

async def test_global_instance():
    """
    Test the exact same global MongoDB manager instance used by the service
    """
    print("=== Testing Global MongoDB Manager Instance ===")
    
    try:
        # Test 1: Check if already connected
        print(f"\n1. Initial Connection Status:")
        print(f"   Is connected: {autoscraper_mongodb_manager.is_connected}")
        print(f"   Client exists: {autoscraper_mongodb_manager.client is not None}")
        print(f"   Database exists: {autoscraper_mongodb_manager.database is not None}")
        
        # Test 2: Initialize using the same function as the service
        print(f"\n2. Initializing using service method...")
        await init_autoscraper_mongodb()
        print(f"   ✓ Initialization completed")
        print(f"   Is connected: {autoscraper_mongodb_manager.is_connected}")
        print(f"   Database name: {autoscraper_mongodb_manager.database_name}")
        
        # Test 3: Test connection
        print(f"\n3. Testing connection...")
        connection_info = await autoscraper_mongodb_manager.test_connection()
        print(f"   Connected: {connection_info.get('connected')}")
        print(f"   Database: {connection_info.get('database_name')}")
        print(f"   Collections: {connection_info.get('collections_count')}")
        
        # Test 4: Query JobBoard using Beanie (same as API)
        print(f"\n4. Testing JobBoard queries (same as API)...")
        
        # Test total count
        total_count = await JobBoard.count()
        print(f"   Total JobBoard count: {total_count}")
        
        # Test with empty filter (same as API when no filters)
        query_filter = {}  # Same as API
        empty_filter_count = await JobBoard.find(query_filter).count()
        print(f"   Empty filter count: {empty_filter_count}")
        
        # Test with active filter
        active_filter = {"is_active": True}
        active_count = await JobBoard.find(active_filter).count()
        print(f"   Active filter count: {active_count}")
        
        # Test pagination (same as API)
        skip = 0
        limit = 5
        job_boards = await JobBoard.find(query_filter).skip(skip).limit(limit).to_list()
        print(f"   Found {len(job_boards)} job boards with pagination")
        
        if job_boards:
            print(f"   Sample job board: {job_boards[0].name} (Active: {job_boards[0].is_active})")
        
        # Test 5: Direct database access
        print(f"\n5. Testing direct database access...")
        collections = await autoscraper_mongodb_manager.database.list_collection_names()
        print(f"   Available collections: {len(collections)}")
        print(f"   Job boards collection exists: {'job_boards' in collections}")
        
        # Direct collection count
        job_boards_collection = autoscraper_mongodb_manager.database.job_boards
        direct_count = await job_boards_collection.count_documents({})
        print(f"   Direct collection count: {direct_count}")
        
        # Test 6: Check Beanie initialization status
        print(f"\n6. Checking Beanie initialization...")
        try:
            # Try to access JobBoard's collection info
            collection_name = JobBoard.get_collection_name()
            print(f"   JobBoard collection name: {collection_name}")
            
            # Check if JobBoard is properly initialized
            motor_collection = JobBoard.get_motor_collection()
            print(f"   JobBoard motor collection: {motor_collection is not None}")
            
        except Exception as e:
            print(f"   ❌ Beanie initialization issue: {e}")
        
        print(f"\n=== Test Complete ===")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_global_instance())