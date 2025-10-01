#!/usr/bin/env python3
"""
Debug script to test the exact response mapping logic
"""

import asyncio
import sys
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from datetime import datetime
import uuid

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from config.settings import get_settings
from models.mongodb_models import JobBoard, JobBoardType
from schemas import JobBoardResponse, JobBoardType as SchemaJobBoardType

async def debug_response_mapping():
    """
    Test the exact response mapping logic from the API
    """
    try:
        print("=== Response Mapping Debug ===")
        
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
        
        # Get one job board
        print(f"\n2. Getting sample job board...")
        job_board = await JobBoard.find_one({})
        
        if not job_board:
            print("   No job boards found!")
            return
        
        print(f"   Found: {job_board.name}")
        print(f"   Type: {job_board.type}")
        print(f"   Active: {job_board.is_active}")
        
        # Test field mapping
        print(f"\n3. Testing field mapping...")
        
        # Check all required fields
        print(f"   Database fields:")
        print(f"     - id: {job_board.id} ({type(job_board.id)})")
        print(f"     - name: {job_board.name}")
        print(f"     - type: {job_board.type} ({type(job_board.type)})")
        print(f"     - base_url: {job_board.base_url}")
        print(f"     - region: {getattr(job_board, 'region', 'NOT_FOUND')}")
        print(f"     - rate_limit_delay: {job_board.rate_limit_delay} ({type(job_board.rate_limit_delay)})")
        print(f"     - max_pages_per_search: {job_board.max_pages_per_search}")
        print(f"     - is_active: {job_board.is_active}")
        print(f"     - success_rate: {job_board.success_rate}")
        print(f"     - last_successful_scrape: {job_board.last_successful_scrape}")
        print(f"     - total_jobs_scraped: {job_board.total_jobs_scraped}")
        print(f"     - created_at: {job_board.created_at}")
        print(f"     - updated_at: {job_board.updated_at}")
        print(f"     - notes: {getattr(job_board, 'notes', 'NOT_FOUND')}")
        print(f"     - selectors: {job_board.selectors}")
        
        # Test UUID conversion
        print(f"\n4. Testing UUID conversion...")
        object_id_str = str(job_board.id)
        uuid_from_objectid = str(uuid.uuid5(uuid.NAMESPACE_DNS, object_id_str))
        print(f"   ObjectId: {object_id_str}")
        print(f"   UUID: {uuid_from_objectid}")
        
        # Test type mapping
        print(f"\n5. Testing type mapping...")
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
        
        job_type = job_board.type.value if job_board.type else "html"
        mapped_type = type_mapping.get(job_type.lower(), job_type)
        print(f"   Original type: {job_type}")
        print(f"   Mapped type: {mapped_type}")
        
        # Test response data creation
        print(f"\n6. Creating response data...")
        
        try:
            response_item = {
                "id": uuid_from_objectid,
                "name": job_board.name,
                "description": getattr(job_board, 'notes', None) or "",  # Use notes field as description
                "type": mapped_type,
                "base_url": job_board.base_url,
                "rss_url": getattr(job_board, 'search_url_template', None),  # Use search_url_template as rss_url
                "region": getattr(job_board, 'region', None),  # Add region field from MongoDB model
                "selectors": job_board.selectors or {},
                "rate_limit_delay": int(job_board.rate_limit_delay or 2),
                "max_pages": job_board.max_pages_per_search or 10,  # Use max_pages_per_search
                "request_timeout": 30,  # Default value as not in MongoDB model
                "retry_attempts": 3,  # Default value as not in MongoDB model
                "is_active": job_board.is_active,
                "success_rate": job_board.success_rate or 0.0,
                "last_scraped_at": job_board.last_successful_scrape,  # Use last_successful_scrape
                "total_scrapes": job_board.total_jobs_scraped or 0,  # Use total_jobs_scraped
                "successful_scrapes": 0,  # Default value as not in MongoDB model
                "failed_scrapes": 0,  # Default value as not in MongoDB model
                "created_at": job_board.created_at,
                "updated_at": job_board.updated_at
            }
            
            print(f"   Response data created successfully")
            print(f"   Keys: {list(response_item.keys())}")
            
            # Test JobBoardResponse creation
            print(f"\n7. Testing JobBoardResponse creation...")
            response = JobBoardResponse(**response_item)
            print(f"   ✓ JobBoardResponse created successfully")
            print(f"   Response ID: {response.id}")
            print(f"   Response name: {response.name}")
            print(f"   Response type: {response.type}")
            
        except Exception as e:
            print(f"   ✗ Error creating response: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to identify missing fields
            print(f"\n   Checking required fields in JobBoardResponse...")
            from pydantic import ValidationError
            try:
                JobBoardResponse(**response_item)
            except ValidationError as ve:
                print(f"   Validation errors:")
                for error in ve.errors():
                    print(f"     - {error['loc'][0]}: {error['msg']}")
        
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
    asyncio.run(debug_response_mapping())