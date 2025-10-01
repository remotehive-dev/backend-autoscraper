#!/usr/bin/env python3
"""
Debug script to test the exact Beanie query logic used in the API
"""

import asyncio
import sys
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from config.settings import get_settings
from models.mongodb_models import JobBoard, JobBoardType
from schemas import JobBoardResponse

async def debug_beanie_query():
    """
    Test the exact Beanie query logic used in the API
    """
    try:
        print("=== Beanie Query Debug ===")
        
        # Get settings
        settings = get_settings()
        print(f"1. Database: {settings.MONGODB_DATABASE_NAME}")
        print(f"   URL: {settings.MONGODB_URL[:50]}...")
        
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        database = client[settings.MONGODB_DATABASE_NAME]
        
        # Test connection
        await client.admin.command('ping')
        print("   ✓ MongoDB connection successful")
        
        # Initialize Beanie with JobBoard model
        print(f"\n2. Initializing Beanie ODM...")
        await init_beanie(
            database=database,
            document_models=[JobBoard]
        )
        print("   ✓ Beanie initialized")
        
        # Test the exact query logic from the API
        print(f"\n3. Testing API query logic:")
        
        # Parameters from API call
        limit = 5
        skip = 0
        active_only = False
        job_board_type = None
        search_query = None
        
        print(f"   Parameters: limit={limit}, skip={skip}, active_only={active_only}")
        
        # Build query (exact same logic as API)
        query_filter = {}
        
        if active_only:
            query_filter["is_active"] = True
            print(f"   Added filter: is_active = True")
        
        if job_board_type:
            query_filter["type"] = job_board_type
            print(f"   Added filter: type = {job_board_type}")
        
        if search_query:
            query_filter["$or"] = [
                {"name": {"$regex": search_query, "$options": "i"}},
                {"base_url": {"$regex": search_query, "$options": "i"}}
            ]
            print(f"   Added search filter: {search_query}")
        
        print(f"   Final query filter: {query_filter}")
        
        # Execute query using Beanie
        print(f"\n4. Executing Beanie query...")
        
        # Count total documents
        total_count = await JobBoard.count()
        print(f"   Total JobBoard documents: {total_count}")
        
        # Count with filter
        if query_filter:
            filtered_count = await JobBoard.find(query_filter).count()
            print(f"   Filtered count: {filtered_count}")
        else:
            filtered_count = total_count
            print(f"   No filter applied, using total count: {filtered_count}")
        
        # Execute the actual query
        if query_filter:
            job_boards = await JobBoard.find(query_filter).skip(skip).limit(limit).to_list()
        else:
            job_boards = await JobBoard.find().skip(skip).limit(limit).to_list()
        
        print(f"   Query returned: {len(job_boards)} documents")
        
        # Show sample results
        if job_boards:
            print(f"\n5. Sample results:")
            for i, job_board in enumerate(job_boards[:3]):
                print(f"   [{i+1}] {job_board.name} ({job_board.type}) - Active: {job_board.is_active}")
                print(f"       ID: {job_board.id}")
                print(f"       URL: {job_board.base_url}")
        else:
            print(f"\n5. No results returned!")
            
            # Additional debugging
            print(f"\n   Additional debugging:")
            
            # Try a simple find_all
            all_boards = await JobBoard.find().limit(3).to_list()
            print(f"   Simple find().limit(3): {len(all_boards)} documents")
            
            if all_boards:
                for board in all_boards:
                    print(f"     - {board.name}: {board.type}, active={board.is_active}")
            
            # Check collection name
            collection_name = JobBoard.get_collection_name()
            print(f"   JobBoard collection name: {collection_name}")
            
            # Check database collections
            collections = await database.list_collection_names()
            print(f"   Available collections: {collections}")
        
        # Test response mapping
        if job_boards:
            print(f"\n6. Testing response mapping:")
            try:
                first_board = job_boards[0]
                response = JobBoardResponse(
                    id=str(first_board.id),
                    name=first_board.name,
                    type=first_board.type,
                    base_url=first_board.base_url,
                    region=first_board.region,
                    is_active=first_board.is_active,
                    total_jobs_scraped=first_board.total_jobs_scraped,
                    success_rate=first_board.success_rate,
                    average_response_time=first_board.average_response_time,
                    last_successful_scrape=first_board.last_successful_scrape,
                    created_at=first_board.created_at,
                    updated_at=first_board.updated_at
                )
                print(f"   ✓ Response mapping successful")
                print(f"   Response ID: {response.id}")
                print(f"   Response name: {response.name}")
            except Exception as e:
                print(f"   ✗ Response mapping failed: {e}")
        
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
    asyncio.run(debug_beanie_query())