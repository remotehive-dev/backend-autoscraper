#!/usr/bin/env python3
"""
Test Beanie initialization in the running service
"""

import asyncio
from app.models.mongodb_models import JobBoard
from app.database.mongodb_manager import get_autoscraper_mongodb_manager

async def test_beanie_initialization():
    """Test if Beanie is properly initialized"""
    print("Testing Beanie initialization...")
    
    try:
        # Get the MongoDB manager
        mongodb_manager = await get_autoscraper_mongodb_manager()
        print(f"✓ MongoDB manager obtained: {mongodb_manager}")
        print(f"✓ Is connected: {mongodb_manager.is_connected}")
        print(f"✓ Database name: {mongodb_manager.database_name}")
        
        # Test if JobBoard model is properly initialized
        print("\nTesting JobBoard model...")
        
        # Check if the model has a collection
        if hasattr(JobBoard, 'get_motor_collection'):
            collection = JobBoard.get_motor_collection()
            print(f"✓ JobBoard collection: {collection.name}")
            print(f"✓ JobBoard database: {collection.database.name}")
        else:
            print("✗ JobBoard model not properly initialized - no get_motor_collection method")
            return
        
        # Test direct count using Beanie
        try:
            count = await JobBoard.count()
            print(f"✓ JobBoard.count() = {count}")
        except Exception as e:
            print(f"✗ JobBoard.count() failed: {e}")
            print(f"   Error type: {type(e).__name__}")
            
        # Test find operation
        try:
            job_boards = await JobBoard.find().limit(1).to_list()
            print(f"✓ JobBoard.find().limit(1) returned {len(job_boards)} documents")
            if job_boards:
                print(f"✓ Sample JobBoard: {job_boards[0].name}")
        except Exception as e:
            print(f"✗ JobBoard.find() failed: {e}")
            print(f"   Error type: {type(e).__name__}")
            
        # Test if the collection exists in the database
        try:
            # Test both database access methods
            db1 = mongodb_manager.database
            db2 = mongodb_manager.get_database()
            
            print(f"✓ Direct database property: {db1.name if db1 is not None else 'None'}")
            print(f"✓ get_database() method: {db2.name if db2 is not None else 'None'}")
            print(f"✓ Same database instance: {db1 is db2}")
            
            # Use get_database() method like the working debug script
            db = mongodb_manager.get_database()
            collections = await db.list_collection_names()
            if 'job_boards' in collections:
                print(f"✓ job_boards collection exists in database")
                
                # Direct collection access
                direct_count = await db.job_boards.count_documents({})
                print(f"✓ Direct collection count: {direct_count}")
            else:
                print(f"✗ job_boards collection not found in database")
                print(f"   Available collections: {collections}")
        except Exception as e:
            print(f"✗ Database collection check failed: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_beanie_initialization())