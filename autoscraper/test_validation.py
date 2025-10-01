#!/usr/bin/env python3

import asyncio
import sys
import os
from datetime import datetime
import uuid

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

async def test_job_board_validation():
    """Test JobBoardResponse validation with actual MongoDB data"""
    try:
        # Import required modules
        from app.database.mongodb_manager import AutoScraperMongoDBManager
        from app.models.mongodb_models import JobBoard
        from app.schemas import JobBoardResponse, JobBoardType
        
        # Initialize database connection
        db_manager = AutoScraperMongoDBManager()
        await db_manager.connect()
        
        print("Connected to MongoDB successfully")
        
        # Get all job boards from MongoDB
        job_boards = await JobBoard.find({}).limit(10).to_list()  # Test first 10
        print(f"Retrieved {len(job_boards)} job boards from MongoDB")
        
        valid_count = 0
        invalid_count = 0
        
        for i, jb in enumerate(job_boards):
            try:
                # Convert MongoDB ObjectId to UUID format for response schema
                object_id_str = str(jb.id)
                uuid_from_objectid = str(uuid.uuid5(uuid.NAMESPACE_DNS, object_id_str))
                
                # Map job board type to valid enum values
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
                
                # Create response data exactly like the API does
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
                
                # Try to validate with JobBoardResponse
                validated_response = JobBoardResponse(**response_item)
                valid_count += 1
                print(f"✓ Job board {i+1} ({jb.name}) validated successfully")
                
            except Exception as e:
                invalid_count += 1
                print(f"✗ Job board {i+1} ({jb.name}) validation failed: {str(e)}")
                print(f"  Raw data: {response_item}")
                print(f"  Error details: {type(e).__name__}: {str(e)}")
                print()
        
        print(f"\nValidation Summary:")
        print(f"Valid job boards: {valid_count}")
        print(f"Invalid job boards: {invalid_count}")
        print(f"Total tested: {len(job_boards)}")
        
        # Test the enum values
        print(f"\nJobBoardType enum values: {[e.value for e in JobBoardType]}")
        
        await db_manager.disconnect()
        
    except Exception as e:
        print(f"Error during validation test: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_job_board_validation())