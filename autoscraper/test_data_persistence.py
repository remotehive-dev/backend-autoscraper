#!/usr/bin/env python3
"""
Test script to verify data persistence in MongoDB
"""

import sys
from pathlib import Path
import asyncio

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.models.mongodb_models import JobBoard
from app.database.database import db_manager

async def test_data_persistence():
    """Test that uploaded CSV data is correctly stored in MongoDB"""
    try:
        # Initialize database connection
        await db_manager.initialize()
        print("✅ Database connection established")
        
        # Query for the uploaded job boards
        test_names = ["RemoteOK", "We Work Remotely", "FlexJobs"]
        
        print("\nChecking uploaded job boards:")
        for name in test_names:
            job_board = await JobBoard.find_one(JobBoard.name == name)
            
            if job_board:
                print(f"\n✅ Found: {job_board.name}")
                print(f"   Base URL: {job_board.base_url}")
                print(f"   Region: {job_board.region}")
                print(f"   Type: {job_board.type}")
                print(f"   Active: {job_board.is_active}")
            else:
                print(f"\n❌ Not found: {name}")
        
        # Count total job boards
        total_count = await JobBoard.count()
        print(f"\nTotal job boards in database: {total_count}")
        
        # Show all job boards with region field
        print("\nAll job boards with region information:")
        all_boards = await JobBoard.find_all().to_list()
        
        for board in all_boards:
            if hasattr(board, 'region') and board.region:
                print(f"  - {board.name}: {board.region} ({board.base_url})")
        
        print("\n✅ Data persistence verification completed!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_data_persistence())