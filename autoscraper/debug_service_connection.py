#!/usr/bin/env python3
"""
Debug script to test the exact database connection used by the running service
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.mongodb_models import JobBoard
from config.settings import AutoscraperSettings

async def test_service_connection():
    """Test the exact connection method used by the service"""
    print("=== Testing Service Database Connection ===")
    
    # Load settings exactly like the service does
    settings = AutoscraperSettings()
    print(f"MongoDB URL from settings: {settings.MONGODB_URL}")
    print(f"Database name from settings: {settings.MONGODB_DATABASE_NAME}")
    
    # Connect using the same method as the service
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    database = client[settings.MONGODB_DATABASE_NAME]
    
    print(f"\nConnected to database: {database.name}")
    
    # List all collections
    collections = await database.list_collection_names()
    print(f"Collections in database: {collections}")
    
    # Check job_boards collection specifically
    if "job_boards" in collections:
        job_boards_collection = database["job_boards"]
        count = await job_boards_collection.count_documents({})
        print(f"\nDirect collection count: {count} job boards")
        
        if count > 0:
            # Get a sample document
            sample = await job_boards_collection.find_one({})
            print(f"Sample document keys: {list(sample.keys()) if sample else 'None'}")
            if sample:
                print(f"Sample document name: {sample.get('name', 'No name field')}")
                print(f"Sample document type: {sample.get('type', 'No type field')}")
                print(f"Sample document is_active: {sample.get('is_active', 'No is_active field')}")
    
    # Now test with Beanie initialization
    print("\n=== Testing Beanie Initialization ===")
    
    try:
        # Initialize Beanie with the JobBoard model
        await init_beanie(database=database, document_models=[JobBoard])
        print("Beanie initialized successfully")
        
        # Test Beanie queries
        total_count = await JobBoard.count()
        print(f"Beanie total count: {total_count}")
        
        active_count = await JobBoard.find({"is_active": True}).count()
        print(f"Beanie active count: {active_count}")
        
        # Test the exact query used by the API
        query_filter = {}
        job_boards = await JobBoard.find(query_filter).skip(0).limit(10).to_list()
        print(f"Beanie API query result count: {len(job_boards)}")
        
        if job_boards:
            first_board = job_boards[0]
            print(f"First job board name: {first_board.name}")
            print(f"First job board type: {first_board.type}")
            print(f"First job board is_active: {first_board.is_active}")
        
    except Exception as e:
        print(f"Beanie initialization failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Close the connection
    client.close()
    print("\n=== Connection Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_service_connection())