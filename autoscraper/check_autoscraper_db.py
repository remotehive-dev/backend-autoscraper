#!/usr/bin/env python3
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

async def check_autoscraper_db():
    """Check the autoscraper_db database specifically"""
    try:
        # Connect to MongoDB
        mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/remotehive")
        client = AsyncIOMotorClient(mongodb_url)
        
        # Check autoscraper_db database
        db = client["autoscraper_db"]
        collections = await db.list_collection_names()
        print(f"Collections in autoscraper_db: {collections}")
        
        # Check document counts in each collection
        for collection_name in collections:
            try:
                collection = db[collection_name]
                count = await collection.count_documents({})
                print(f"\n{collection_name}: {count} documents")
                
                # Show sample document for collections with data
                if count > 0:
                    sample = await collection.find_one()
                    if sample:
                        print(f"  Sample document keys: {list(sample.keys())}")
                        # If it looks like job boards, show more details
                        if 'name' in sample or 'url' in sample or 'board' in collection_name.lower():
                            print(f"  Sample: {sample}")
                            
            except Exception as e:
                print(f"  Error checking {collection_name}: {e}")
        
        client.close()
        
    except Exception as e:
        print(f"Error checking autoscraper_db: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_autoscraper_db())