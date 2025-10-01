#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append('/Users/ranjeettiwary/Downloads/developer/RemoteHive_Migration_Package/autoscraper-service')

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def debug_beanie_query():
    """Debug the Beanie query that the API is using"""
    
    # Get connection details from environment
    mongodb_url = os.getenv('MONGODB_URL')
    database_name = os.getenv('MONGODB_DATABASE_NAME')
    
    print(f"Connecting to: {database_name} database")
    print(f"MongoDB URL: {mongodb_url[:50]}...")
    
    # Create MongoDB client
    client = AsyncIOMotorClient(mongodb_url)
    database = client[database_name]
    
    try:
        # Import the JobBoard model
        from app.models.mongodb_models import JobBoard
        
        # Initialize Beanie with the JobBoard model
        await init_beanie(database=database, document_models=[JobBoard])
        
        print("\n--- Testing Beanie JobBoard.find() query ---")
        
        # Test the exact query used by the API
        query_filter = {}
        
        print(f"Query filter: {query_filter}")
        
        # Execute the same query as the API
        job_boards = await JobBoard.find(query_filter).skip(0).limit(1000).to_list()
        
        print(f"Beanie query returned: {len(job_boards)} results")
        
        if job_boards:
            print("\n--- Sample Beanie results ---")
            for i, jb in enumerate(job_boards[:3]):
                print(f"Job Board {i+1}:")
                print(f"  ID: {jb.id}")
                print(f"  Name: {jb.name}")
                print(f"  Type: {jb.type}")
                print(f"  Is Active: {jb.is_active}")
                print(f"  Base URL: {jb.base_url}")
                print()
        
        # Test with active_only=True filter
        print("\n--- Testing Beanie query with active_only=True ---")
        active_filter = {"is_active": True}
        active_job_boards = await JobBoard.find(active_filter).skip(0).limit(1000).to_list()
        print(f"Beanie query (active_only=True) returned: {len(active_job_boards)} results")
        
        # Check collection name
        print(f"\n--- Collection Information ---")
        print(f"JobBoard collection name: {JobBoard.get_collection_name()}")
        
        # Check if there are any issues with the model settings
        print(f"JobBoard model settings: {JobBoard.Settings.__dict__ if hasattr(JobBoard, 'Settings') else 'No Settings'}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(debug_beanie_query())