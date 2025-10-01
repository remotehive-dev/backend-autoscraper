import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def check_mongodb_job_boards():
    try:
        # Connect to MongoDB
        mongodb_url = os.getenv('MONGODB_URL')
        database_name = os.getenv('MONGODB_DATABASE_NAME', 'autoscraper')
        
        print(f"Connecting to MongoDB: {mongodb_url}")
        print(f"Database: {database_name}")
        
        client = AsyncIOMotorClient(mongodb_url)
        db = client[database_name]
        
        # Check job_boards collection
        count = await db.job_boards.count_documents({})
        print(f"\nTotal job boards in MongoDB: {count}")
        
        # Get sample documents
        docs = await db.job_boards.find({}).limit(10).to_list(10)
        print(f"Sample documents found: {len(docs)}")
        
        for i, doc in enumerate(docs, 1):
            name = doc.get('name', 'Unknown')
            base_url = doc.get('base_url', 'No URL')
            is_active = doc.get('is_active', False)
            print(f"{i}. {name} - {base_url} (Active: {is_active})")
        
        # List all collections
        collections = await db.list_collection_names()
        print(f"\nAvailable collections: {collections}")
        
        # Check if there are other job board related collections
        for collection_name in collections:
            if 'job' in collection_name.lower() or 'board' in collection_name.lower():
                collection_count = await db[collection_name].count_documents({})
                print(f"Collection '{collection_name}': {collection_count} documents")
        
        client.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_mongodb_job_boards())