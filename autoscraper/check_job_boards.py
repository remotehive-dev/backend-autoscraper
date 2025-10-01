import asyncio
from app.database.mongodb_manager import get_autoscraper_mongodb_manager
from app.models.mongodb_models import JobBoard

async def check_job_boards():
    try:
        # Get MongoDB manager
        mongodb_manager = await get_autoscraper_mongodb_manager()
        
        # Query job boards using Beanie ODM
        job_boards = await JobBoard.find_all().to_list()
        print(f'Found {len(job_boards)} job boards in MongoDB:')
        
        active_count = 0
        for jb in job_boards:
            name = jb.name
            jb_type = jb.type
            is_active = jb.is_active
            if is_active:
                active_count += 1
            print(f'- {name} ({jb_type}) - Active: {is_active}')
        
        print(f'\nTotal active job boards: {active_count}')
        
    except Exception as e:
        print(f'Error checking job boards: {e}')

if __name__ == '__main__':
    asyncio.run(check_job_boards())