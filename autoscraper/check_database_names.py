#!/usr/bin/env python3
"""
Check which MongoDB database contains the job boards
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure

async def check_databases():
    """
    Check both databases to see which one contains job boards
    """
    
    # MongoDB connection string
    connection_string = "mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive"
    
    try:
        # Create client
        client = AsyncIOMotorClient(connection_string)
        
        # Test connection
        await client.admin.command('ping')
        print("✅ Connected to MongoDB Atlas")
        
        # Check both databases
        databases_to_check = ["remotehive", "remotehive_autoscraper"]
        
        for db_name in databases_to_check:
            print(f"\n🔍 Checking database: {db_name}")
            
            db = client[db_name]
            
            # List collections
            collections = await db.list_collection_names()
            print(f"   Collections: {collections}")
            
            # Check for job_boards collection
            if "job_boards" in collections:
                count = await db.job_boards.count_documents({})
                print(f"   📊 job_boards collection: {count} documents")
                
                # Get sample document
                sample = await db.job_boards.find_one()
                if sample:
                    print(f"   📄 Sample document keys: {list(sample.keys())}")
                    print(f"   📄 Sample name: {sample.get('name', 'N/A')}")
                    print(f"   📄 Sample is_active: {sample.get('is_active', 'N/A')}")
            else:
                print(f"   ❌ No job_boards collection found")
        
        # Close connection
        client.close()
        
    except ConnectionFailure as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_databases())