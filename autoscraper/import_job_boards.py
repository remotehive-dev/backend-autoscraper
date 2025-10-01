#!/usr/bin/env python3
"""
Job Boards CSV Import Script
Imports job board data from CSV file into MongoDB database
"""

import asyncio
import csv
import os
import sys
from pathlib import Path
from typing import List, Dict
from loguru import logger

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent))

from app.database.mongodb_manager import AutoScraperMongoDBManager
from app.models.mongodb_models import JobBoard, JobBoardType
from config.settings import get_settings

settings = get_settings()


class JobBoardImporter:
    """Handles importing job boards from CSV file"""
    
    def __init__(self):
        self.mongodb_manager = AutoScraperMongoDBManager()
        self.imported_count = 0
        self.skipped_count = 0
        self.error_count = 0
    
    async def connect_database(self):
        """Connect to MongoDB database"""
        success = await self.mongodb_manager.connect()
        if not success:
            raise Exception("Failed to connect to MongoDB")
        logger.info("Connected to MongoDB successfully")
    
    async def disconnect_database(self):
        """Disconnect from MongoDB database"""
        await self.mongodb_manager.disconnect()
        logger.info("Disconnected from MongoDB")
    
    def parse_csv_file(self, csv_file_path: str) -> List[Dict]:
        """Parse CSV file and return list of job board data"""
        job_boards_data = []
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                
                for row_num, row in enumerate(csv_reader, start=2):  # Start from 2 (header is row 1)
                    try:
                        # Clean and validate data
                        name = row.get('name', '').strip()
                        url = row.get('url', '').strip()
                        region = row.get('region', '').strip()
                        
                        if not name or not url:
                            logger.warning(f"Row {row_num}: Missing name or URL, skipping")
                            continue
                        
                        # Ensure URL has protocol
                        if not url.startswith(('http://', 'https://')):
                            url = f"https://{url}"
                        
                        job_board_data = {
                            'name': name,
                            'url': url,
                            'region': region if region else 'Global',
                            'row_number': row_num
                        }
                        
                        job_boards_data.append(job_board_data)
                        
                    except Exception as e:
                        logger.error(f"Error parsing row {row_num}: {e}")
                        continue
        
        except FileNotFoundError:
            logger.error(f"CSV file not found: {csv_file_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            raise
        
        logger.info(f"Parsed {len(job_boards_data)} job boards from CSV")
        return job_boards_data
    
    async def import_job_board(self, job_board_data: Dict) -> bool:
        """Import a single job board into the database"""
        try:
            # Check if job board already exists
            existing = await JobBoard.find_one(JobBoard.name == job_board_data['name'])
            if existing:
                logger.info(f"Job board '{job_board_data['name']}' already exists, skipping")
                self.skipped_count += 1
                return False
            
            # Create new job board
            job_board = JobBoard(
                name=job_board_data['name'],
                type=JobBoardType.GENERAL,  # Default type
                base_url=job_board_data['url'],
                region=job_board_data['region'],
                is_active=True,
                scraping_enabled=True,
                description=f"Job board imported from CSV - {job_board_data['region']} region",
                # Initialize metrics
                total_jobs_scraped=0,
                successful_scrapes=0,
                failed_scrapes=0,
                last_scrape_jobs_count=0
            )
            
            # Save to database
            await job_board.save()
            
            logger.info(f"Imported job board: {job_board_data['name']} ({job_board_data['region']})")
            self.imported_count += 1
            return True
            
        except Exception as e:
            logger.error(f"Error importing job board '{job_board_data['name']}': {e}")
            self.error_count += 1
            return False
    
    async def import_all_job_boards(self, csv_file_path: str):
        """Import all job boards from CSV file"""
        logger.info(f"Starting job boards import from: {csv_file_path}")
        
        # Parse CSV file
        job_boards_data = self.parse_csv_file(csv_file_path)
        
        if not job_boards_data:
            logger.warning("No job boards data to import")
            return
        
        # Connect to database
        await self.connect_database()
        
        try:
            # Import each job board
            for i, job_board_data in enumerate(job_boards_data, 1):
                logger.info(f"Processing {i}/{len(job_boards_data)}: {job_board_data['name']}")
                await self.import_job_board(job_board_data)
                
                # Add small delay to avoid overwhelming the database
                if i % 50 == 0:
                    await asyncio.sleep(0.1)
        
        finally:
            await self.disconnect_database()
        
        # Print summary
        logger.info("\n" + "="*50)
        logger.info("IMPORT SUMMARY")
        logger.info("="*50)
        logger.info(f"Total records processed: {len(job_boards_data)}")
        logger.info(f"Successfully imported: {self.imported_count}")
        logger.info(f"Skipped (already exists): {self.skipped_count}")
        logger.info(f"Errors: {self.error_count}")
        logger.info("="*50)


async def main():
    """Main function to run the import"""
    # Configure logging
    logger.add("import_job_boards.log", rotation="10 MB", level="INFO")
    
    # CSV file path
    csv_file_path = "../job boards.csv"
    
    # Check if CSV file exists
    if not os.path.exists(csv_file_path):
        logger.error(f"CSV file not found: {csv_file_path}")
        logger.info("Please ensure the 'job boards.csv' file is in the parent directory")
        return
    
    # Create importer and run import
    importer = JobBoardImporter()
    
    try:
        await importer.import_all_job_boards(csv_file_path)
        logger.info("Job boards import completed successfully!")
    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())