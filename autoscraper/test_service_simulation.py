#!/usr/bin/env python3
"""
Test script to simulate exactly what the autoscraper service does
to identify why the API returns 0 job boards while direct queries find 735.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from app.database.mongodb_manager import AutoScraperMongoDBManager
from app.models.mongodb_models import JobBoard
from config.settings import get_settings

async def test_service_simulation():
    """
    Simulate exactly what the service does during startup and API calls
    """
    print("=== Service Simulation Test ===")
    
    # Get settings (same as service)
    settings = get_settings()
    print(f"MongoDB URL: {settings.MONGODB_URL}")
    print(f"Database Name: {settings.MONGODB_DATABASE_NAME}")
    
    # Initialize database manager (same as service)
    db_manager = AutoScraperMongoDBManager()
    
    try:
        # Connect to database (same as service startup)
        print("\n1. Connecting to MongoDB...")
        success = await db_manager.connect()
        if not success:
            print("❌ Failed to connect to MongoDB")
            return
        print("✅ Connected to MongoDB")
        
        # Test connection (same as service health check)
        print("\n2. Testing connection...")
        connection_info = await db_manager.test_connection()
        print(f"Connection Status: {connection_info.get('connected')}")
        print(f"Collections: {connection_info.get('collections_count')}")
        print(f"Objects Count: {connection_info.get('objects_count')}")
        
        # Test JobBoard queries (same as API endpoint)
        print("\n3. Testing JobBoard queries...")
        
        # Count all job boards
        total_count = await JobBoard.count()
        print(f"Total JobBoard count (Beanie): {total_count}")
        
        # Count active job boards (same as API with active_only=True)
        active_count = await JobBoard.find({"is_active": True}).count()
        print(f"Active JobBoard count: {active_count}")
        
        # Count all job boards (same as API with active_only=False)
        all_count = await JobBoard.find().count()
        print(f"All JobBoard count: {all_count}")
        
        # Test the exact query used in the API
        print("\n4. Testing API-style queries...")
        
        # Simulate active_only=False (no filter)
        query_filter = {}
        api_count = await JobBoard.find(query_filter).count()
        print(f"API query count (no filter): {api_count}")
        
        # Get first 5 documents (same as API limit=5)
        documents = await JobBoard.find(query_filter).limit(5).to_list()
        print(f"Retrieved {len(documents)} documents")
        
        if documents:
            print("Sample documents:")
            for doc in documents[:3]:
                print(f"  - {doc.name}: active={doc.is_active}, type={doc.type}")
        else:
            print("❌ No documents retrieved!")
        
        # Test with active filter (same as API with active_only=True)
        query_filter_active = {"is_active": True}
        active_api_count = await JobBoard.find(query_filter_active).count()
        print(f"API query count (active only): {active_api_count}")
        
        # Get active documents
        active_documents = await JobBoard.find(query_filter_active).limit(5).to_list()
        print(f"Retrieved {len(active_documents)} active documents")
        
        # Test raw MongoDB query (bypass Beanie)
        print("\n5. Testing raw MongoDB queries...")
        raw_collection = db_manager.database.job_boards
        raw_count = await raw_collection.count_documents({})
        print(f"Raw MongoDB count: {raw_count}")
        
        raw_docs = await raw_collection.find({}).limit(3).to_list(length=3)
        print(f"Raw MongoDB documents: {len(raw_docs)}")
        if raw_docs:
            for doc in raw_docs:
                print(f"  - {doc.get('name')}: active={doc.get('is_active')}")
        
    except Exception as e:
        print(f"❌ Error during simulation: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Disconnect (same as service shutdown)
        await db_manager.disconnect()
        print("\n✅ Disconnected from MongoDB")

if __name__ == "__main__":
    asyncio.run(test_service_simulation())