#!/usr/bin/env python3
"""
Direct MongoDB Atlas Connection Check
Verify connection and count job boards in remotehive_autoscraper database
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from config.settings import get_settings
from app.models.mongodb_models import JobBoard

async def check_mongodb_connection():
    """Check MongoDB Atlas connection and count job boards"""
    
    try:
        # Get settings
        settings = get_settings()
        print(f"MongoDB URL: {settings.MONGODB_URL}")
        
        # Create MongoDB client
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        
        # Test connection
        await client.admin.command('ping')
        print("✅ MongoDB Atlas connection successful!")
        
        # Get database
        db = client.remotehive_autoscraper
        
        # Initialize Beanie
        await init_beanie(database=db, document_models=[JobBoard])
        print("✅ Beanie initialized successfully!")
        
        # Count total job boards
        total_count = await JobBoard.count()
        print(f"\n📊 Total job boards in database: {total_count}")
        
        # Count active job boards
        active_count = await JobBoard.find({"is_active": True}).count()
        print(f"📊 Active job boards: {active_count}")
        
        # Count inactive job boards
        inactive_count = await JobBoard.find({"is_active": False}).count()
        print(f"📊 Inactive job boards: {inactive_count}")
        
        # Get sample job boards
        sample_job_boards = await JobBoard.find().limit(10).to_list()
        print(f"\n📋 Sample job boards (first 10):")
        for i, jb in enumerate(sample_job_boards, 1):
            print(f"  {i}. {jb.name} - Active: {jb.is_active} - Type: {jb.type}")
        
        # Check for different job board types
        type_counts = {}
        all_job_boards = await JobBoard.find().to_list()
        for jb in all_job_boards:
            job_type = str(jb.type) if jb.type else "None"
            type_counts[job_type] = type_counts.get(job_type, 0) + 1
        
        print(f"\n📈 Job boards by type:")
        for job_type, count in type_counts.items():
            print(f"  {job_type}: {count}")
        
        # Check collections in database
        collections = await db.list_collection_names()
        print(f"\n📁 Collections in remotehive_autoscraper database:")
        for collection in collections:
            count = await db[collection].count_documents({})
            print(f"  {collection}: {count} documents")
        
        # Check if there are other databases
        databases = await client.list_database_names()
        print(f"\n🗄️ Available databases:")
        for database in databases:
            if 'remotehive' in database.lower():
                print(f"  {database} (RemoteHive related)")
            else:
                print(f"  {database}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    asyncio.run(check_mongodb_connection())