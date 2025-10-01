#!/usr/bin/env python3
"""
Comprehensive Database Exploration Script
Find all job board data across databases and collections
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from config.settings import get_settings

async def explore_databases():
    """Explore all databases and collections to find job board data"""
    try:
        print("=== Comprehensive Database Exploration ===")
        
        # Get settings
        settings = get_settings()
        print(f"MongoDB URL: {settings.MONGODB_URL}")
        print(f"Expected Database: {settings.MONGODB_DATABASE_NAME}")
        
        # Create both async and sync clients for comprehensive exploration
        async_client = AsyncIOMotorClient(settings.MONGODB_URL)
        sync_client = MongoClient(settings.MONGODB_URL)
        
        print("\n1. Listing all databases...")
        # List all databases
        db_list = await async_client.list_database_names()
        print(f"Available databases: {db_list}")
        
        # Check each database for job board related collections
        for db_name in db_list:
            if db_name in ['admin', 'local', 'config']:
                continue
                
            print(f"\n2. Exploring database: {db_name}")
            db = async_client[db_name]
            collections = await db.list_collection_names()
            print(f"   Collections: {collections}")
            
            # Check each collection for job board data
            for collection_name in collections:
                if 'job' in collection_name.lower() or 'board' in collection_name.lower():
                    print(f"\n   📋 Found potential job board collection: {collection_name}")
                    collection = db[collection_name]
                    
                    # Count documents
                    count = await collection.count_documents({})
                    print(f"      Total documents: {count}")
                    
                    if count > 0:
                        # Get sample document
                        sample = await collection.find_one({})
                        print(f"      Sample document keys: {list(sample.keys()) if sample else 'None'}")
                        
                        # Check for specific fields that indicate job boards
                        if sample:
                            job_board_indicators = ['name', 'url', 'active', 'type', 'board_type']
                            found_indicators = [key for key in job_board_indicators if key in sample]
                            if found_indicators:
                                print(f"      ✅ Job board indicators found: {found_indicators}")
                                print(f"      Sample data: {dict(list(sample.items())[:5])}")
                            else:
                                print(f"      ❌ No job board indicators found")
        
        print("\n3. Specifically checking remotehive_autoscraper database...")
        autoscraper_db = async_client['remotehive_autoscraper']
        autoscraper_collections = await autoscraper_db.list_collection_names()
        print(f"Collections in remotehive_autoscraper: {autoscraper_collections}")
        
        if 'job_boards' in autoscraper_collections:
            job_boards_collection = autoscraper_db['job_boards']
            count = await job_boards_collection.count_documents({})
            print(f"Job boards count: {count}")
            
            if count > 0:
                sample = await job_boards_collection.find_one({})
                print(f"Sample job board: {sample}")
            else:
                print("❌ job_boards collection is empty!")
        else:
            print("❌ job_boards collection not found!")
        
        print("\n4. Checking main remotehive database...")
        if 'remotehive' in db_list:
            main_db = async_client['remotehive']
            main_collections = await main_db.list_collection_names()
            print(f"Collections in remotehive: {main_collections}")
            
            # Look for job board related collections
            for collection_name in main_collections:
                if 'job' in collection_name.lower():
                    collection = main_db[collection_name]
                    count = await collection.count_documents({})
                    print(f"   {collection_name}: {count} documents")
                    
                    if count > 0:
                        sample = await collection.find_one({})
                        print(f"   Sample keys: {list(sample.keys()) if sample else 'None'}")
        
        print("\n5. Using sync client to double-check...")
        # Use sync client for additional verification
        sync_db = sync_client['remotehive_autoscraper']
        if 'job_boards' in sync_db.list_collection_names():
            sync_count = sync_db['job_boards'].count_documents({})
            print(f"Sync client job boards count: {sync_count}")
            
            if sync_count > 0:
                sync_sample = sync_db['job_boards'].find_one({})
                print(f"Sync sample: {sync_sample}")
        
        # Close connections
        async_client.close()
        sync_client.close()
        
    except Exception as e:
        print(f"❌ Error in database exploration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(explore_databases())