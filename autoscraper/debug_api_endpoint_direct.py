#!/usr/bin/env python3
"""
Debug script to test the API endpoint directly and catch any errors
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.getcwd())

async def debug_api_endpoint_direct():
    """Debug the API endpoint directly"""
    
    print("=== Direct API Endpoint Debug ===")
    print(f"Timestamp: {datetime.now()}")
    print()
    
    try:
        # Initialize database connection like the service does
        from config.settings import get_settings
        from motor.motor_asyncio import AsyncIOMotorClient
        from beanie import init_beanie
        
        settings = get_settings()
        
        print("🔗 Connecting to MongoDB...")
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        database = client[settings.MONGODB_DATABASE_NAME]
        
        # Import models
        from app.models.mongodb_models import (
            JobBoard, ScheduleConfig, ScrapeJob, ScrapeRun, 
            RawJob, NormalizedJob, EngineState, ScrapingMetrics,
            JobPosting, ScrapingSession
        )
        
        document_models = [
            JobBoard, ScheduleConfig, ScrapeJob, ScrapeRun,
            RawJob, NormalizedJob, EngineState, ScrapingMetrics,
            JobPosting, ScrapingSession
        ]
        
        # Initialize Beanie
        await init_beanie(database=database, document_models=document_models)
        print("✅ Database initialized")
        print()
        
        # Test the exact API endpoint logic
        print("🔍 Testing API endpoint logic directly:")
        
        # Parameters from API call
        skip = 0
        limit = 10
        active_only = False
        
        # Build MongoDB query (same as API)
        query_filter = {}
        if active_only:
            query_filter["is_active"] = True
        
        print(f"Query filter: {query_filter}")
        print(f"Skip: {skip}, Limit: {limit}")
        
        # Execute MongoDB query with pagination (same as API)
        job_boards = await JobBoard.find(query_filter).skip(skip).limit(limit).to_list()
        print(f"Raw query returned: {len(job_boards)} job boards")
        
        if not job_boards:
            print("❌ No job boards returned from query!")
            
            # Test alternative queries
            print("\n🔍 Testing alternative queries:")
            all_boards = await JobBoard.find().limit(5).to_list()
            print(f"Find all (no filter): {len(all_boards)} results")
            
            if all_boards:
                print("First board from find all:")
                board = all_boards[0]
                print(f"  - ID: {board.id}")
                print(f"  - Name: {board.name}")
                print(f"  - Type: {board.type}")
                print(f"  - Is Active: {board.is_active}")
            
            return
        
        print("\n📋 Processing response mapping (same as API):")
        
        # Map MongoDB models to response schema (same as API)
        response_data = []
        for i, jb in enumerate(job_boards):
            print(f"\nProcessing job board {i+1}: {jb.name}")
            
            try:
                # Convert MongoDB ObjectId to UUID format for response schema
                import uuid
                object_id_str = str(jb.id)
                print(f"  ObjectId: {object_id_str}")
                
                # Create a deterministic UUID from ObjectId
                uuid_from_objectid = str(uuid.uuid5(uuid.NAMESPACE_DNS, object_id_str))
                print(f"  UUID: {uuid_from_objectid}")
                
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
                print(f"  Job type: {job_type}")
                mapped_type = type_mapping.get(job_type.lower(), job_type)
                print(f"  Mapped type: {mapped_type}")
                
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
                
                print(f"  ✅ Successfully mapped response item")
                response_data.append(response_item)
                
            except Exception as mapping_error:
                print(f"  ❌ Error mapping job board {jb.name}: {str(mapping_error)}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\n📊 Final results: {len(response_data)} job boards successfully mapped")
        
        if response_data:
            print("\nFirst mapped result:")
            first = response_data[0]
            print(f"  - ID: {first['id']}")
            print(f"  - Name: {first['name']}")
            print(f"  - Type: {first['type']}")
            print(f"  - Base URL: {first['base_url']}")
            print(f"  - Is Active: {first['is_active']}")
        
        print("\n✅ API endpoint logic test complete!")
        
    except Exception as e:
        print(f"❌ Error in API endpoint test: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'client' in locals():
            client.close()
            print("🔌 MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(debug_api_endpoint_direct())