import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_databases():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    dbs = await client.list_database_names()
    print('Available databases:', dbs)
    
    # Check each database for job board collections
    for db_name in dbs:
        if db_name not in ['admin', 'config', 'local']:
            db = client[db_name]
            collections = await db.list_collection_names()
            print(f'\nDatabase: {db_name}')
            print(f'Collections: {collections}')
            
            # Check for job board related collections
            for collection_name in collections:
                if 'job' in collection_name.lower() or 'board' in collection_name.lower():
                    collection = db[collection_name]
                    count = await collection.count_documents({})
                    print(f'  {collection_name}: {count} documents')
                    
                    # Show a sample document
                    if count > 0:
                        sample = await collection.find_one()
                        print(f'    Sample: {sample}')

if __name__ == '__main__':
    asyncio.run(check_databases())