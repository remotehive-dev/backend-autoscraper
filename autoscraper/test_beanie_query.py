#!/usr/bin/env python3

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the JobBoard model
from app.models.mongodb_models import JobBoard

async def test_beanie_query():
    """Test Beanie JobBoard queries directly"""
    
    # Get connection details from environment
    mongodb_url = os.getenv("MONGODB_URL")
    mongodb_database_name = os.getenv("MONGODB_DATABASE_NAME")
    
    print(f"Connecting to: {mongodb_database_name}")
    print(f"URL: {mongodb_url}")
    print("\n" + "="*50)
    
    try:
        # Create MongoDB client
        client = AsyncIOMotorClient(mongodb_url)
        database = client[mongodb_database_name]
        
        # Initialize Beanie with JobBoard model
        await init_beanie(database=database, document_models=[JobBoard])
        
        print("✓ Beanie initialized successfully")
        
        # Test different queries
        print("\n1. Testing JobBoard.find_all()...")
        all_job_boards = await JobBoard.find_all().to_list()
        print(f"Total job boards (find_all): {len(all_job_boards)}")
        
        print("\n2. Testing JobBoard.find({})...")
        job_boards_empty_filter = await JobBoard.find({}).to_list()
        print(f"Total job boards (empty filter): {len(job_boards_empty_filter)}")
        
        print("\n3. Testing JobBoard.find({}).skip(0).limit(100)...")
        job_boards_paginated = await JobBoard.find({}).skip(0).limit(100).to_list()
        print(f"Job boards (paginated): {len(job_boards_paginated)}")
        
        print("\n4. Testing JobBoard.find({}).skip(0).limit(1000)...")
        job_boards_large_limit = await JobBoard.find({}).skip(0).limit(1000).to_list()
        print(f"Job boards (large limit): {len(job_boards_large_limit)}")
        
        print("\n5. Testing JobBoard.find({'is_active': True})...")
        active_job_boards = await JobBoard.find({"is_active": True}).to_list()
        print(f"Active job boards: {len(active_job_boards)}")
        
        print("\n6. Testing JobBoard.count()...")
        total_count = await JobBoard.count()
        print(f"Total count: {total_count}")
        
        print("\n7. Testing active count...")
        active_count = await JobBoard.find({"is_active": True}).count()
        print(f"Active count: {active_count}")
        
        # Show first few job boards
        if job_boards_paginated:
            print("\nFirst 3 job boards from paginated query:")
            for i, jb in enumerate(job_boards_paginated[:3], 1):
                print(f"{i}. {jb.name} - Active: {jb.is_active} - ID: {jb.id}")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_beanie_query())