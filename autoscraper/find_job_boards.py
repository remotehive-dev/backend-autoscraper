#!/usr/bin/env python3
"""
Script to find where the 735 job boards are actually stored.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def find_job_boards():
    """Find job boards across all databases."""
    print("Searching for job boards across all databases...")
    
    # MongoDB connection URL
    mongodb_url = "mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive"
    
    client = AsyncIOMotorClient(mongodb_url)
    
    try:
        # List all databases
        databases = await client.list_database_names()
        print(f"\n📁 Available databases: {databases}")
        
        # Check each database for job boards
        for db_name in databases:
            if db_name in ['admin', 'local', 'config']:  # Skip system databases
                continue
                
            print(f"\n🔍 Checking database: {db_name}")
            db = client[db_name]
            collections = await db.list_collection_names()
            
            # Look for job board collections
            job_board_collections = [c for c in collections if 'job' in c.lower() and 'board' in c.lower()]
            
            if job_board_collections:
                print(f"  📋 Job board collections found: {job_board_collections}")
                
                for collection_name in job_board_collections:
                    count = await db[collection_name].count_documents({})
                    print(f"    {collection_name}: {count} documents")
                    
                    if count > 0:
                        # Show sample document
                        sample = await db[collection_name].find_one()
                        if sample:
                            print(f"      Sample keys: {list(sample.keys())[:10]}...")  # First 10 keys
                            if 'name' in sample:
                                print(f"      Sample name: {sample.get('name')}")
                            if 'base_url' in sample:
                                print(f"      Sample URL: {sample.get('base_url')}")
            
            # Also check for any collection with significant document count
            print(f"  📊 Collections with documents:")
            for collection_name in collections:
                count = await db[collection_name].count_documents({})
                if count > 100:  # Only show collections with substantial data
                    print(f"    {collection_name}: {count} documents")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()
        print("\n🔌 Connection closed")

if __name__ == "__main__":
    asyncio.run(find_job_boards())