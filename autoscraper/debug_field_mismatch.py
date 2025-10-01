#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append('/Users/ranjeettiwary/Downloads/developer/RemoteHive_Migration_Package/autoscraper-service')

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.mongodb_models import JobBoard
from config.settings import AutoscraperSettings

async def debug_field_mismatch():
    """Debug field mismatch between database and Beanie model"""
    
    # Get settings
    settings = AutoscraperSettings()
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    database = client.get_database(settings.MONGODB_DATABASE_NAME)
    
    print("=== Field Mismatch Debug ===")
    
    # 1. Check raw MongoDB collection
    print("\n1. Raw MongoDB collection sample:")
    collection = database.job_boards
    sample_doc = await collection.find_one()
    if sample_doc:
        print(f"Sample document fields: {list(sample_doc.keys())}")
        print(f"Sample document: {sample_doc}")
    else:
        print("No documents found in collection")
    
    # 2. Initialize Beanie
    print("\n2. Initializing Beanie...")
    await init_beanie(database=database, document_models=[JobBoard])
    
    # 3. Try to query with Beanie
    print("\n3. Beanie query test:")
    try:
        count = await JobBoard.count()
        print(f"Beanie count: {count}")
        
        # Try to get first document
        first_doc = await JobBoard.find_one()
        if first_doc:
            print(f"First document via Beanie: {first_doc.dict()}")
        else:
            print("No documents found via Beanie")
            
    except Exception as e:
        print(f"Beanie query error: {e}")
    
    # 4. Check field mapping issues
    print("\n4. Field mapping analysis:")
    model_fields = list(JobBoard.__fields__.keys())
    print(f"Model expects fields: {model_fields}")
    
    if sample_doc:
        db_fields = list(sample_doc.keys())
        missing_in_db = set(model_fields) - set(db_fields)
        extra_in_db = set(db_fields) - set(model_fields)
        
        print(f"Missing in database: {missing_in_db}")
        print(f"Extra in database: {extra_in_db}")
        
        # Check specific field mappings
        if 'search_url_template' in missing_in_db and 'rss_url' in extra_in_db:
            print("\n*** FIELD MISMATCH DETECTED ***")
            print("Model expects 'search_url_template' but database has 'rss_url'")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(debug_field_mismatch())