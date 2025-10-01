#!/usr/bin/env python3
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_main_db():
    """Check job board count in main remotehive database"""
    client = AsyncIOMotorClient('mongodb://localhost:27017/remotehive')
    db = client.remotehive
    
    try:
        count = await db.job_boards.count_documents({})
        print(f"Job boards in main 'remotehive' database: {count}")
        
        # Also check active job boards
        active_count = await db.job_boards.count_documents({"is_active": True})
        print(f"Active job boards in main database: {active_count}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check_main_db())