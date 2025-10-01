#!/usr/bin/env python3
"""
Debug script to check actual collection names in MongoDB Atlas
and compare with what Beanie expects.
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.mongodb_models import JobBoard
from config.settings import get_settings

async def debug_collection_names():
    print("=== Collection Names Debug ===")
    
    # Get settings
    settings = get_settings()
    mongodb_url = settings.MONGODB_URL
    database_name = settings.MONGODB_DATABASE_NAME
    
    print(f"MongoDB URL: {mongodb_url}")
    print(f"Database Name: {database_name}")
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(mongodb_url)
    database = client[database_name]
    
    print("\n1. Listing all collections in database...")
    collections = await database.list_collection_names()
    print(f"Found {len(collections)} collections:")
    for i, collection in enumerate(collections, 1):
        print(f"  {i}. {collection}")
    
    print("\n2. Checking JobBoard model collection name...")
    print(f"JobBoard model expects collection: '{JobBoard.Settings.name}'")
    
    print("\n3. Checking if expected collection exists...")
    expected_collection = JobBoard.Settings.name
    if expected_collection in collections:
        print(f"✅ Collection '{expected_collection}' exists")
        
        # Count documents in the expected collection
        count = await database[expected_collection].count_documents({})
        print(f"   Documents in '{expected_collection}': {count}")
        
        # Get a sample document
        sample = await database[expected_collection].find_one({})
        if sample:
            print(f"   Sample document keys: {list(sample.keys())}")
        else:
            print("   No documents found")
    else:
        print(f"❌ Collection '{expected_collection}' does NOT exist")
    
    print("\n4. Checking for similar collection names...")
    similar_names = [col for col in collections if 'job' in col.lower() or 'board' in col.lower()]
    if similar_names:
        print(f"Found {len(similar_names)} collections with 'job' or 'board' in name:")
        for name in similar_names:
            count = await database[name].count_documents({})
            print(f"  - {name}: {count} documents")
            
            # Get sample document from each
            sample = await database[name].find_one({})
            if sample:
                print(f"    Sample keys: {list(sample.keys())[:10]}...")  # First 10 keys
    else:
        print("No collections found with 'job' or 'board' in name")
    
    print("\n5. Initializing Beanie and testing...")
    try:
        await init_beanie(database=database, document_models=[JobBoard])
        print("✅ Beanie initialized successfully")
        
        # Test Beanie query
        beanie_count = await JobBoard.count()
        print(f"Beanie JobBoard count: {beanie_count}")
        
        # Test direct collection access through Beanie
        collection_name = JobBoard.get_collection_name()
        print(f"Beanie reports collection name as: '{collection_name}'")
        
    except Exception as e:
        print(f"❌ Beanie initialization failed: {e}")
    
    # Close connection
    client.close()
    print("\n✅ Disconnected from MongoDB")

if __name__ == "__main__":
    asyncio.run(debug_collection_names())