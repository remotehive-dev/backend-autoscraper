#!/usr/bin/env python3
"""
Test script to verify the autoscraper service database connection after fixing the database name.
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import get_settings
from app.database.mongodb_manager import autoscraper_mongodb_manager
from app.models.mongodb_models import JobBoard

async def test_connection():
    """Test the database connection and job board retrieval."""
    print("Testing autoscraper service database connection...")
    
    # Get settings
    settings = get_settings()
    print(f"MongoDB URL: {settings.MONGODB_URL}")
    print(f"Database Name: {settings.MONGODB_DATABASE_NAME}")
    
    try:
        # Connect to MongoDB
        await autoscraper_mongodb_manager.connect()
        print("✅ Successfully connected to MongoDB")
        
        # Test JobBoard queries
        total_job_boards = await JobBoard.count()
        print(f"📊 Total JobBoard documents: {total_job_boards}")
        
        if total_job_boards > 0:
            # Get first few job boards
            job_boards = await JobBoard.find().limit(3).to_list()
            print(f"\n📋 Sample job boards:")
            for i, jb in enumerate(job_boards, 1):
                print(f"  {i}. {jb.name} - {jb.base_url} (Active: {jb.is_active})")
        
        # Test active job boards
        active_count = await JobBoard.find({"is_active": True}).count()
        print(f"\n🟢 Active job boards: {active_count}")
        
        print("\n✅ Database connection test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during database test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Disconnect
        await autoscraper_mongodb_manager.disconnect()
        print("🔌 Disconnected from MongoDB")

if __name__ == "__main__":
    asyncio.run(test_connection())