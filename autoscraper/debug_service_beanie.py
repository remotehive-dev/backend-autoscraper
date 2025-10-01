#!/usr/bin/env python3
"""
Debug script to test the exact same Beanie initialization
that the running service uses.
"""

import asyncio
import os
from app.database.mongodb_manager import init_autoscraper_mongodb, close_autoscraper_mongodb
from app.models.mongodb_models import JobBoard
from config.settings import get_settings

async def debug_service_beanie():
    print("=== Service Beanie Debug ===")
    
    # Get settings exactly like the service does
    settings = get_settings()
    print(f"MongoDB URL: {settings.MONGODB_URL}")
    print(f"Database Name: {settings.MONGODB_DATABASE_NAME}")
    
    print("\n1. Initializing MongoDB exactly like the service...")
    try:
        await init_autoscraper_mongodb()
        print("✅ MongoDB initialized successfully")
    except Exception as e:
        print(f"❌ MongoDB initialization failed: {e}")
        return
    
    print("\n2. Testing JobBoard queries after service-style initialization...")
    try:
        # Test basic count
        total_count = await JobBoard.count()
        print(f"Total JobBoard count: {total_count}")
        
        # Test with filter
        active_count = await JobBoard.find({"is_active": True}).count()
        print(f"Active JobBoard count: {active_count}")
        
        # Test find_all
        all_boards = await JobBoard.find_all().to_list()
        print(f"Find all returned: {len(all_boards)} documents")
        
        # Test with limit (like the API does)
        limited_boards = await JobBoard.find().limit(5).to_list()
        print(f"Limited query returned: {len(limited_boards)} documents")
        
        if limited_boards:
            print(f"First board name: {limited_boards[0].name}")
            print(f"First board is_active: {limited_boards[0].is_active}")
        
        # Test the exact query from the API
        print("\n3. Testing exact API query logic...")
        query_filter = {}
        # This mimics the API logic
        active_only = False
        if active_only:
            query_filter["is_active"] = True
        
        print(f"Query filter: {query_filter}")
        
        api_style_count = await JobBoard.find(query_filter).count()
        print(f"API-style count: {api_style_count}")
        
        api_style_docs = await JobBoard.find(query_filter).limit(5).to_list()
        print(f"API-style limited query: {len(api_style_docs)} documents")
        
        # Test with active_only=True
        query_filter_active = {"is_active": True}
        active_api_count = await JobBoard.find(query_filter_active).count()
        print(f"Active-only API count: {active_api_count}")
        
    except Exception as e:
        print(f"❌ Query failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n4. Checking Beanie state...")
    try:
        # Check if JobBoard is properly registered
        collection_name = JobBoard.get_collection_name()
        print(f"JobBoard collection name: {collection_name}")
        
        # Check database connection
        db = JobBoard.get_motor_collection().database
        print(f"Database name from JobBoard: {db.name}")
        
        # Test raw collection access
        raw_count = await JobBoard.get_motor_collection().count_documents({})
        print(f"Raw collection count: {raw_count}")
        
    except Exception as e:
        print(f"❌ Beanie state check failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n5. Closing connection...")
    try:
        await close_autoscraper_mongodb()
        print("✅ Connection closed")
    except Exception as e:
        print(f"❌ Close failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_service_beanie())