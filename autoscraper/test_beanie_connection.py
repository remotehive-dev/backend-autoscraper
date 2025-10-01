#!/usr/bin/env python3
"""
Direct test of Beanie ODM connection to verify job board retrieval.
"""

import asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.models.mongodb_models import JobBoard
from config.settings import get_settings

async def test_beanie_connection():
    """Test Beanie connection and job board retrieval."""
    print("Testing Beanie ODM connection...")
    
    settings = get_settings()
    print(f"MongoDB URL: {settings.MONGODB_URL}")
    print(f"Database Name: {settings.MONGODB_DATABASE_NAME}")
    
    # Create MongoDB client
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    database = client[settings.MONGODB_DATABASE_NAME]
    
    try:
        # Initialize Beanie
        await init_beanie(
            database=database,
            document_models=[JobBoard]
        )
        print("✅ Beanie initialized successfully")
        
        # Test direct collection access
        collection = database.job_boards
        direct_count = await collection.count_documents({})
        print(f"📊 Direct collection count: {direct_count}")
        
        # Test Beanie model access
        beanie_count = await JobBoard.count()
        print(f"📊 Beanie model count: {beanie_count}")
        
        # Get sample documents
        if beanie_count > 0:
            print("\n📋 Sample job boards via Beanie:")
            job_boards = await JobBoard.find().limit(3).to_list()
            for i, jb in enumerate(job_boards, 1):
                print(f"  {i}. {jb.name} - {jb.base_url} (Active: {jb.is_active})")
        
        # Test with filters
        active_count = await JobBoard.find(JobBoard.is_active == True).count()
        print(f"📊 Active job boards: {active_count}")
        
        # Test the exact query used in the API
        print("\n🔍 Testing API-style queries:")
        
        # Query with no filters (like the API)
        all_boards = await JobBoard.find().to_list()
        print(f"  All boards query: {len(all_boards)} results")
        
        # Query with active filter
        active_boards = await JobBoard.find(JobBoard.is_active == True).to_list()
        print(f"  Active boards query: {len(active_boards)} results")
        
        # Check if there's an issue with the model definition
        print("\n🔧 Model inspection:")
        print(f"  JobBoard collection name: {JobBoard.get_collection_name()}")
        print(f"  JobBoard database: {JobBoard.get_motor_collection().database.name}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()
        print("\n🔌 Connection closed")

if __name__ == "__main__":
    asyncio.run(test_beanie_connection())
