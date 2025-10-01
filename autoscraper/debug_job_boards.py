import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def debug_job_boards():
    client = AsyncIOMotorClient('mongodb+srv://remotehiveofficial_db_user:b9z6QbkaiR3qc2KZ@remotehive.l5zq7k0.mongodb.net/?retryWrites=true&w=majority&appName=Remotehive')
    
    # Check remotehive_autoscraper database
    db = client['remotehive_autoscraper']
    
    # Count total job boards
    total_count = await db['job_boards'].count_documents({})
    print(f'Total job boards in remotehive_autoscraper.job_boards: {total_count}')
    
    # Count active job boards
    active_count = await db['job_boards'].count_documents({'is_active': True})
    print(f'Active job boards: {active_count}')
    
    # Get sample job boards
    sample = await db['job_boards'].find({}).limit(10).to_list(length=10)
    print('\nSample job boards:')
    for i, doc in enumerate(sample, 1):
        name = doc.get('name', 'Unknown')
        is_active = doc.get('is_active', False)
        job_type = doc.get('type', 'Unknown')
        print(f'{i}. {name} (active: {is_active}, type: {job_type})')
    
    # Test the exact query that the API uses
    print('\n--- Testing API Query ---')
    query_filter = {}
    api_results = await db['job_boards'].find(query_filter).skip(0).limit(100).to_list(length=100)
    print(f'API query returned {len(api_results)} job boards')
    
    if api_results:
        print('First 3 results from API query:')
        for i, doc in enumerate(api_results[:3], 1):
            name = doc.get('name', 'Unknown')
            is_active = doc.get('is_active', False)
            print(f'{i}. {name} (active: {is_active})')
    
    client.close()

if __name__ == '__main__':
    asyncio.run(debug_job_boards())