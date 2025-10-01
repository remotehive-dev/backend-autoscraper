import asyncio
from app.models.mongodb_models import JobBoard
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

async def check_db():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client.autoscraper_db
    await init_beanie(database=db, document_models=[JobBoard])
    
    boards = await JobBoard.find_all().to_list()
    print(f'Total job boards: {len(boards)}')
    
    for i, board in enumerate(boards[:5]):
        print(f'Board {i+1}:')
        print(f'  ID: {board.id}')
        print(f'  Name: {board.name}')
        print(f'  Active: {board.is_active}')
        print(f'  Type: {getattr(board, "id", "No id field")}')
        print('---')

if __name__ == '__main__':
    asyncio.run(check_db())