#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.mongodb_models import JobBoard
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

async def debug_job_boards_issue():
    print("=== Debugging Job Boards API Issue ===")
    
    client = None
    try:
        # Initialize MongoDB connection
        print("\n1. Connecting to MongoDB...")
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        database = client.remotehive_autoscraper
        
        # Initialize Beanie
        await init_beanie(database=database, document_models=[JobBoard])
        print("✓ Connected to MongoDB and initialized Beanie")
        
        # Test 1: Count total documents
        print("\n2. Counting total job boards...")
        total_count = await JobBoard.count()
        print(f"✓ Total job boards in database: {total_count}")
        
        # Test 2: Test active filter
        print("\n3. Testing active filter...")
        active_job_boards = await JobBoard.find({"is_active": True}).to_list()
        print(f"✓ Active job boards: {len(active_job_boards)}")
        
        inactive_job_boards = await JobBoard.find({"is_active": False}).to_list()
        print(f"✓ Inactive job boards: {len(inactive_job_boards)}")
        
        # Test 3: Check for null/missing is_active field
        print("\n4. Checking for documents with null/missing is_active...")
        null_active = await JobBoard.find({"is_active": None}).to_list()
        print(f"✓ Job boards with null is_active: {len(null_active)}")
        
        missing_active = await JobBoard.find({"is_active": {"$exists": False}}).to_list()
        print(f"✓ Job boards missing is_active field: {len(missing_active)}")
        
        # Test 4: Simulate the exact API query logic
        print("\n5. Simulating API query logic...")
        
        # Default API parameters
        skip = 0
        limit = 50
        active_only = True
        
        # Build query like the API does
        query = {}
        if active_only:
            query["is_active"] = True
            
        print(f"   Query: {query}")
        print(f"   Skip: {skip}, Limit: {limit}")
        
        api_result = await JobBoard.find(query).skip(skip).limit(limit).to_list()
        print(f"✓ API simulation returned: {len(api_result)} job boards")
        
        # Test 5: Try without active filter
        print("\n6. Testing without active filter...")
        no_filter_result = await JobBoard.find({}).skip(skip).limit(limit).to_list()
        print(f"✓ Without active filter: {len(no_filter_result)} job boards")
        
        # Test 6: Show active job boards
        print("\n7. Active job boards details...")
        active_boards = await JobBoard.find({"is_active": True}).to_list()
        print(f"✓ Found {len(active_boards)} active job boards:")
        for board in active_boards:
            print(f"   - {board.name} (ID: {board.id})")
        
        if len(active_boards) == 3:
            print("\n🔍 FOUND THE ISSUE: Only 3 job boards are marked as active!")
            print("   This explains why the API returns only 3 job boards.")
            print("   The API filters by is_active=True by default.")
            
            # Show some inactive ones
            print("\n   Sample inactive job boards:")
            inactive_sample = await JobBoard.find({"is_active": False}).limit(5).to_list()
            for board in inactive_sample:
                print(f"   ✗ {board.name}")
                
            print("\n💡 SOLUTION: Either:")
            print("   1. Set more job boards to active (is_active=true)")
            print("   2. Modify the API to not filter by active status by default")
            print("   3. Use active_only=false parameter in API calls")
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Close connection
        if client:
            client.close()
            print("\n✓ MongoDB connection closed")

if __name__ == "__main__":
    asyncio.run(debug_job_boards_issue())