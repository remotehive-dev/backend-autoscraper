#!/usr/bin/env python3
"""
Test Beanie ODM directly with the same setup as the service
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.mongodb_models import JobBoard

async def test_beanie_direct():
    """
    Test Beanie ODM directly to see if it can find job boards
    """
    
    # Use the same connection string and database name as the service
    connection_string = "mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive"
    database_name = "remotehive_autoscraper"
    
    try:
        # Create client and get database
        client = AsyncIOMotorClient(connection_string)
        database = client[database_name]
        
        # Test connection
        await client.admin.command('ping')
        print("✅ Connected to MongoDB Atlas")
        
        # Initialize Beanie with just JobBoard model
        await init_beanie(database=database, document_models=[JobBoard])
        print("✅ Beanie initialized")
        
        # Test direct MongoDB query first
        raw_count = await database.job_boards.count_documents({})
        print(f"📊 Raw MongoDB count: {raw_count}")
        
        # Test Beanie query
        beanie_count = await JobBoard.find().count()
        print(f"📊 Beanie count: {beanie_count}")
        
        # Test with empty filter (same as API)
        query_filter = {}
        beanie_filtered_count = await JobBoard.find(query_filter).count()
        print(f"📊 Beanie filtered count: {beanie_filtered_count}")
        
        # Get sample documents
        sample_docs = await JobBoard.find().limit(3).to_list()
        print(f"📄 Sample documents found: {len(sample_docs)}")
        
        for i, doc in enumerate(sample_docs):
            print(f"   Document {i+1}: {doc.name} - Active: {doc.is_active}")
        
        # Test the exact same query as the API
        api_query_filter = {}
        api_docs = await JobBoard.find(api_query_filter).skip(0).limit(5).to_list()
        print(f"📄 API-style query found: {len(api_docs)} documents")
        
        # Close connection
        client.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_beanie_direct())