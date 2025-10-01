#!/usr/bin/env python3
"""
Debug script to test MongoDB job boards query directly
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

async def debug_job_boards_query():
    """Debug the job boards MongoDB query"""
    
    try:
        # Import settings and database
        from config.settings import settings
        from app.database.database import DatabaseManager
        from app.models.mongodb_models import JobBoard
        
        print(f"Settings loaded:")
        print(f"  MongoDB URL: {settings.MONGODB_URL}")
        print(f"  Database Name: {settings.MONGODB_DATABASE_NAME}")
        
        # Initialize database
        print("\nInitializing database...")
        db_manager = DatabaseManager()
        await db_manager.initialize()
        print("Database initialized successfully")
        
        # Test 1: Count all job boards
        print("\n=== Test 1: Count all job boards ===")
        total_count = await JobBoard.count()
        print(f"Total job boards in collection: {total_count}")
        
        # Test 2: Find all job boards (no filter)
        print("\n=== Test 2: Find all job boards (no filter) ===")
        all_job_boards = await JobBoard.find().to_list()
        print(f"Found {len(all_job_boards)} job boards")
        
        if all_job_boards:
            first_jb = all_job_boards[0]
            print(f"First job board:")
            print(f"  ID: {first_jb.id}")
            print(f"  Name: {first_jb.name}")
            print(f"  Type: {first_jb.type}")
            print(f"  Base URL: {first_jb.base_url}")
            print(f"  Is Active: {first_jb.is_active}")
            print(f"  Created At: {first_jb.created_at}")
        
        # Test 3: Find with active_only=False filter (same as API)
        print("\n=== Test 3: Find with empty filter (active_only=False) ===")
        query_filter = {}
        filtered_job_boards = await JobBoard.find(query_filter).to_list()
        print(f"Found {len(filtered_job_boards)} job boards with empty filter")
        
        # Test 4: Find with active_only=True filter
        print("\n=== Test 4: Find with active filter (active_only=True) ===")
        active_filter = {"is_active": True}
        active_job_boards = await JobBoard.find(active_filter).to_list()
        print(f"Found {len(active_job_boards)} active job boards")
        
        # Test 5: Find with pagination (same as API)
        print("\n=== Test 5: Find with pagination (skip=0, limit=5) ===")
        paginated_job_boards = await JobBoard.find({}).skip(0).limit(5).to_list()
        print(f"Found {len(paginated_job_boards)} job boards with pagination")
        
        for i, jb in enumerate(paginated_job_boards):
            print(f"  {i+1}. {jb.name} - Active: {jb.is_active}")
        
        # Test 6: Check database connection details
        print("\n=== Test 6: Database connection details ===")
        from motor.motor_asyncio import AsyncIOMotorClient
        
        # Get the actual client from Beanie
        client = JobBoard.get_motor_client()
        if client:
            db_name = client.get_default_database().name
            print(f"Connected database name: {db_name}")
            
            # List collections
            collections = await client.get_default_database().list_collection_names()
            print(f"Collections in database: {collections}")
            
            # Check job_boards collection specifically
            if 'job_boards' in collections:
                job_boards_collection = client.get_default_database()['job_boards']
                raw_count = await job_boards_collection.count_documents({})
                print(f"Raw count from job_boards collection: {raw_count}")
                
                # Get a sample document
                sample_doc = await job_boards_collection.find_one({})
                if sample_doc:
                    print(f"Sample raw document keys: {list(sample_doc.keys())}")
                    print(f"Sample document: {sample_doc}")
        
    except Exception as e:
        print(f"Error during debug: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_job_boards_query())