import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_collections():
    client = AsyncIOMotorClient('mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive')
    
    # Check remotehive database
    db = client['remotehive']
    collections = await db.list_collection_names()
    print('Collections in remotehive database:')
    for col in sorted(collections):
        count = await db[col].count_documents({})
        print(f'- {col}: {count} documents')
    
    # Check remotehive_autoscraper database
    db_autoscraper = client['remotehive_autoscraper']
    collections_autoscraper = await db_autoscraper.list_collection_names()
    print('\nCollections in remotehive_autoscraper database:')
    for col in sorted(collections_autoscraper):
        count = await db_autoscraper[col].count_documents({})
        print(f'- {col}: {count} documents')
    
    client.close()

if __name__ == '__main__':
    asyncio.run(check_collections())