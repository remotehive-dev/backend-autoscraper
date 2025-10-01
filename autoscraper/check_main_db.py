#!/usr/bin/env python3
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.mongodb_models import JobBoard

async def check_main_database():
    """Check job boards in main remotehive database"""
    try:
        # Connect to main remotehive database
        mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/remotehive")
        client = AsyncIOMotorClient(mongodb_url)
        
        # Check remotehive database
        main_db = client["remotehive"]
        await init_beanie(database=main_db, document_models=[JobBoard])
        
        count = await JobBoard.count()
        print(f"Job boards in 'remotehive' database: {count}")
        
        if count > 0:
            job_boards = await JobBoard.find().limit(10).to_list()
            print("\nSample job boards from remotehive:")
            for jb in job_boards:
                print(f"- {jb.name} ({jb.type}) - Active: {jb.is_active}")
        
        # Also check remotehive_autoscraper database
        autoscraper_db = client["remotehive_autoscraper"]
        await init_beanie(database=autoscraper_db, document_models=[JobBoard])
        
        count_autoscraper = await JobBoard.count()
        print(f"\nJob boards in 'remotehive_autoscraper' database: {count_autoscraper}")
        
        if count_autoscraper > 0:
            job_boards_auto = await JobBoard.find().limit(10).to_list()
            print("\nSample job boards from remotehive_autoscraper:")
            for jb in job_boards_auto:
                print(f"- {jb.name} ({jb.type}) - Active: {jb.is_active}")
        
        client.close()
        
    except Exception as e:
        print(f"Error checking databases: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_main_database())