#!/usr/bin/env python3
"""
Comprehensive debug script for the job-boards API endpoint
This script will test every step of the endpoint logic to identify the issue
"""

import asyncio
import sys
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from config.settings import settings
from app.database.database import DatabaseManager
from app.models.mongodb_models import JobBoard
from app.schemas import JobBoardResponse
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def debug_endpoint_logic():
    """Debug the exact logic used in the list_job_boards endpoint"""
    
    try:
        print("=== Starting Comprehensive Endpoint Debug ===")
        
        # Step 1: Load settings
        print("\n1. Loading settings...")
        print(f"MongoDB URL: {settings.MONGODB_URL}")
        print(f"Database Name: {settings.MONGODB_DATABASE_NAME}")
        
        # Step 2: Connect to MongoDB
        print("\n2. Connecting to MongoDB...")
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        database = client[settings.MONGODB_DATABASE_NAME]
        
        # Step 3: Initialize Beanie
        print("\n3. Initializing Beanie...")
        await init_beanie(
            database=database,
            document_models=[
                JobBoard,
                # Add other models if needed
            ]
        )
        print("Beanie initialized successfully")
        
        # Step 4: Test basic JobBoard query
        print("\n4. Testing basic JobBoard query...")
        total_count = await JobBoard.count()
        print(f"Total JobBoard count: {total_count}")
        
        # Step 5: Test the exact endpoint parameters
        print("\n5. Testing endpoint parameters...")
        skip = 0
        limit = 10
        is_active = None  # Default parameter
        
        print(f"Parameters: skip={skip}, limit={limit}, is_active={is_active}")
        
        # Step 6: Build query filter (exact logic from endpoint)
        print("\n6. Building query filter...")
        query_filter = {}
        if is_active is not None:
            query_filter["is_active"] = is_active
        print(f"Query filter: {query_filter}")
        
        # Step 7: Execute the query (exact logic from endpoint)
        print("\n7. Executing JobBoard query...")
        try:
            job_boards = await JobBoard.find(query_filter).skip(skip).limit(limit).to_list()
            print(f"Query returned {len(job_boards)} job boards")
            
            if job_boards:
                print("\nFirst job board details:")
                first_board = job_boards[0]
                print(f"  ID: {first_board.id}")
                print(f"  Name: {first_board.name}")
                print(f"  URL: {first_board.url}")
                print(f"  Is Active: {first_board.is_active}")
                print(f"  Type: {type(first_board)}")
            else:
                print("No job boards returned from query")
                
        except Exception as e:
            print(f"Error in JobBoard query: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Step 8: Test response mapping (exact logic from endpoint)
        print("\n8. Testing response mapping...")
        try:
            mapped_responses = []
            for job_board in job_boards:
                print(f"\nMapping job board: {job_board.name}")
                
                # Create JobBoardResponse exactly as in endpoint
                response_data = {
                    "id": str(job_board.id),
                    "name": job_board.name,
                    "url": job_board.url,
                    "is_active": job_board.is_active,
                    "scrape_frequency_hours": job_board.scrape_frequency_hours,
                    "last_scraped_at": job_board.last_scraped_at,
                    "created_at": job_board.created_at,
                    "updated_at": job_board.updated_at,
                    "total_jobs_scraped": job_board.total_jobs_scraped or 0,
                    "description": job_board.description,
                    "tags": job_board.tags or [],
                    "scraping_config": job_board.scraping_config or {}
                }
                
                print(f"  Response data keys: {list(response_data.keys())}")
                
                # Create JobBoardResponse object
                try:
                    job_board_response = JobBoardResponse(**response_data)
                    mapped_responses.append(job_board_response)
                    print(f"  Successfully mapped to JobBoardResponse")
                except Exception as mapping_error:
                    print(f"  Error mapping to JobBoardResponse: {mapping_error}")
                    print(f"  Response data: {response_data}")
                    import traceback
                    traceback.print_exc()
                    
            print(f"\nSuccessfully mapped {len(mapped_responses)} responses")
            
        except Exception as e:
            print(f"Error in response mapping: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Step 9: Test JSON serialization
        print("\n9. Testing JSON serialization...")
        try:
            import json
            from pydantic import BaseModel
            
            # Convert to dict for JSON serialization
            response_dicts = [response.dict() for response in mapped_responses]
            json_str = json.dumps(response_dicts, default=str, indent=2)
            print(f"JSON serialization successful, length: {len(json_str)}")
            
            if len(json_str) < 1000:  # Only print if not too long
                print(f"JSON content: {json_str}")
            else:
                print("JSON content too long to display")
                
        except Exception as e:
            print(f"Error in JSON serialization: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Step 10: Test with different parameters
        print("\n10. Testing with different parameters...")
        
        # Test with is_active=True
        print("\nTesting with is_active=True:")
        active_filter = {"is_active": True}
        active_boards = await JobBoard.find(active_filter).skip(0).limit(5).to_list()
        print(f"Active job boards: {len(active_boards)}")
        
        # Test with is_active=False
        print("\nTesting with is_active=False:")
        inactive_filter = {"is_active": False}
        inactive_boards = await JobBoard.find(inactive_filter).skip(0).limit(5).to_list()
        print(f"Inactive job boards: {len(inactive_boards)}")
        
        # Step 11: Check for any hidden issues
        print("\n11. Checking for potential issues...")
        
        # Check if all job boards have required fields
        sample_boards = await JobBoard.find({}).limit(5).to_list()
        for i, board in enumerate(sample_boards):
            print(f"\nJob board {i+1}:")
            print(f"  Has id: {hasattr(board, 'id') and board.id is not None}")
            print(f"  Has name: {hasattr(board, 'name') and board.name is not None}")
            print(f"  Has url: {hasattr(board, 'url') and board.url is not None}")
            print(f"  Has is_active: {hasattr(board, 'is_active') and board.is_active is not None}")
            
        print("\n=== Debug Complete ===")
        
    except Exception as e:
        print(f"Critical error in debug script: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Close database connection
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    asyncio.run(debug_endpoint_logic())