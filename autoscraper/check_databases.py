import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def check_databases():
    # Get MongoDB connection string
    mongodb_url = os.getenv('MONGODB_URL')
    print(f"Connecting to: {mongodb_url[:50]}...")
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(mongodb_url)
    
    try:
        # List all databases
        print("\n📋 Available databases:")
        db_list = await client.list_database_names()
        for db_name in db_list:
            print(f"  - {db_name}")
        
        # Check each database for job_boards collection
        print("\n🔍 Checking for job_boards collection in each database:")
        for db_name in db_list:
            if db_name in ['admin', 'local', 'config']:  # Skip system databases
                continue
                
            db = client[db_name]
            collections = await db.list_collection_names()
            
            if 'job_boards' in collections:
                collection = db['job_boards']
                count = await collection.count_documents({})
                active_count = await collection.count_documents({'is_active': True})
                
                print(f"  ✅ {db_name}:")
                print(f"     - Total job boards: {count}")
                print(f"     - Active job boards: {active_count}")
                
                # Sample a few documents
                sample_docs = await collection.find({}, {'name': 1, 'is_active': 1, 'type': 1}).limit(3).to_list(3)
                print(f"     - Sample job boards:")
                for doc in sample_docs:
                    print(f"       * {doc.get('name', 'N/A')} (Active: {doc.get('is_active', False)}, Type: {doc.get('type', 'N/A')})")
            else:
                print(f"  ❌ {db_name}: No job_boards collection")
        
        # Specifically check the autoscraper database
        print("\n🎯 Detailed check of remotehive_autoscraper database:")
        autoscraper_db = client['remotehive_autoscraper']
        collections = await autoscraper_db.list_collection_names()
        print(f"Collections in remotehive_autoscraper: {collections}")
        
        if 'job_boards' in collections:
            job_boards_collection = autoscraper_db['job_boards']
            total = await job_boards_collection.count_documents({})
            active = await job_boards_collection.count_documents({'is_active': True})
            print(f"Job boards in remotehive_autoscraper: {total} total, {active} active")
            
            # Get all job boards to see what's there
            all_boards = await job_boards_collection.find({}, {'name': 1, 'is_active': 1, 'created_at': 1}).to_list(None)
            print(f"\nAll job boards in remotehive_autoscraper:")
            for i, board in enumerate(all_boards, 1):
                print(f"  {i}. {board.get('name', 'N/A')} (Active: {board.get('is_active', False)}, Created: {board.get('created_at', 'N/A')})")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check_databases())