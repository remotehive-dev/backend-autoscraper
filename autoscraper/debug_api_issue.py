#!/usr/bin/env python3

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def debug_api_issue():
    """Debug why the API returns only 3 job boards"""
    
    # Initialize database connection
    from app.core.database import DatabaseManager
    from app.models.mongodb_models import JobBoard
    
    db_manager = DatabaseManager()
    await db_manager.init_database()
    
    print("=== Testing JobBoard queries ===")
    
    # Test 1: Basic count
    total_count = await JobBoard.count()
    print(f"Total job boards in database: {total_count}")
    
    # Test 2: Query with no filters (like the API)
    query_filter = {}
    job_boards = await JobBoard.find(query_filter).skip(0).limit(100).to_list()
    print(f"Query with no filters returned: {len(job_boards)} job boards")
    
    # Test 3: Query with active_only=False (like the API call we tested)
    # Note: active_only=False means no filter is applied
    job_boards_no_active_filter = await JobBoard.find({}).skip(0).limit(100).to_list()
    print(f"Query with no active filter returned: {len(job_boards_no_active_filter)} job boards")
    
    # Test 4: Query with active_only=True
    active_job_boards = await JobBoard.find({"is_active": True}).skip(0).limit(100).to_list()
    print(f"Query with is_active=True returned: {len(active_job_boards)} job boards")
    
    # Test 5: Check if there are any validation issues
    print("\n=== Checking first few job boards for validation issues ===")
    first_few = await JobBoard.find({}).limit(5).to_list()
    
    for i, jb in enumerate(first_few, 1):
        try:
            # Try to access all fields that the API uses
            print(f"{i}. {jb.name}:")
            print(f"   - ID: {jb.id}")
            print(f"   - Type: {jb.type}")
            print(f"   - Base URL: {jb.base_url}")
            print(f"   - Is Active: {jb.is_active}")
            print(f"   - Selectors: {type(jb.selectors)}")
            print(f"   - Created: {jb.created_at}")
            
            # Test the UUID conversion that the API does
            import uuid
            object_id_str = str(jb.id)
            uuid_from_objectid = str(uuid.uuid5(uuid.NAMESPACE_DNS, object_id_str))
            print(f"   - UUID conversion: {uuid_from_objectid}")
            
        except Exception as e:
            print(f"   - ERROR accessing fields: {e}")
    
    # Test 6: Simulate the exact API logic
    print("\n=== Simulating exact API logic ===")
    try:
        # This is exactly what the API does
        skip = 0
        limit = 100
        active_only = False
        
        query_filter = {}
        if active_only:
            query_filter["is_active"] = True
        
        job_boards = await JobBoard.find(query_filter).skip(skip).limit(limit).to_list()
        print(f"Exact API simulation returned: {len(job_boards)} job boards")
        
        # Try to process them like the API does
        response_data = []
        for jb in job_boards[:3]:  # Just test first 3
            import uuid
            object_id_str = str(jb.id)
            uuid_from_objectid = str(uuid.uuid5(uuid.NAMESPACE_DNS, object_id_str))
            
            type_mapping = {
                "indeed": "html",
                "linkedin": "html",
                "glassdoor": "html",
                "monster": "html",
                "dice": "html",
                "custom": "html"
            }
            
            job_type = jb.type.value if jb.type else "html"
            mapped_type = type_mapping.get(job_type.lower(), job_type)
            
            response_item = {
                "id": uuid_from_objectid,
                "name": jb.name,
                "description": jb.notes or "",
                "type": mapped_type,
                "base_url": jb.base_url,
                "rss_url": getattr(jb, 'search_url_template', None),
                "selectors": jb.selectors or {},
                "rate_limit_delay": int(jb.rate_limit_delay or 2),
                "max_pages": jb.max_pages_per_search or 10,
                "request_timeout": 30,
                "retry_attempts": 3,
                "is_active": jb.is_active,
                "success_rate": jb.success_rate or 0.0,
                "last_scraped_at": jb.last_successful_scrape,
                "total_scrapes": jb.total_jobs_scraped or 0,
                "successful_scrapes": 0,
                "failed_scrapes": 0,
                "created_at": jb.created_at,
                "updated_at": jb.updated_at
            }
            response_data.append(response_item)
            print(f"Successfully processed: {jb.name}")
            
        print(f"Successfully processed {len(response_data)} job boards without errors")
        
    except Exception as e:
        print(f"Error in API simulation: {e}")
        import traceback
        traceback.print_exc()
    
    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(debug_api_issue())