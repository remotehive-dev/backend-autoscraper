import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

async def check_atlas_data():
    # Use the MongoDB Atlas connection string
    mongodb_url = "mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive"
    database_name = "remotehive_autoscraper"
    
    print(f"Connecting to MongoDB Atlas...")
    print(f"Database: {database_name}")
    
    # Create async client
    client = AsyncIOMotorClient(mongodb_url)
    db = client[database_name]
    
    try:
        # List all collections
        collections = await db.list_collection_names()
        print(f"\nCollections in database: {collections}")
        
        # Check job_boards collection specifically
        if "job_boards" in collections:
            job_boards_collection = db.job_boards
            
            # Count total documents
            total_count = await job_boards_collection.count_documents({})
            print(f"\nTotal job boards in Atlas: {total_count}")
            
            # Get a few sample documents
            sample_docs = []
            async for doc in job_boards_collection.find({}).limit(5):
                # Convert ObjectId to string for printing
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
                sample_docs.append(doc)
            
            print(f"\nSample job boards:")
            for i, doc in enumerate(sample_docs, 1):
                print(f"{i}. Name: {doc.get('name', 'N/A')}, Type: {doc.get('type', 'N/A')}, Active: {doc.get('is_active', 'N/A')}")
                
            # Check if there are any filters that might be limiting results
            active_count = await job_boards_collection.count_documents({"is_active": True})
            print(f"\nActive job boards: {active_count}")
            
            inactive_count = await job_boards_collection.count_documents({"is_active": False})
            print(f"Inactive job boards: {inactive_count}")
            
        else:
            print("\nNo 'job_boards' collection found in the database!")
            
        # Also check if there are other collections that might contain job board data
        for collection_name in collections:
            if "job" in collection_name.lower():
                collection = db[collection_name]
                count = await collection.count_documents({})
                print(f"Collection '{collection_name}': {count} documents")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check_atlas_data())