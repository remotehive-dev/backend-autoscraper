#!/usr/bin/env python3
"""
Simple debug script to test MongoDB connection and job board queries
"""

import asyncio
import sys
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from config.settings import get_settings

async def debug_mongodb_direct():
    """
    Debug MongoDB connection and queries directly
    """
    try:
        print("=== Direct MongoDB Debug ===")
        
        # Get settings
        settings = get_settings()
        print(f"1. MongoDB URL: {settings.MONGODB_URL}")
        print(f"   Database: {settings.MONGODB_DATABASE_NAME}")
        
        # Connect to MongoDB directly
        print("\n2. Connecting to MongoDB...")
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = client[settings.MONGODB_DATABASE_NAME]
        
        # Test connection
        await client.admin.command('ping')
        print("   ✓ MongoDB connection successful")
        
        # Get job_boards collection
        job_boards_collection = db.job_boards
        
        # Count total documents
        total_count = await job_boards_collection.count_documents({})
        print(f"\n3. Total job boards in collection: {total_count}")
        
        # Count active documents
        active_count = await job_boards_collection.count_documents({"is_active": True})
        print(f"   Active job boards: {active_count}")
        
        # Count inactive documents
        inactive_count = await job_boards_collection.count_documents({"is_active": False})
        print(f"   Inactive job boards: {inactive_count}")
        
        # Get sample documents
        print(f"\n4. Sample job boards (first 5):")
        cursor = job_boards_collection.find({}).limit(5)
        async for doc in cursor:
            print(f"   - Name: {doc.get('name', 'N/A')}")
            print(f"     URL: {doc.get('url', doc.get('base_url', 'N/A'))}")
            print(f"     Active: {doc.get('is_active', 'N/A')}")
            print(f"     Type: {doc.get('type', 'N/A')}")
            print(f"     ID: {doc.get('_id', 'N/A')}")
            print()
        
        # Test the exact query used by API
        print(f"\n5. Testing API query (limit=1000, active_only=False):")
        query_filter = {}  # No filter for active_only=False
        
        cursor = job_boards_collection.find(query_filter).skip(0).limit(1000)
        results = await cursor.to_list(length=1000)
        
        print(f"   Query results: {len(results)} documents")
        
        if results:
            print(f"   First result:")
            first = results[0]
            print(f"     Name: {first.get('name', 'N/A')}")
            print(f"     Active: {first.get('is_active', 'N/A')}")
            print(f"     Type: {first.get('type', 'N/A')}")
        else:
            print("   No results returned from query")
        
        # Test with active_only=True
        print(f"\n6. Testing API query (limit=1000, active_only=True):")
        query_filter = {"is_active": True}
        
        cursor = job_boards_collection.find(query_filter).skip(0).limit(1000)
        results = await cursor.to_list(length=1000)
        
        print(f"   Query results: {len(results)} documents")
        
        # Check collection indexes
        print(f"\n7. Collection indexes:")
        indexes = await job_boards_collection.list_indexes().to_list(length=None)
        for idx in indexes:
            print(f"   - {idx.get('name', 'unnamed')}: {idx.get('key', {})}")
        
        print(f"\n=== Debug Complete ===")
        
    except Exception as e:
        print(f"Error during debug: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Close connection
        if 'client' in locals():
            client.close()
            print("MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(debug_mongodb_direct())