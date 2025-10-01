#!/usr/bin/env python3
"""
Direct test of MongoDB connection and job boards query
from within the autoscraper service context.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from config.settings import get_settings
    from app.database.mongodb_manager import init_autoscraper_mongodb, get_autoscraper_mongodb_manager
    from app.models.mongodb_models import JobBoard
    from beanie import init_beanie
    from motor.motor_asyncio import AsyncIOMotorClient
    
    settings = get_settings()
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

async def test_connection():
    """Test MongoDB connection and query job boards"""
    print("=== Testing MongoDB Connection ===")
    print(f"MongoDB URL: {settings.MONGODB_URL}")
    print(f"Database Name: {settings.MONGODB_DATABASE_NAME}")
    
    try:
        # Initialize MongoDB connection
        print("\n1. Initializing MongoDB connection...")
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        database = client[settings.MONGODB_DATABASE_NAME]
        
        # Test connection
        print("\n2. Testing connection...")
        server_info = await client.server_info()
        print(f"Connected to MongoDB version: {server_info.get('version', 'Unknown')}")
        
        # List collections
        print("\n3. Listing collections...")
        collections = await database.list_collection_names()
        print(f"Collections found: {collections}")
        
        # Check if job_boards collection exists
        if 'job_boards' in collections:
            print("\n4. Checking job_boards collection...")
            job_boards_collection = database['job_boards']
            
            # Count total documents
            total_count = await job_boards_collection.count_documents({})
            print(f"Total job boards in collection: {total_count}")
            
            # Count active documents
            active_count = await job_boards_collection.count_documents({"is_active": True})
            print(f"Active job boards: {active_count}")
            
            # Count inactive documents
            inactive_count = await job_boards_collection.count_documents({"is_active": False})
            print(f"Inactive job boards: {inactive_count}")
            
            # Count null status documents
            null_count = await job_boards_collection.count_documents({"is_active": None})
            print(f"Job boards with null is_active: {null_count}")
            
            # Get sample documents
            print("\n5. Sample job boards:")
            async for doc in job_boards_collection.find({}).limit(3):
                print(f"  - Name: {doc.get('name', 'N/A')}, Active: {doc.get('is_active', 'N/A')}, Type: {doc.get('type', 'N/A')}")
        else:
            print("\n4. job_boards collection not found!")
        
        # Now test with Beanie ODM
        print("\n6. Testing with Beanie ODM...")
        try:
            await init_beanie(database=database, document_models=[JobBoard])
            print("Beanie initialized successfully")
            
            # Query using Beanie
            total_beanie = await JobBoard.count()
            print(f"Total job boards via Beanie: {total_beanie}")
            
            active_beanie = await JobBoard.find({"is_active": True}).count()
            print(f"Active job boards via Beanie: {active_beanie}")
            
            # Get sample via Beanie
            sample_boards = await JobBoard.find().limit(3).to_list()
            print(f"Sample job boards via Beanie: {len(sample_boards)}")
            for board in sample_boards:
                print(f"  - {board.name}: active={board.is_active}, type={board.type}")
                
        except Exception as beanie_error:
            print(f"Beanie error: {beanie_error}")
        
    except Exception as e:
        print(f"Connection error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    asyncio.run(test_connection())
