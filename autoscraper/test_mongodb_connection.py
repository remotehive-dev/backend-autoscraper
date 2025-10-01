#!/usr/bin/env python3
"""
Direct MongoDB connection test for AutoScraper service
Tests the actual connection and queries the job_boards collection
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_mongodb_connection():
    """
    Test direct MongoDB connection and query job_boards collection
    """
    try:
        # Get connection details from environment
        mongodb_url = os.getenv("MONGODB_URL")
        database_name = os.getenv("MONGODB_DATABASE_NAME", "remotehive_autoscraper")
        
        print(f"Connecting to MongoDB...")
        print(f"URL: {mongodb_url[:50]}...")
        print(f"Database: {database_name}")
        
        # Create client
        client = AsyncIOMotorClient(mongodb_url)
        
        # Get database
        db = client[database_name]
        
        # Test connection
        await client.admin.command('ping')
        print("✅ MongoDB connection successful!")
        
        # List all collections
        collections = await db.list_collection_names()
        print(f"\n📁 Collections in '{database_name}' database:")
        for collection in collections:
            count = await db[collection].count_documents({})
            print(f"  - {collection}: {count} documents")
        
        # Focus on job_boards collection
        if 'job_boards' in collections:
            print(f"\n🎯 Analyzing 'job_boards' collection:")
            
            # Count total documents
            total_count = await db.job_boards.count_documents({})
            print(f"  Total documents: {total_count}")
            
            # Count active job boards
            active_count = await db.job_boards.count_documents({"is_active": True})
            print(f"  Active job boards: {active_count}")
            
            # Get sample documents
            print(f"\n📄 Sample job boards:")
            async for doc in db.job_boards.find().limit(5):
                print(f"  - {doc.get('name', 'Unknown')}: {doc.get('base_url', 'No URL')} (Active: {doc.get('is_active', False)})")
            
            # Test the exact query used by the API
            print(f"\n🔍 Testing API-style query:")
            
            # Query with no filter (like the API does)
            cursor = db.job_boards.find({})
            api_results = await cursor.to_list(length=1000)
            print(f"  Query with no filter returned: {len(api_results)} documents")
            
            # Query with active filter
            cursor_active = db.job_boards.find({"is_active": True})
            active_results = await cursor_active.to_list(length=1000)
            print(f"  Query with is_active=True returned: {len(active_results)} documents")
            
        else:
            print("❌ 'job_boards' collection not found!")
        
        # Close connection
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mongodb_connection())