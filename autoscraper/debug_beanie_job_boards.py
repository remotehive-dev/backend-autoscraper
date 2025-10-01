#!/usr/bin/env python3

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv
from app.models.mongodb_models import JobBoard

load_dotenv()

async def debug_job_boards():
    try:
        # Initialize MongoDB connection
        mongodb_url = os.getenv('MONGODB_URL')
        database_name = os.getenv('MONGODB_DATABASE_NAME')
        
        print(f"Connecting to: {database_name}")
        
        client = AsyncIOMotorClient(mongodb_url)
        database = client[database_name]
        
        # Initialize Beanie
        await init_beanie(database=database, document_models=[JobBoard])
        
        # Test direct MongoDB query
        print("\n=== Direct MongoDB Query ===")
        collection = database.job_boards
        direct_count = await collection.count_documents({})
        print(f"Direct MongoDB count: {direct_count}")
        
        # Test Beanie query
        print("\n=== Beanie Query ===")
        try:
            beanie_count = await JobBoard.count()
            print(f"Beanie count: {beanie_count}")
            
            # Try to get first few documents
            job_boards = await JobBoard.find().limit(5).to_list()
            print(f"Beanie returned {len(job_boards)} job boards")
            
            for i, board in enumerate(job_boards, 1):
                print(f"  {i}. {board.name} ({board.type}) - Active: {board.is_active}")
                
        except Exception as e:
            print(f"Beanie query error: {e}")
            import traceback
            traceback.print_exc()
        
        # Test with different limits
        print("\n=== Testing Different Limits ===")
        for limit in [10, 50, 100, 500]:
            try:
                boards = await JobBoard.find().limit(limit).to_list()
                print(f"Limit {limit}: Got {len(boards)} job boards")
            except Exception as e:
                print(f"Limit {limit}: Error - {e}")
        
        # Test pagination
        print("\n=== Testing Pagination ===")
        try:
            page1 = await JobBoard.find().skip(0).limit(10).to_list()
            page2 = await JobBoard.find().skip(10).limit(10).to_list()
            print(f"Page 1: {len(page1)} boards")
            print(f"Page 2: {len(page2)} boards")
        except Exception as e:
            print(f"Pagination error: {e}")
            
    except Exception as e:
        print(f"Connection error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_job_boards())