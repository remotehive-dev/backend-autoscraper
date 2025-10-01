#!/usr/bin/env python3
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_all_collections():
    """Check collections in both databases"""
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    
    try:
        # Check main remotehive database
        print("=== Main 'remotehive' database ===")
        main_db = client.remotehive
        main_collections = await main_db.list_collection_names()
        print(f"Collections: {main_collections}")
        
        for collection_name in main_collections:
            if 'job' in collection_name.lower() or 'board' in collection_name.lower():
                count = await main_db[collection_name].count_documents({})
                print(f"  {collection_name}: {count} documents")
        
        # Check autoscraper database
        print("\n=== Autoscraper 'remotehive_autoscraper' database ===")
        auto_db = client.remotehive_autoscraper
        auto_collections = await auto_db.list_collection_names()
        print(f"Collections: {auto_collections}")
        
        for collection_name in auto_collections:
            if 'job' in collection_name.lower() or 'board' in collection_name.lower():
                count = await auto_db[collection_name].count_documents({})
                print(f"  {collection_name}: {count} documents")
        
        # Check if there are other databases
        print("\n=== All databases ===")
        db_names = await client.list_database_names()
        print(f"Available databases: {db_names}")
        
        # Check each database for job-related collections
        for db_name in db_names:
            if db_name not in ['admin', 'config', 'local']:
                print(f"\n--- Database: {db_name} ---")
                db = client[db_name]
                collections = await db.list_collection_names()
                for collection_name in collections:
                    if 'job' in collection_name.lower() or 'board' in collection_name.lower():
                        count = await db[collection_name].count_documents({})
                        print(f"  {collection_name}: {count} documents")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check_all_collections())