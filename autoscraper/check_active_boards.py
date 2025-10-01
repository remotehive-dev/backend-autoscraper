import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def check_active_boards():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client.remotehive_autoscraper
    collection = db.job_boards
    
    # Get all job boards
    all_boards = await collection.find({}).to_list(length=None)
    print(f'Total job boards: {len(all_boards)}')
    
    # Check active status
    active_boards = await collection.find({'is_active': True}).to_list(length=None)
    print(f'Active job boards: {len(active_boards)}')
    
    # Show details of first few active boards
    print('\nActive job boards:')
    for i, board in enumerate(active_boards[:5]):
        print(f'Board {i+1}:')
        print(f'  _id: {board["_id"]}')
        print(f'  id: {board.get("id", "No id field")}')
        print(f'  name: {board["name"]}')
        print(f'  is_active: {board["is_active"]}')
        print('---')
    
    # Check if any boards have the UUIDs we're trying to use
    test_uuids = [
        "162a4e2d-8400-5e57-baa9-e47d88d0c144",
        "477d7139-8310-5a3c-8a85-02a629cd470a",
        "9c226492-b169-5b5c-8196-ddfd9d8ad08f"
    ]
    
    print('\nChecking for test UUIDs:')
    for uuid in test_uuids:
        # Check by id field
        board_by_id = await collection.find_one({'id': uuid})
        # Check by _id field (if it's a string)
        board_by_object_id = await collection.find_one({'_id': uuid})
        
        print(f'UUID {uuid}:')
        print(f'  Found by id field: {"Yes" if board_by_id else "No"}')
        print(f'  Found by _id field: {"Yes" if board_by_object_id else "No"}')
        if board_by_id:
            print(f'  Name: {board_by_id["name"]}, Active: {board_by_id["is_active"]}')
        elif board_by_object_id:
            print(f'  Name: {board_by_object_id["name"]}, Active: {board_by_object_id["is_active"]}')

if __name__ == '__main__':
    asyncio.run(check_active_boards())