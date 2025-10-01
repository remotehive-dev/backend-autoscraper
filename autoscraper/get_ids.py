import asyncio
from app.models.mongodb_models import JobBoard
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

async def get_job_board_ids():
    try:
        # Initialize MongoDB connection
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        database = client.remotehive_autoscraper
        
        # Initialize Beanie
        await init_beanie(database=database, document_models=[JobBoard])
        
        # Get all job boards
        boards = await JobBoard.find_all().to_list()
        print("Job Board ObjectIds:")
        for board in boards:
            print(f"{board.name}: {board.id}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(get_job_board_ids())