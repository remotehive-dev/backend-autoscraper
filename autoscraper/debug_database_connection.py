#!/usr/bin/env python3
"""
Debug script to check which database and collections Beanie is connecting to
"""

import asyncio
from loguru import logger
from config.settings import get_settings
from app.database.mongodb_manager import autoscraper_mongodb_manager
from app.models.mongodb_models import JobBoard
from motor.motor_asyncio import AsyncIOMotorClient

async def debug_connection_details():
    """Debug the actual database connection details"""
    print("\n=== Debugging Database Connection Details ===")
    
    try:
        # Get settings
        settings = get_settings()
        print(f"MongoDB URL from settings: {settings.MONGODB_URL}")
        
        # Connect to MongoDB
        success = await autoscraper_mongodb_manager.connect()
        print(f"Connection successful: {success}")
        
        if success:
            # Get client and database info
            client = autoscraper_mongodb_manager.get_client()
            database = autoscraper_mongodb_manager.get_database()
            
            print(f"Database name: {database.name}")
            
            # List all databases
            db_list = await client.list_database_names()
            print(f"Available databases: {db_list}")
            
            # List collections in current database
            collections = await database.list_collection_names()
            print(f"Collections in '{database.name}': {collections}")
            
            # Check if job_boards collection exists
            if 'job_boards' in collections:
                print("✓ job_boards collection exists")
                
                # Get collection stats
                job_boards_collection = database.job_boards
                count = await job_boards_collection.count_documents({})
                print(f"Documents in job_boards collection: {count}")
                
                # Try to get a sample document
                sample_doc = await job_boards_collection.find_one()
                if sample_doc:
                    print(f"Sample document: {sample_doc}")
                else:
                    print("No documents found in job_boards collection")
            else:
                print("✗ job_boards collection does not exist")
            
            # Check what Beanie thinks about JobBoard
            print(f"\nBeanie JobBoard model info:")
            print(f"Collection name: {JobBoard.get_collection_name()}")
            
            # Try to get Beanie's database
            try:
                beanie_db = JobBoard.get_motor_collection().database
                print(f"Beanie database name: {beanie_db.name}")
                
                # Check if Beanie is using the same database
                if beanie_db.name == database.name:
                    print("✓ Beanie is using the same database")
                else:
                    print(f"✗ Beanie is using different database: {beanie_db.name}")
                    
                    # List collections in Beanie's database
                    beanie_collections = await beanie_db.list_collection_names()
                    print(f"Collections in Beanie's database '{beanie_db.name}': {beanie_collections}")
                    
            except Exception as e:
                print(f"Error getting Beanie database info: {e}")
            
            # Check all databases for job_boards collections
            print("\n=== Searching for job_boards in all databases ===")
            for db_name in db_list:
                if db_name not in ['admin', 'local', 'config']:
                    db = client[db_name]
                    collections = await db.list_collection_names()
                    if 'job_boards' in collections:
                        count = await db.job_boards.count_documents({})
                        print(f"Found job_boards in '{db_name}': {count} documents")
                        
                        # Get a sample document
                        sample = await db.job_boards.find_one()
                        if sample:
                            print(f"  Sample: {sample.get('name', 'Unknown')} (ID: {sample.get('_id')})")
        
    except Exception as e:
        print(f"Error during connection debug: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await autoscraper_mongodb_manager.disconnect()

async def main():
    """Main debug function"""
    print("Debugging database connection details...")
    await debug_connection_details()

if __name__ == "__main__":
    asyncio.run(main())