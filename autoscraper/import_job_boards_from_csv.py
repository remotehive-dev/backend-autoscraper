import asyncio
import csv
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.models.mongodb_models import JobBoard, JobBoardType
from config.settings import settings

async def import_job_boards_from_csv():
    """Import job boards from CSV file to MongoDB Atlas"""
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    database = client[settings.MONGODB_DATABASE_NAME]
    
    # Initialize Beanie
    await init_beanie(database=database, document_models=[JobBoard])
    
    # Path to CSV file
    csv_file_path = "/Users/ranjeettiwary/Downloads/developer/RemoteHive_Migration_Package/job boards.csv"
    
    if not os.path.exists(csv_file_path):
        print(f"CSV file not found: {csv_file_path}")
        return
    
    # Count existing job boards
    existing_count = await JobBoard.count()
    print(f"Existing job boards in database: {existing_count}")
    
    # Read CSV and import job boards
    imported_count = 0
    skipped_count = 0
    
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        csv_reader = csv.DictReader(file)
        
        for row in csv_reader:
            name = row['name'].strip()
            url = row['url'].strip()
            region = row['region'].strip()
            
            # Check if job board already exists
            existing_job_board = await JobBoard.find_one(JobBoard.name == name)
            
            if existing_job_board:
                print(f"Skipping existing job board: {name}")
                skipped_count += 1
                continue
            
            # Create new job board
            job_board = JobBoard(
                name=name,
                type=JobBoardType.CUSTOM,  # Use enum value
                base_url=url,
                search_url_template=f"{url}/jobs",  # Default template
                is_active=True,
                region=region,
                selectors={
                    "job_title": ".job-title",
                    "company_name": ".company-name", 
                    "location": ".job-location",
                    "job_url": ".job-link",
                    "description": ".job-description"
                },
                rate_limit_delay=1.0,
                max_pages_per_search=5
            )
            
            try:
                await job_board.insert()
                imported_count += 1
                print(f"Imported: {name} ({region})")
            except Exception as e:
                print(f"Error importing {name}: {str(e)}")
    
    # Final count
    final_count = await JobBoard.count()
    
    print(f"\n=== Import Summary ===")
    print(f"Job boards imported: {imported_count}")
    print(f"Job boards skipped (already exist): {skipped_count}")
    print(f"Total job boards in database: {final_count}")
    
    # Show sample of imported data
    sample_boards = await JobBoard.find().limit(5).to_list()
    print(f"\nSample job boards:")
    for board in sample_boards:
        print(f"- {board.name} ({board.region}) - Active: {board.is_active}")

if __name__ == "__main__":
    asyncio.run(import_job_boards_from_csv())