#!/usr/bin/env python3

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from config.settings import get_settings
import uuid

async def debug_api_response():
    """Debug the API response processing to understand why only 17 job boards are returned"""
    
    try:
        # Get settings
        settings = get_settings()
        
        # Initialize MongoDB connection
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        database = client[settings.MONGODB_DATABASE_NAME]
        
        # Import JobBoard model
        from app.models.mongodb_models import JobBoard
        
        # Initialize Beanie with JobBoard model
        await init_beanie(database=database, document_models=[JobBoard])
        
        print("=== Debug API Response Processing ===")
        
        # Execute the same query as API with limit 100
        skip = 0
        limit = 100
        query_filter = {}
        
        job_boards = await JobBoard.find(query_filter).skip(skip).limit(limit).to_list()
        print(f"MongoDB query returned: {len(job_boards)} job boards")
        
        # Process response data like the API does
        response_data = []
        successful_mappings = 0
        failed_mappings = 0
        
        for i, jb in enumerate(job_boards):
            try:
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
                successful_mappings += 1
                
            except Exception as e:
                print(f"Failed to process job board {i+1} ({jb.name}): {e}")
                failed_mappings += 1
                continue
        
        print(f"Successfully mapped: {successful_mappings} job boards")
        print(f"Failed to map: {failed_mappings} job boards")
        print(f"Final response data length: {len(response_data)}")
        
        # Show first few successful mappings
        print("\n=== First 5 successful mappings ===")
        for i, item in enumerate(response_data[:5]):
            print(f"  {i+1}. {item['name']} (ID: {item['id']}, Type: {item['type']})")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    asyncio.run(debug_api_response())