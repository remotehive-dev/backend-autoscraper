#!/usr/bin/env python3
"""
Debug the difference between Beanie and Motor access to job_boards collection
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the autoscraper-service directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import get_settings
from motor.motor_asyncio import AsyncIOMotorClient
import json

async def debug_beanie_vs_motor():
    """Debug the difference between Beanie and Motor access"""
    
    print("=== Debugging Beanie vs Motor Access ===")
    
    # Load settings
    settings = get_settings()
    print(f"\nMongoDB URL: {settings.MONGODB_URL}")
    print(f"Database: {settings.MONGODB_DATABASE_NAME}")
    
    # 1. Direct Motor connection
    print("\n1. Testing Direct Motor Connection...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DATABASE_NAME]
    collection = db.job_boards
    
    # Count documents
    motor_count = await collection.count_documents({})
    print(f"   ✓ Motor count: {motor_count}")
    
    # Get sample documents
    if motor_count > 0:
        sample_docs = await collection.find({}).limit(3).to_list(length=3)
        print(f"   ✓ Sample documents found: {len(sample_docs)}")
        
        for i, doc in enumerate(sample_docs):
            print(f"\n   Document {i+1}:")
            print(f"     _id: {doc.get('_id')}")
            print(f"     name: {doc.get('name')}")
            print(f"     type: {doc.get('type')}")
            print(f"     is_active: {doc.get('is_active')}")
            print(f"     base_url: {doc.get('base_url')}")
            print(f"     All keys: {list(doc.keys())}")
    
    # 2. Test Beanie connection
    print("\n\n2. Testing Beanie Connection...")
    
    try:
        # Initialize Beanie manually
        from beanie import init_beanie
        from app.models.mongodb_models import JobBoard
        
        # Initialize Beanie with the same database
        await init_beanie(database=db, document_models=[JobBoard])
        print("   ✓ Beanie initialized successfully")
        
        # Test Beanie queries
        beanie_count = await JobBoard.find().count()
        print(f"   ✓ Beanie count: {beanie_count}")
        
        if beanie_count > 0:
            beanie_docs = await JobBoard.find().limit(3).to_list()
            print(f"   ✓ Beanie documents found: {len(beanie_docs)}")
            
            for i, doc in enumerate(beanie_docs):
                print(f"\n   Beanie Document {i+1}:")
                print(f"     id: {doc.id}")
                print(f"     name: {doc.name}")
                print(f"     type: {doc.type}")
                print(f"     is_active: {doc.is_active}")
        else:
            print("   ✗ No documents found via Beanie")
            
            # Try to understand why Beanie can't find documents
            print("\n   Debugging Beanie collection access...")
            
            # Check if Beanie is using the right collection
            beanie_collection_name = JobBoard.get_collection_name()
            print(f"   ✓ Beanie collection name: {beanie_collection_name}")
            
            # Check if we can access the collection directly through Beanie
            beanie_collection = JobBoard.get_motor_collection()
            beanie_motor_count = await beanie_collection.count_documents({})
            print(f"   ✓ Beanie motor collection count: {beanie_motor_count}")
            
            if beanie_motor_count > 0:
                beanie_motor_doc = await beanie_collection.find_one({})
                print(f"   ✓ Beanie motor sample: {beanie_motor_doc.get('name', 'N/A')}")
    
    except Exception as e:
        print(f"   ✗ Beanie initialization failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Check collection names and database structure
    print("\n\n3. Database Structure Analysis...")
    
    collections = await db.list_collection_names()
    print(f"   ✓ All collections: {collections}")
    
    # Check if there are multiple job board collections
    job_board_collections = [c for c in collections if 'job' in c.lower() or 'board' in c.lower()]
    print(f"   ✓ Job board related collections: {job_board_collections}")
    
    # Check each collection for job board data
    for coll_name in job_board_collections:
        coll = db[coll_name]
        count = await coll.count_documents({})
        print(f"   ✓ Collection '{coll_name}': {count} documents")
        
        if count > 0:
            sample = await coll.find_one({})
            print(f"     Sample keys: {list(sample.keys()) if sample else 'None'}")
    
    # Cleanup
    client.close()
    print("\n=== Debug Complete ===")

if __name__ == "__main__":
    asyncio.run(debug_beanie_vs_motor())