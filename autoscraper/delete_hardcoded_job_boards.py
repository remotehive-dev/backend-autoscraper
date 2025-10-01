#!/usr/bin/env python3
import asyncio
from app.models.mongodb_models import JobBoard, JobBoardType
from app.database.mongodb_manager import get_autoscraper_mongodb_manager

# List of hardcoded job board names that need to be deleted
HARDCODED_JOB_BOARDS = [
    "Indeed Jobs",
    "LinkedIn Jobs", 
    "Glassdoor",
    "Monster",
    "ZipRecruiter",
    "CareerBuilder",
    "Dice",
    "Remote OK",
    "We Work Remotely",
    "AngelList",
    "FlexJobs",
    "Upwork",
    "Freelancer",
    "Toptal",
    "Guru",
    "Stack Overflow Jobs",
    "GitHub Jobs"
]

async def delete_hardcoded_job_boards():
    """Delete the 17 hardcoded job boards that were created by populate_job_boards.py"""
    try:
        manager = await get_autoscraper_mongodb_manager()
        
        # Check current job boards count
        initial_count = await JobBoard.count()
        print(f"Initial job boards in database: {initial_count}")
        
        deleted_count = 0
        
        # Delete each hardcoded job board by name
        for job_board_name in HARDCODED_JOB_BOARDS:
            result = await JobBoard.find_one(JobBoard.name == job_board_name)
            if result:
                await result.delete()
                deleted_count += 1
                print(f"Deleted: {job_board_name}")
            else:
                print(f"Not found: {job_board_name}")
        
        # Final count
        final_count = await JobBoard.count()
        
        print(f"\n=== Summary ===")
        print(f"Initial job boards: {initial_count}")
        print(f"Job boards deleted: {deleted_count}")
        print(f"Final job boards: {final_count}")
        
        return deleted_count
        
    except Exception as e:
        print(f"Error deleting hardcoded job boards: {e}")
        import traceback
        traceback.print_exc()
        return 0

if __name__ == '__main__':
    asyncio.run(delete_hardcoded_job_boards())