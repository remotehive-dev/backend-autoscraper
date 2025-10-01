#!/usr/bin/env python3
"""
Debug script to test if index conflicts are preventing Beanie from working
"""

import asyncio
from loguru import logger
from config.settings import get_settings
from app.database.mongodb_manager import autoscraper_mongodb_manager
from app.models.mongodb_models import JobBoard

async def test_without_index_creation():
    """Test Beanie initialization without creating indexes"""
    print("\n=== Testing Beanie without index creation ===")
    
    try:
        # Connect without creating indexes
        success = await autoscraper_mongodb_manager.connect()
        print(f"MongoDB connection: {success}")
        
        if success:
            # Test JobBoard queries immediately after connection
            total_job_boards = await JobBoard.count()
            print(f"Total JobBoard documents: {total_job_boards}")
            
            if total_job_boards > 0:
                # Try to fetch some job boards
                job_boards = await JobBoard.find().limit(3).to_list()
                print(f"Found {len(job_boards)} job boards:")
                for jb in job_boards:
                    print(f"  - {jb.name} (ID: {jb.id})")
            else:
                print("No job boards found")
                
                # Check if we can access the collection directly
                collection = autoscraper_mongodb_manager.database.job_boards
                direct_count = await collection.count_documents({})
                print(f"Direct collection count: {direct_count}")
                
                # Try to find documents directly
                cursor = collection.find().limit(3)
                direct_docs = await cursor.to_list(length=3)
                print(f"Direct documents found: {len(direct_docs)}")
                for doc in direct_docs:
                    print(f"  - {doc.get('name', 'Unknown')} (ID: {doc.get('_id')})")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await autoscraper_mongodb_manager.disconnect()

async def test_with_index_creation():
    """Test the current initialization process with index creation"""
    print("\n=== Testing current initialization with index creation ===")
    
    try:
        # Use the current initialization process
        from app.database.mongodb_manager import init_autoscraper_mongodb, close_autoscraper_mongodb
        
        await init_autoscraper_mongodb()
        print("MongoDB initialized with index creation")
        
        # Test JobBoard queries
        total_job_boards = await JobBoard.count()
        print(f"Total JobBoard documents: {total_job_boards}")
        
        if total_job_boards > 0:
            job_boards = await JobBoard.find().limit(3).to_list()
            print(f"Found {len(job_boards)} job boards:")
            for jb in job_boards:
                print(f"  - {jb.name} (ID: {jb.id})")
        else:
            print("No job boards found with current initialization")
        
    except Exception as e:
        print(f"Error during current initialization test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await close_autoscraper_mongodb()

async def main():
    """Main test function"""
    print("Debugging index conflicts and Beanie initialization...")
    
    # Test 1: Without index creation
    await test_without_index_creation()
    
    # Wait a bit between tests
    await asyncio.sleep(2)
    
    # Test 2: With index creation (current process)
    await test_with_index_creation()

if __name__ == "__main__":
    asyncio.run(main())