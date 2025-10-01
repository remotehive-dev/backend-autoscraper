#!/usr/bin/env python3
"""
Debug script to examine the exact connection details of the global instance
"""

import asyncio
import os
from pathlib import Path

# Add the current directory to Python path
current_dir = Path(__file__).parent
os.chdir(current_dir)

# Import the exact same global instance used by the service
from app.database.mongodb_manager import autoscraper_mongodb_manager, init_autoscraper_mongodb
from app.models.mongodb_models import JobBoard
from config.settings import get_settings
from motor.motor_asyncio import AsyncIOMotorClient

async def debug_connection_details():
    """
    Debug the exact connection details and compare with a fresh connection
    """
    print("=== Debugging Connection Details ===")
    
    try:
        # Get settings
        settings = get_settings()
        print(f"\n1. Settings:")
        print(f"   MONGODB_URL: {settings.MONGODB_URL}")
        print(f"   MONGODB_DATABASE_NAME: {settings.MONGODB_DATABASE_NAME}")
        
        # Initialize global instance
        print(f"\n2. Initializing global instance...")
        await init_autoscraper_mongodb()
        
        # Check global instance details
        print(f"\n3. Global Instance Details:")
        print(f"   Connection string: {autoscraper_mongodb_manager.connection_string}")
        print(f"   Database name: {autoscraper_mongodb_manager.database_name}")
        print(f"   Is connected: {autoscraper_mongodb_manager.is_connected}")
        
        # Get database info from global instance
        global_db = autoscraper_mongodb_manager.database
        print(f"   Database object: {global_db}")
        print(f"   Database name from object: {global_db.name}")
        
        # List collections in global instance database
        global_collections = await global_db.list_collection_names()
        print(f"   Collections in global DB: {global_collections}")
        
        # Check job_boards collection in global instance
        global_job_boards = global_db.job_boards
        global_count = await global_job_boards.count_documents({})
        print(f"   Job boards count in global DB: {global_count}")
        
        # Sample document from global instance
        global_sample = await global_job_boards.find_one()
        print(f"   Sample document in global DB: {global_sample}")
        
        print(f"\n4. Creating Fresh Connection for Comparison...")
        
        # Create a fresh connection using the same settings
        fresh_client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000
        )
        
        fresh_db = fresh_client[settings.MONGODB_DATABASE_NAME]
        print(f"   Fresh database name: {fresh_db.name}")
        
        # List collections in fresh connection
        fresh_collections = await fresh_db.list_collection_names()
        print(f"   Collections in fresh DB: {fresh_collections}")
        
        # Check job_boards collection in fresh connection
        fresh_job_boards = fresh_db.job_boards
        fresh_count = await fresh_job_boards.count_documents({})
        print(f"   Job boards count in fresh DB: {fresh_count}")
        
        # Sample document from fresh connection
        fresh_sample = await fresh_job_boards.find_one()
        print(f"   Sample document in fresh DB: {fresh_sample}")
        
        print(f"\n5. Comparison:")
        print(f"   Same connection string: {autoscraper_mongodb_manager.connection_string == settings.MONGODB_URL}")
        print(f"   Same database name: {autoscraper_mongodb_manager.database_name == settings.MONGODB_DATABASE_NAME}")
        print(f"   Same collections: {set(global_collections) == set(fresh_collections)}")
        print(f"   Same job board count: {global_count == fresh_count}")
        
        # Check if we're connecting to different databases
        if global_count != fresh_count:
            print(f"\n❌ ISSUE FOUND: Different job board counts!")
            print(f"   Global instance: {global_count} job boards")
            print(f"   Fresh connection: {fresh_count} job boards")
            
            # Check if they're connecting to different databases
            if global_db.name != fresh_db.name:
                print(f"   ❌ Different database names: '{global_db.name}' vs '{fresh_db.name}'")
            else:
                print(f"   ✓ Same database name: '{global_db.name}'")
                
                # Check if collections are different
                if set(global_collections) != set(fresh_collections):
                    print(f"   ❌ Different collections")
                    print(f"   Global only: {set(global_collections) - set(fresh_collections)}")
                    print(f"   Fresh only: {set(fresh_collections) - set(global_collections)}")
                else:
                    print(f"   ✓ Same collections")
        
        # Close fresh connection
        fresh_client.close()
        
        print(f"\n=== Debug Complete ===")
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_connection_details())