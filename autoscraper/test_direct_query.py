#!/usr/bin/env python3

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_direct_mongodb_query():
    """Test direct MongoDB query to job_boards collection"""
    
    # Get connection details from environment
    mongodb_url = os.getenv('MONGODB_URL')
    database_name = os.getenv('MONGODB_DATABASE_NAME')
    
    print(f"Connecting to: {database_name} database")
    print(f"MongoDB URL: {mongodb_url[:50]}...")
    
    # Create MongoDB client
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]
    collection = db['job_boards']
    
    try:
        # Count total documents
        total_count = await collection.count_documents({})
        print(f"Total job boards in collection: {total_count}")
        
        # Count active job boards
        active_count = await collection.count_documents({"is_active": True})
        print(f"Active job boards: {active_count}")
        
        # Count inactive job boards
        inactive_count = await collection.count_documents({"is_active": False})
        print(f"Inactive job boards: {inactive_count}")
        
        # Test the exact query used by the API
        print("\n--- Testing API query with no filters ---")
        cursor = collection.find({}).skip(0).limit(1000)
        api_results = await cursor.to_list(length=1000)
        print(f"API query (no filters) returned: {len(api_results)} results")
        
        # Test with active_only=False explicitly
        print("\n--- Testing API query with active_only=False ---")
        cursor = collection.find({}).skip(0).limit(1000)
        api_results_false = await cursor.to_list(length=1000)
        print(f"API query (active_only=False) returned: {len(api_results_false)} results")
        
        # Test with active_only=True
        print("\n--- Testing API query with active_only=True ---")
        cursor = collection.find({"is_active": True}).skip(0).limit(1000)
        api_results_true = await cursor.to_list(length=1000)
        print(f"API query (active_only=True) returned: {len(api_results_true)} results")
        
        # Sample first few documents
        if api_results:
            print("\n--- Sample documents ---")
            for i, doc in enumerate(api_results[:3]):
                print(f"Document {i+1}:")
                print(f"  Name: {doc.get('name')}")
                print(f"  Type: {doc.get('type')}")
                print(f"  Is Active: {doc.get('is_active')}")
                print(f"  Base URL: {doc.get('base_url')}")
                print()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_direct_mongodb_query())