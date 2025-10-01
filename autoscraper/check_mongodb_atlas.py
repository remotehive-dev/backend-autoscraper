#!/usr/bin/env python3
"""
Direct MongoDB Atlas Connection Test
Check actual job boards count in the database
"""

import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from config.settings import settings

async def check_mongodb_atlas():
    """
    Direct check of MongoDB Atlas database
    """
    try:
        print("=== MongoDB Atlas Connection Test ===")
        print(f"MongoDB URL: {settings.MONGODB_URL}")
        print(f"Database Name: {settings.MONGODB_DATABASE_NAME}")
        
        # Connect to MongoDB Atlas
        print("\n1. Connecting to MongoDB Atlas...")
        client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000
        )
        
        # Test connection
        try:
            await client.admin.command('ping')
            print("✓ Successfully connected to MongoDB Atlas")
        except Exception as e:
            print(f"✗ Failed to ping MongoDB: {e}")
            return
        
        # Get database
        database = client[settings.MONGODB_DATABASE_NAME]
        
        # List all collections
        print("\n2. Listing all collections...")
        collections = await database.list_collection_names()
        print(f"Collections found: {collections}")
        
        # Check job_boards collection specifically
        if 'job_boards' in collections:
            print("\n3. Checking job_boards collection...")
            job_boards_collection = database['job_boards']
            
            # Count total documents
            total_count = await job_boards_collection.count_documents({})
            print(f"Total job boards in collection: {total_count}")
            
            if total_count > 0:
                # Get a sample document
                print("\n4. Sample job board document:")
                sample_doc = await job_boards_collection.find_one({})
                if sample_doc:
                    print(f"Sample document keys: {list(sample_doc.keys())}")
                    print(f"Sample document ID: {sample_doc.get('_id')}")
                    print(f"Sample document name: {sample_doc.get('name', 'N/A')}")
                    print(f"Sample document URL: {sample_doc.get('url', 'N/A')}")
                    print(f"Sample document status: {sample_doc.get('status', 'N/A')}")
                
                # Check for any filtering conditions that might affect the API
                print("\n5. Checking document status distribution...")
                pipeline = [
                    {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}}
                ]
                status_counts = await job_boards_collection.aggregate(pipeline).to_list(None)
                print(f"Status distribution: {status_counts}")
                
                # Check for active job boards specifically
                active_count = await job_boards_collection.count_documents({"status": "active"})
                print(f"Active job boards: {active_count}")
                
                # Check for any other status values
                enabled_count = await job_boards_collection.count_documents({"status": "enabled"})
                print(f"Enabled job boards: {enabled_count}")
                
                # Check for documents without status field
                no_status_count = await job_boards_collection.count_documents({"status": {"$exists": False}})
                print(f"Job boards without status field: {no_status_count}")
                
            else:
                print("No job boards found in the collection!")
        else:
            print("\n✗ job_boards collection not found!")
            print("Available collections:", collections)
        
        # Check other potential collections
        print("\n6. Checking for other potential job board collections...")
        for collection_name in collections:
            if 'job' in collection_name.lower() or 'board' in collection_name.lower():
                collection = database[collection_name]
                count = await collection.count_documents({})
                print(f"Collection '{collection_name}': {count} documents")
        
        # Close connection
        client.close()
        print("\n✓ Connection closed successfully")
        
    except ServerSelectionTimeoutError as e:
        print(f"✗ MongoDB connection timeout: {e}")
    except Exception as e:
        print(f"✗ Error checking MongoDB Atlas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_mongodb_atlas())