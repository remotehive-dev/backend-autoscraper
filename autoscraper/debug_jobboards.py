#!/usr/bin/env python3

import asyncio
import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

async def debug_job_boards():
    """Debug job boards collection access"""
    try:
        # Import the MongoDB manager
        from app.database.mongodb_manager import autoscraper_mongodb_manager
        
        # Initialize the connection
        await autoscraper_mongodb_manager.connect()
        
        print("=== MongoDB Connection Debug ===")
        print(f"Database URL: {autoscraper_mongodb_manager.connection_string}")
        print(f"Database Name: {autoscraper_mongodb_manager.database_name}")
        
        # Get database and collection directly
        db = autoscraper_mongodb_manager.get_database()
        print(f"\nDatabase object: {db}")
        
        # List all collections
        collections = await db.list_collection_names()
        print(f"\nAvailable collections: {collections}")
        
        # Check job_boards collection directly
        job_boards_collection = db.job_boards
        direct_count = await job_boards_collection.count_documents({})
        print(f"\nDirect collection count: {direct_count}")
        
        # Get sample documents
        sample_docs = await job_boards_collection.find({}).limit(5).to_list(length=5)
        print(f"\nSample documents ({len(sample_docs)}):")        
        for i, doc in enumerate(sample_docs, 1):
            print(f"  {i}. ID: {doc.get('_id')}, Name: {doc.get('name')}, Type: {doc.get('type')}")
        
        # Now try with Beanie models
        print("\n=== Beanie Model Debug ===")
        try:
            from app.models.mongodb_models import JobBoard
            
            # Count using Beanie
            beanie_count = await JobBoard.count()
            print(f"Beanie model count: {beanie_count}")
            
            # Get sample using Beanie
            beanie_docs = await JobBoard.find().limit(5).to_list()
            print(f"\nBeanie sample documents ({len(beanie_docs)}):")
            for i, doc in enumerate(beanie_docs, 1):
                print(f"  {i}. ID: {doc.id}, Name: {doc.name}, Type: {doc.type}")
                
        except Exception as e:
            print(f"Beanie model error: {e}")
            import traceback
            traceback.print_exc()
        
        # Test the actual API query
        print("\n=== API Query Debug ===")
        try:
            from app.models.mongodb_models import JobBoard
            
            # Simulate the API query
            query_filter = {}
            job_boards = await JobBoard.find(query_filter).skip(0).limit(1000).to_list()
            print(f"API query result count: {len(job_boards)}")
            
            if job_boards:
                print("First few results:")
                for i, jb in enumerate(job_boards[:3], 1):
                    print(f"  {i}. Name: {jb.name}, Type: {jb.type}, Active: {jb.is_active}")
                    
        except Exception as e:
            print(f"API query error: {e}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"Debug error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await autoscraper_mongodb_manager.close()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(debug_job_boards())