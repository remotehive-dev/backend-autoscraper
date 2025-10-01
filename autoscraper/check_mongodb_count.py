import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_databases():
    client = AsyncIOMotorClient('mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive')
    
    # List all databases
    databases = await client.list_database_names()
    print(f'Available databases: {databases}')
    
    # Check each database for job_boards collection
    for db_name in databases:
        if db_name in ['admin', 'local', 'config']:  # Skip system databases
            continue
            
        db = client[db_name]
        collections = await db.list_collection_names()
        print(f'\nDatabase: {db_name}')
        print(f'Collections: {collections}')
        
        # Check if job_boards collection exists
        if 'job_boards' in collections:
            job_boards_count = await db.job_boards.count_documents({})
            print(f'*** FOUND job_boards collection with {job_boards_count} documents! ***')
            
            # Sample a job board to see structure
            if job_boards_count > 0:
                sample = await db.job_boards.find_one({})
                if sample:
                    print(f'Sample job board fields: {list(sample.keys())}')
                    print(f'Sample name: {sample.get("name", "N/A")}')
                    print(f'Sample is_active: {sample.get("is_active", "N/A")}')
    
    client.close()

if __name__ == '__main__':
    asyncio.run(check_databases())