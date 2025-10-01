#!/usr/bin/env python3
"""
Debug script to check collections in the remotehive database.
"""

import asyncio
import sys
import os
from motor.motor_asyncio import AsyncIOMotorClient

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import get_settings

async def debug_collections():
    """Debug collections in the remotehive database."""
    print("Debugging collections in remotehive database...")
    
    settings = get_settings()
    print(f"MongoDB URL: {settings.MONGODB_URL}")
    print(f"Database Name: {settings.MONGODB_DATABASE_NAME}")
    
    # Create direct MongoDB connection
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DATABASE_NAME]
    
    try:
        # List all collections
        collections = await db.list_collection_names()
        print(f"\n📁 Collections in '{settings.MONGODB_DATABASE_NAME}' database:")
        for i, collection in enumerate(collections, 1):
            print(f"  {i}. {collection}")
        
        # Check for job board related collections
        job_board_collections = [c for c in collections if 'job' in c.lower() or 'board' in c.lower()]
        print(f"\n🎯 Job board related collections: {job_board_collections}")
        
        # Check document counts for potential job board collections
        potential_collections = ['job_boards', 'jobboards', 'JobBoard', 'JobBoards', 'jobs', 'boards']
        
        print(f"\n📊 Document counts for potential job board collections:")
        for collection_name in potential_collections:
            if collection_name in collections:
                count = await db[collection_name].count_documents({})
                print(f"  {collection_name}: {count} documents")
                
                if count > 0:
                    # Show sample document
                    sample = await db[collection_name].find_one()
                    print(f"    Sample document keys: {list(sample.keys()) if sample else 'None'}")
        
        # Check all collections with documents
        print(f"\n📈 All collections with document counts:")
        for collection_name in collections:
            count = await db[collection_name].count_documents({})
            if count > 0:
                print(f"  {collection_name}: {count} documents")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()
        print("\n🔌 Connection closed")

if __name__ == "__main__":
    asyncio.run(debug_collections())