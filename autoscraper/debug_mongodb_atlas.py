#!/usr/bin/env python3
"""
Debug script to check MongoDB Atlas connection and count job boards
This script will:
1. Connect to MongoDB Atlas using the connection string from environment
2. Query the remotehive_autoscraper database -> job_boards collection
3. Count total documents and show a sample of the data
4. Check if there are any filtering issues or data inconsistencies
5. Also check if there are multiple databases or collections that might contain job board data
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import json
from bson import ObjectId
from typing import Dict, Any

# Custom JSON encoder for MongoDB types
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

async def debug_mongodb_atlas():
    """Debug MongoDB Atlas connection and job boards data"""
    
    print("=== MongoDB Atlas Connection Debug ===")
    print(f"Timestamp: {datetime.now()}")
    print()
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Get MongoDB connection details
    mongodb_url = os.getenv('MONGODB_URL')
    mongodb_database = os.getenv('MONGODB_DATABASE_NAME', 'remotehive_autoscraper')
    
    print(f"MongoDB URL: {mongodb_url[:50]}..." if mongodb_url else "MongoDB URL: Not found")
    print(f"Database Name: {mongodb_database}")
    print()
    
    if not mongodb_url:
        print("❌ ERROR: MONGODB_URL not found in environment variables")
        return
    
    try:
        # Connect to MongoDB Atlas
        print("🔗 Connecting to MongoDB Atlas...")
        client = AsyncIOMotorClient(mongodb_url)
        
        # Test connection
        await client.admin.command('ping')
        print("✅ Successfully connected to MongoDB Atlas")
        print()
        
        # Get database
        db = client[mongodb_database]
        
        # List all databases
        print("📋 Available Databases:")
        db_list = await client.list_database_names()
        for db_name in db_list:
            print(f"  - {db_name}")
        print()
        
        # List all collections in the target database
        print(f"📋 Collections in '{mongodb_database}' database:")
        collections = await db.list_collection_names()
        for collection_name in collections:
            count = await db[collection_name].count_documents({})
            print(f"  - {collection_name}: {count} documents")
        print()
        
        # Focus on job_boards collection
        job_boards_collection = db['job_boards']
        
        print("🎯 Analyzing 'job_boards' collection:")
        print()
        
        # Count total documents
        total_count = await job_boards_collection.count_documents({})
        print(f"📊 Total job boards: {total_count}")
        
        # Count active job boards
        active_count = await job_boards_collection.count_documents({"is_active": True})
        print(f"📊 Active job boards: {active_count}")
        
        # Count inactive job boards
        inactive_count = await job_boards_collection.count_documents({"is_active": False})
        print(f"📊 Inactive job boards: {inactive_count}")
        
        # Count by type
        print("\n📊 Job boards by type:")
        pipeline = [
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        async for doc in job_boards_collection.aggregate(pipeline):
            print(f"  - {doc['_id']}: {doc['count']}")
        
        # Count by region
        print("\n📊 Job boards by region:")
        pipeline = [
            {"$group": {"_id": "$region", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        async for doc in job_boards_collection.aggregate(pipeline):
            region = doc['_id'] if doc['_id'] else "(no region)"
            print(f"  - {region}: {doc['count']}")
        
        print()
        
        # Sample some documents
        print("📄 Sample job board documents (first 5):")
        cursor = job_boards_collection.find({}).limit(5)
        sample_docs = await cursor.to_list(length=5)
        
        for i, doc in enumerate(sample_docs, 1):
            print(f"\n--- Sample {i} ---")
            print(f"ID: {doc.get('_id')}")
            print(f"Name: {doc.get('name')}")
            print(f"Type: {doc.get('type')}")
            print(f"Base URL: {doc.get('base_url')}")
            print(f"Region: {doc.get('region')}")
            print(f"Is Active: {doc.get('is_active')}")
            print(f"Created At: {doc.get('created_at')}")
            print(f"Updated At: {doc.get('updated_at')}")
        
        print()
        
        # Test the exact query used by the API
        print("🔍 Testing API query (skip=0, limit=10, active_only=False):")
        api_cursor = job_boards_collection.find({}).skip(0).limit(10)
        api_results = await api_cursor.to_list(length=10)
        print(f"API query returned: {len(api_results)} documents")
        
        if api_results:
            print("First API result:")
            first_result = api_results[0]
            print(f"  - ID: {first_result.get('_id')}")
            print(f"  - Name: {first_result.get('name')}")
            print(f"  - Is Active: {first_result.get('is_active')}")
        
        print()
        
        # Test active only query
        print("🔍 Testing API query (active_only=True):")
        active_cursor = job_boards_collection.find({"is_active": True}).skip(0).limit(10)
        active_results = await active_cursor.to_list(length=10)
        print(f"Active-only query returned: {len(active_results)} documents")
        
        print()
        
        # Check for any data inconsistencies
        print("🔍 Checking for data inconsistencies:")
        
        # Check for documents without required fields
        missing_name = await job_boards_collection.count_documents({"name": {"$exists": False}})
        missing_base_url = await job_boards_collection.count_documents({"base_url": {"$exists": False}})
        missing_is_active = await job_boards_collection.count_documents({"is_active": {"$exists": False}})
        
        print(f"Documents missing 'name': {missing_name}")
        print(f"Documents missing 'base_url': {missing_base_url}")
        print(f"Documents missing 'is_active': {missing_is_active}")
        
        # Check for null values
        null_name = await job_boards_collection.count_documents({"name": None})
        null_base_url = await job_boards_collection.count_documents({"base_url": None})
        null_is_active = await job_boards_collection.count_documents({"is_active": None})
        
        print(f"Documents with null 'name': {null_name}")
        print(f"Documents with null 'base_url': {null_base_url}")
        print(f"Documents with null 'is_active': {null_is_active}")
        
        print()
        
        # Check if there are other collections that might contain job board data
        print("🔍 Checking other collections for job board data:")
        for collection_name in collections:
            if 'job' in collection_name.lower() and collection_name != 'job_boards':
                count = await db[collection_name].count_documents({})
                print(f"  - {collection_name}: {count} documents")
                
                # Sample one document to see structure
                if count > 0:
                    sample = await db[collection_name].find_one({})
                    if sample:
                        print(f"    Sample fields: {list(sample.keys())[:10]}")
        
        print()
        print("✅ MongoDB Atlas analysis complete!")
        
    except Exception as e:
        print(f"❌ Error connecting to MongoDB Atlas: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'client' in locals():
            client.close()
            print("🔌 MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(debug_mongodb_atlas())