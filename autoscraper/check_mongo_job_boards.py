import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

async def check_mongodb_job_boards():
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(os.getenv('MONGODB_URL'))
        db_name = os.getenv('MONGODB_DATABASE_NAME', 'autoscraper')
        db = client[db_name]
        
        print(f"Connected to database: {db_name}")
        
        # Check job_boards collection
        collection = db.job_boards
        total_count = await collection.count_documents({})
        print(f"Total job boards in MongoDB: {total_count}")
        
        # Check active job boards
        active_count = await collection.count_documents({"is_active": True})
        print(f"Active job boards: {active_count}")
        
        # Get sample documents
        sample_docs = await collection.find({}).limit(10).to_list(10)
        print(f"\nSample documents ({len(sample_docs)}):") 
        for i, doc in enumerate(sample_docs, 1):
            print(f"{i}. {doc.get('name', 'Unknown')} (active: {doc.get('is_active', False)})")
            
        # Check collections in database
        collections = await db.list_collection_names()
        print(f"\nAvailable collections: {collections}")
        
        client.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_mongodb_job_boards())