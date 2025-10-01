#!/usr/bin/env python3
"""
Debug script to test the exact API function logic
"""

import asyncio
import sys
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from datetime import datetime
import uuid
import time

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from config.settings import get_settings
from models.mongodb_models import JobBoard, JobBoardType
from schemas import JobBoardResponse, JobBoardType as SchemaJobBoardType

async def test_list_job_boards_function():
    """
    Test the exact list_job_boards function logic
    """
    try:
        print("=== Testing list_job_boards Function ===")
        
        # Get settings
        settings = get_settings()
        print(f"1. Connecting to database: {settings.MONGODB_DATABASE_NAME}")
        
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        database = client[settings.MONGODB_DATABASE_NAME]
        
        # Test connection
        await client.admin.command('ping')
        print("   ✓ MongoDB connection successful")
        
        # Initialize Beanie
        await init_beanie(
            database=database,
            document_models=[JobBoard]
        )
        print("   ✓ Beanie initialized")
        
        # Test the exact function logic
        print(f"\n2. Testing function logic...")
        
        # Function parameters
        skip = 0
        limit = 5
        active_only = False
        
        start_time = time.time()
        
        # Build MongoDB query (exact same logic as API)
        query_filter = {}
        if active_only:
            query_filter["is_active"] = True
        
        print(f"   Query filter: {query_filter}")
        
        # Execute MongoDB query with pagination (exact same logic as API)
        job_boards = await JobBoard.find(query_filter).skip(skip).limit(limit).to_list()
        
        print(f"   Found {len(job_boards)} job boards")
        
        if not job_boards:
            print("   ✗ No job boards found!")
            
            # Debug: Try different queries
            print(f"\n3. Debug queries...")
            
            # Try without filter
            all_boards = await JobBoard.find().to_list()
            print(f"   All boards (no filter): {len(all_boards)}")
            
            # Try with active filter
            active_boards = await JobBoard.find({"is_active": True}).to_list()
            print(f"   Active boards: {len(active_boards)}")
            
            # Try count
            total_count = await JobBoard.find().count()
            print(f"   Total count: {total_count}")
            
            return
        
        # Map MongoDB models to response schema (exact same logic as API)
        response_data = []
        for jb in job_boards:
            print(f"   Processing: {jb.name}")
            
            # Convert MongoDB ObjectId to UUID format for response schema
            object_id_str = str(jb.id)
            # Create a deterministic UUID from ObjectId
            uuid_from_objectid = str(uuid.uuid5(uuid.NAMESPACE_DNS, object_id_str))
            
            # Map job board type to valid enum values
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
            
            response_item = {
                "id": uuid_from_objectid,
                "name": jb.name,
                "description": jb.notes or "",  # Use notes field as description
                "type": mapped_type,
                "base_url": jb.base_url,
                "rss_url": getattr(jb, 'search_url_template', None),  # Use search_url_template as rss_url
                "region": getattr(jb, 'region', None),  # Add region field from MongoDB model
                "selectors": jb.selectors or {},
                "rate_limit_delay": int(jb.rate_limit_delay or 2),
                "max_pages": jb.max_pages_per_search or 10,  # Use max_pages_per_search
                "request_timeout": 30,  # Default value as not in MongoDB model
                "retry_attempts": 3,  # Default value as not in MongoDB model
                "is_active": jb.is_active,
                "success_rate": jb.success_rate or 0.0,
                "last_scraped_at": jb.last_successful_scrape,  # Use last_successful_scrape
                "total_scrapes": jb.total_jobs_scraped or 0,  # Use total_jobs_scraped
                "successful_scrapes": 0,  # Default value as not in MongoDB model
                "failed_scrapes": 0,  # Default value as not in MongoDB model
                "created_at": jb.created_at,
                "updated_at": jb.updated_at
            }
            
            try:
                response_obj = JobBoardResponse(**response_item)
                response_data.append(response_obj)
                print(f"     ✓ Successfully created response for {jb.name}")
            except Exception as e:
                print(f"     ✗ Failed to create response for {jb.name}: {e}")
        
        duration = time.time() - start_time
        
        print(f"\n3. Results:")
        print(f"   Total processed: {len(response_data)}")
        print(f"   Duration: {duration:.3f}s")
        
        # Print first result
        if response_data:
            first = response_data[0]
            print(f"   First result:")
            print(f"     ID: {first.id}")
            print(f"     Name: {first.name}")
            print(f"     Type: {first.type}")
            print(f"     Active: {first.is_active}")
        
        print(f"\n=== Test Complete ===")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Close connection
        if 'client' in locals():
            client.close()
            print("MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(test_list_job_boards_function())