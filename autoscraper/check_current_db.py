#!/usr/bin/env python3

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def check_database():
    # Get MongoDB connection details from environment
    mongodb_url = os.getenv('MONGODB_URL')
    
    print(f"Connecting to: {mongodb_url}")
    
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(mongodb_url)
        
        # List all databases
        print("\n=== Available Databases ===")
        db_list = await client.list_database_names()
        for db_name in db_list:
            print(f"- {db_name}")
        
        # Check each database for job_boards collections
        target_databases = ['remotehive', 'remotehive_autoscraper', 'remotehive_jobs', 'remotehive_main', 'remotehive_production']
        
        for db_name in target_databases:
            if db_name in db_list:
                print(f"\n=== Collections in '{db_name}' ===")
                db = client[db_name]
                collections = await db.list_collection_names()
                
                for collection in collections:
                    count = await db[collection].count_documents({})
                    print(f"- {collection}: {count} documents")
                    
                    # Show sample document if it contains 'job' or 'board'
                    if ('job' in collection.lower() and 'board' in collection.lower()) or count > 500:
                        sample = await db[collection].find_one()
                        if sample:
                            print(f"  Sample keys: {list(sample.keys())[:10]}")
                            if 'name' in sample:
                                print(f"  Sample name: {sample.get('name', 'N/A')}")
                            if 'base_url' in sample:
                                print(f"  Sample base_url: {sample.get('base_url', 'N/A')}")
        
        await client.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_database())