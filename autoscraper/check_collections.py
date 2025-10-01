#!/usr/bin/env python3
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

async def check_all_collections():
    """Check all collections in MongoDB databases"""
    try:
        # Connect to MongoDB
        mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/remotehive")
        client = AsyncIOMotorClient(mongodb_url)
        
        # List all databases
        databases = await client.list_database_names()
        print(f"Available databases: {databases}")
        
        # Check each relevant database
        for db_name in ["remotehive", "remotehive_autoscraper", "autoscraper"]:
            if db_name in databases:
                print(f"\n=== Database: {db_name} ===")
                db = client[db_name]
                collections = await db.list_collection_names()
                print(f"Collections: {collections}")
                
                # Check document counts in each collection
                for collection_name in collections:
                    try:
                        collection = db[collection_name]
                        count = await collection.count_documents({})
                        print(f"  {collection_name}: {count} documents")
                        
                        # If it's a job-related collection with many documents, show sample
                        if count > 10 and ('job' in collection_name.lower() or 'board' in collection_name.lower()):
                            sample = await collection.find_one()
                            if sample:
                                print(f"    Sample document keys: {list(sample.keys())}")
                                
                    except Exception as e:
                        print(f"  Error checking {collection_name}: {e}")
        
        client.close()
        
    except Exception as e:
        print(f"Error checking collections: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_all_collections())