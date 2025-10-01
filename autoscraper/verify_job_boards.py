import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError

async def verify_job_boards():
    try:
        # MongoDB connection
        mongodb_url = "mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive"
        client = AsyncIOMotorClient(mongodb_url)
        
        # Connect to the database
        db = client['remotehive_autoscraper']
        
        print("\n=== MongoDB Connection Successful ===")
        print(f"Database: remotehive_autoscraper")
        
        # List all collections
        collections = await db.list_collection_names()
        print(f"\nCollections in remotehive_autoscraper: {collections}")
        
        # Check job_boards collection specifically
        if 'job_boards' in collections:
            job_boards_collection = db['job_boards']
            
            # Get total count
            total_count = await job_boards_collection.count_documents({})
            print(f"\nTotal job_boards documents: {total_count}")
            
            # Get first 5 documents to see structure
            cursor = job_boards_collection.find({}).limit(5)
            documents = await cursor.to_list(length=5)
            
            print(f"\nFirst 5 job_boards documents:")
            for i, doc in enumerate(documents, 1):
                print(f"\n{i}. ID: {doc.get('_id')}")
                print(f"   Name: {doc.get('name')}")
                print(f"   Base URL: {doc.get('base_url')}")
                print(f"   Type: {doc.get('type')}")
                print(f"   Is Active: {doc.get('is_active')}")
                
            # Check if there are any filters that might be limiting results
            active_count = await job_boards_collection.count_documents({"is_active": True})
            inactive_count = await job_boards_collection.count_documents({"is_active": False})
            
            print(f"\nActive job boards: {active_count}")
            print(f"Inactive job boards: {inactive_count}")
            
            # Check for any other potential collections with job board data
            for collection_name in collections:
                if 'job' in collection_name.lower() or 'board' in collection_name.lower():
                    collection = db[collection_name]
                    count = await collection.count_documents({})
                    print(f"\nCollection '{collection_name}': {count} documents")
                    
                    if count > 0 and count < 10:  # Show sample if small collection
                        sample_doc = await collection.find_one({})
                        print(f"Sample document keys: {list(sample_doc.keys()) if sample_doc else 'None'}")
        else:
            print("\nNo 'job_boards' collection found!")
            
            # Check all collections for job board-like data
            for collection_name in collections:
                collection = db[collection_name]
                count = await collection.count_documents({})
                print(f"\nCollection '{collection_name}': {count} documents")
                
                if count > 500:  # Likely candidate for job boards
                    sample_doc = await collection.find_one({})
                    print(f"Sample document keys: {list(sample_doc.keys()) if sample_doc else 'None'}")
        
        await client.close()
        
    except ServerSelectionTimeoutError:
        print("Failed to connect to MongoDB Atlas - DNS resolution error")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify_job_boards())