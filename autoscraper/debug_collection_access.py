#!/usr/bin/env python3
"""
Debug script to test direct collection access vs Beanie model access
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from config.settings import get_settings
from app.models.mongodb_models import JobBoard

async def debug_collection_access():
    """Debug collection access methods"""
    settings = get_settings()
    
    print(f"Settings - MongoDB URL: {settings.MONGODB_URL[:50]}...")
    print(f"Settings - Database Name: {settings.MONGODB_DATABASE_NAME}")
    
    # Create MongoDB client
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    database = client[settings.MONGODB_DATABASE_NAME]
    
    print(f"\n=== Direct MongoDB Collection Access ===")
    
    # List all collections in the database
    collections = await database.list_collection_names()
    print(f"Collections in database '{settings.MONGODB_DATABASE_NAME}': {collections}")
    
    # Direct collection access
    job_boards_collection = database.job_boards
    direct_count = await job_boards_collection.count_documents({})
    print(f"Direct collection count: {direct_count}")
    
    if direct_count > 0:
        # Get a sample document directly
        sample_doc = await job_boards_collection.find_one({})
        print(f"Sample document keys: {list(sample_doc.keys()) if sample_doc else 'None'}")
        if sample_doc:
            print(f"Sample document _id: {sample_doc.get('_id')}")
            print(f"Sample document name: {sample_doc.get('name')}")
            print(f"Sample document is_active: {sample_doc.get('is_active')}")
    
    print(f"\n=== Initialize Beanie and Test Model Access ===")
    
    # Initialize Beanie
    await init_beanie(
        database=database,
        document_models=[JobBoard]
    )
    
    print("Beanie initialized successfully")
    
    # Test Beanie model access
    beanie_count = await JobBoard.count()
    print(f"Beanie model count: {beanie_count}")
    
    # Check what collection Beanie is using
    print(f"JobBoard model collection name: {JobBoard.get_collection_name()}")
    
    # Try to find all job boards with Beanie
    all_job_boards = await JobBoard.find().to_list()
    print(f"Beanie find().to_list() returned {len(all_job_boards)} documents")
    
    if len(all_job_boards) > 0:
        sample_board = all_job_boards[0]
        print(f"Sample JobBoard from Beanie:")
        print(f"  - ID: {sample_board.id}")
        print(f"  - Name: {sample_board.name}")
        print(f"  - Type: {sample_board.type}")
        print(f"  - Is Active: {sample_board.is_active}")
    
    # Test with query filter (like the API does)
    print(f"\n=== Test API-style Query ===")
    query_filter = {}
    api_style_count = await JobBoard.find(query_filter).count()
    print(f"API-style count with empty filter: {api_style_count}")
    
    api_style_results = await JobBoard.find(query_filter).limit(5).to_list()
    print(f"API-style results with limit 5: {len(api_style_results)} documents")
    
    # Test active filter
    active_filter = {"is_active": True}
    active_count = await JobBoard.find(active_filter).count()
    print(f"Active job boards count: {active_count}")
    
    # Close connection
    client.close()
    print("\nConnection closed")

if __name__ == "__main__":
    asyncio.run(debug_collection_access())