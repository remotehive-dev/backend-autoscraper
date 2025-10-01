#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append('/Users/ranjeettiwary/Downloads/developer/RemoteHive_Migration_Package/autoscraper-service')

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv
import uuid

# Load environment variables
load_dotenv()

async def test_api_logic():
    """Test the exact logic used in the API endpoint"""
    
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
        
        print("\n--- Testing API Logic ---")
        
        # Simulate API parameters
        skip = 0
        limit = 1000
        active_only = False
        
        # Build MongoDB query (same as API)
        query_filter = {}
        if active_only:
            query_filter["is_active"] = True
        
        print(f"Query filter: {query_filter}")
        print(f"Skip: {skip}, Limit: {limit}")
        
        # Execute MongoDB query with pagination (same as API)
        job_boards = await JobBoard.find(query_filter).skip(skip).limit(limit).to_list()
        
        print(f"Raw query returned: {len(job_boards)} results")
        
        # Map MongoDB models to response schema (same as API)
        response_data = []
        for i, jb in enumerate(job_boards):
            try:
                # Convert MongoDB ObjectId to UUID format for response schema
                object_id_str = str(jb.id)
                # Create a deterministic UUID from ObjectId
                uuid_from_objectid = str(uuid.uuid5(uuid.NAMESPACE_DNS, object_id_str))
                
                # Map job board type to valid enum values
                type_mapping = {
                    "indeed": "html",  # Map indeed to html type
                    "linkedin": "html",
                    "glassdoor": "html",
                    "monster": "html",
                    "dice": "html",
                    "custom": "html"  # Map custom to html type
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
                response_data.append(response_item)
                
                if i < 3:  # Show first 3 for debugging
                    print(f"\nProcessed Job Board {i+1}:")
                    print(f"  Name: {jb.name}")
                    print(f"  Type: {jb.type} -> {mapped_type}")
                    print(f"  Base URL: {jb.base_url}")
                    print(f"  UUID: {uuid_from_objectid}")
                    
            except Exception as e:
                print(f"Error processing job board {i}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\nFinal response_data length: {len(response_data)}")
        
        if len(response_data) != len(job_boards):
            print(f"WARNING: Lost {len(job_boards) - len(response_data)} job boards during processing!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_api_logic())