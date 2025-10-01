#!/usr/bin/env python3

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.mongodb_models import JobBoard
from config.settings import get_settings

async def debug_collections():
    """Debug MongoDB collections and databases"""
    settings = get_settings()
    
    print(f"MongoDB URL from settings: {settings.MONGODB_URL}")
    print(f"Database name from settings: {settings.MONGODB_DATABASE_NAME}")
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    
    try:
        # List all databases
        databases = await client.list_database_names()
        print(f"\nAvailable databases: {databases}")
        
        # Check the specific database
        db = client[settings.MONGODB_DATABASE_NAME]
        collections = await db.list_collection_names()
        print(f"\nCollections in '{settings.MONGODB_DATABASE_NAME}': {collections}")
        
        # Check job_boards collection specifically
        if "job_boards" in collections:
            job_boards_count = await db.job_boards.count_documents({})
            print(f"\nTotal documents in job_boards collection: {job_boards_count}")
            
            # Get sample documents
            sample_docs = await db.job_boards.find({}).limit(5).to_list(length=5)
            print(f"\nSample job boards from direct MongoDB query:")
            for doc in sample_docs:
                print(f"  - {doc.get('name', 'Unknown')} (ID: {doc.get('_id')})")
        
        # Initialize Beanie and test
        await init_beanie(database=db, document_models=[JobBoard])
        
        # Test Beanie query
        beanie_count = await JobBoard.count()
        print(f"\nTotal job boards via Beanie: {beanie_count}")
        
        # Test with different queries
        active_count = await JobBoard.find({"is_active": True}).count()
        print(f"Active job boards via Beanie: {active_count}")
        
        # Get sample via Beanie
        beanie_samples = await JobBoard.find().limit(5).to_list()
        print(f"\nSample job boards via Beanie:")
        for job_board in beanie_samples:
            print(f"  - {job_board.name} (ID: {job_board.id}, Active: {job_board.is_active})")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(debug_collections())