#!/usr/bin/env python3
"""
Debug MongoDB Authentication and Connection Issues
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError
from config.settings import get_settings

async def test_mongodb_connection():
    """Test MongoDB connection with detailed error reporting"""
    settings = get_settings()
    
    print(f"Testing MongoDB connection...")
    print(f"Database Name: {settings.MONGODB_DATABASE_NAME}")
    print(f"Connection URL: {settings.MONGODB_URL[:50]}...")
    
    try:
        # Create client
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        
        # Test server connection
        print("\n1. Testing server connection...")
        server_info = await client.server_info()
        print(f"   ✓ Connected to MongoDB server version: {server_info.get('version')}")
        
        # Get database
        db = client[settings.MONGODB_DATABASE_NAME]
        
        # Test database access
        print("\n2. Testing database access...")
        collections = await db.list_collection_names()
        print(f"   ✓ Database '{settings.MONGODB_DATABASE_NAME}' accessible")
        print(f"   ✓ Collections found: {collections}")
        
        # Test job_boards collection specifically
        print("\n3. Testing job_boards collection...")
        job_boards_collection = db.job_boards
        
        # Test read permission
        try:
            count = await job_boards_collection.count_documents({})
            print(f"   ✓ job_boards collection accessible")
            print(f"   ✓ Document count: {count}")
            
            if count > 0:
                # Get a sample document
                sample = await job_boards_collection.find_one({})
                if sample:
                    print(f"   ✓ Sample document keys: {list(sample.keys())}")
                    print(f"   ✓ Sample document _id: {sample.get('_id')}")
                    print(f"   ✓ Sample document name: {sample.get('name')}")
            else:
                print("   ⚠ Collection is empty")
                
        except OperationFailure as e:
            print(f"   ✗ Permission denied for job_boards collection: {e}")
            print(f"   Error code: {e.code}")
            print(f"   Error details: {e.details}")
            
        # Test authentication info
        print("\n4. Testing authentication...")
        try:
            # Try to get current user info
            user_info = await db.command("connectionStatus")
            auth_info = user_info.get('authInfo', {})
            print(f"   ✓ Authenticated users: {auth_info.get('authenticatedUsers', [])}")
            print(f"   ✓ Authenticated user roles: {auth_info.get('authenticatedUserRoles', [])}")
        except Exception as e:
            print(f"   ⚠ Could not get auth info: {e}")
            
        # Test write permission
        print("\n5. Testing write permissions...")
        try:
            test_doc = {"test": "debug_test", "timestamp": "2024-01-01"}
            result = await job_boards_collection.insert_one(test_doc)
            print(f"   ✓ Write permission confirmed, inserted: {result.inserted_id}")
            
            # Clean up test document
            await job_boards_collection.delete_one({"_id": result.inserted_id})
            print(f"   ✓ Test document cleaned up")
            
        except OperationFailure as e:
            print(f"   ✗ Write permission denied: {e}")
            print(f"   Error code: {e.code}")
            
    except ServerSelectionTimeoutError as e:
        print(f"   ✗ Server selection timeout: {e}")
    except OperationFailure as e:
        print(f"   ✗ Operation failed: {e}")
        print(f"   Error code: {e.code}")
        print(f"   Error details: {e.details}")
    except Exception as e:
        print(f"   ✗ Unexpected error: {e}")
        print(f"   Error type: {type(e).__name__}")
    finally:
        if 'client' in locals():
            client.close()
            print("\n✓ Connection closed")

if __name__ == "__main__":
    asyncio.run(test_mongodb_connection())