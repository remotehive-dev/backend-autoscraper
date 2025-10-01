import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

async def check_mongodb_data():
    # MongoDB Atlas connection string
    mongodb_url = "mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive"
    
    print("Connecting to MongoDB Atlas...")
    
    # Use synchronous client for easier debugging
    client = MongoClient(mongodb_url)
    
    try:
        # List all databases
        print("\nAvailable databases:")
        db_names = client.list_database_names()
        for db_name in db_names:
            print(f"  - {db_name}")
        
        # Check remotehive_autoscraper database
        db = client['remotehive_autoscraper']
        print(f"\nCollections in 'remotehive_autoscraper' database:")
        collections = db.list_collection_names()
        for collection in collections:
            count = db[collection].count_documents({})
            print(f"  - {collection}: {count} documents")
        
        # Specifically check job_boards collection
        job_boards_collection = db['job_boards']
        total_job_boards = job_boards_collection.count_documents({})
        active_job_boards = job_boards_collection.count_documents({"is_active": True})
        
        print(f"\nJob Boards Analysis:")
        print(f"  - Total job boards: {total_job_boards}")
        print(f"  - Active job boards: {active_job_boards}")
        
        # Sample a few job boards to see their structure
        print(f"\nSample job boards:")
        sample_boards = list(job_boards_collection.find().limit(3))
        for i, board in enumerate(sample_boards, 1):
            print(f"  {i}. Name: {board.get('name', 'N/A')}")
            print(f"     ID: {board.get('_id', 'N/A')}")
            print(f"     Active: {board.get('is_active', 'N/A')}")
            print(f"     Type: {board.get('type', 'N/A')}")
        
        # Check if there are other databases that might contain job boards
        print(f"\nChecking other databases for job_boards collections:")
        for db_name in db_names:
            if db_name not in ['admin', 'local', 'config']:
                other_db = client[db_name]
                if 'job_boards' in other_db.list_collection_names():
                    count = other_db['job_boards'].count_documents({})
                    print(f"  - {db_name}.job_boards: {count} documents")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()
        print("\nDisconnected from MongoDB Atlas")

if __name__ == "__main__":
    asyncio.run(check_mongodb_data())