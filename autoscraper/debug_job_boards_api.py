#!/usr/bin/env python3
"""
Debug script to test the job boards API endpoint directly
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def debug_job_boards_api():
    try:
        # Import required modules
        from config.settings import get_settings
        from app.database.mongodb import init_mongodb
        from app.models.mongodb_models import JobBoard
        
        print("=== Debug Job Boards API ===")
        print(f"Timestamp: {datetime.now()}")
        
        # Initialize settings and database
        settings = get_settings()
        print(f"MongoDB URL: {settings.MONGODB_URL}")
        
        await init_mongodb()
        print("✓ MongoDB connection initialized")
        
        # Test the exact query used in the API
        print("\n=== Testing API Query Logic ===")
        
        # Test 1: Query without filters (same as active_only=False)
        query_filter = {}
        print(f"Query filter: {query_filter}")
        
        job_boards = await JobBoard.find(query_filter).skip(0).limit(10).to_list()
        print(f"Found {len(job_boards)} job boards with no filter")
        
        if job_boards:
            print("\nSample job boards:")
            for i, jb in enumerate(job_boards[:3]):
                print(f"  {i+1}. {jb.name} - Active: {jb.is_active} - Type: {jb.type}")
        
        # Test 2: Query with active_only=True
        query_filter = {"is_active": True}
        print(f"\nQuery filter with active_only: {query_filter}")
        
        active_job_boards = await JobBoard.find(query_filter).skip(0).limit(10).to_list()
        print(f"Found {len(active_job_boards)} active job boards")
        
        # Test 3: Count all documents
        total_count = await JobBoard.count()
        print(f"\nTotal job boards in collection: {total_count}")
        
        # Test 4: Check if there are any issues with the response mapping
        if job_boards:
            print("\n=== Testing Response Mapping ===")
            jb = job_boards[0]
            print(f"Sample job board data:")
            print(f"  ID: {jb.id}")
            print(f"  Name: {jb.name}")
            print(f"  Type: {jb.type}")
            print(f"  Base URL: {jb.base_url}")
            print(f"  Is Active: {jb.is_active}")
            print(f"  Created At: {jb.created_at}")
            
            # Test UUID conversion
            import uuid
            object_id_str = str(jb.id)
            uuid_from_objectid = str(uuid.uuid5(uuid.NAMESPACE_DNS, object_id_str))
            print(f"  UUID conversion: {uuid_from_objectid}")
            
            # Test type mapping
            type_mapping = {
                "indeed": "html",
                "linkedin": "html",
                "glassdoor": "html",
                "monster": "html",
                "ziprecruiter": "html",
                "careerbuilder": "html",
                "dice": "html",
                "remote_ok": "html",
                "we_work_remotely": "html",
                "angellist": "html",
                "flexjobs": "html",
                "upwork": "html",
                "freelancer": "html",
                "toptal": "html",
                "guru": "html",
                "stackoverflow": "html",
                "github_jobs": "html",
                "custom": "html"
            }
            
            job_type = jb.type.value if jb.type else "html"
            mapped_type = type_mapping.get(job_type.lower(), job_type)
            print(f"  Type mapping: {job_type} -> {mapped_type}")
        
        print("\n=== Debug Complete ===")
        
    except Exception as e:
        print(f"Error during debug: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_job_boards_api())