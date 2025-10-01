#!/usr/bin/env python3
"""
Celery Tasks for Autoscraper Service
Background tasks for scraping operations
"""

import time
import asyncio
from datetime import datetime
from celery import Celery
from loguru import logger
from typing import Optional

from app.database.mongodb_manager import AutoScraperMongoDBManager
from app.models.mongodb_models import ScrapeJob, JobBoard, ScrapeJobStatus
from app.services.services import ScrapingService
from config.settings import get_settings

settings = get_settings()

# Initialize Celery app
celery_app = Celery(
    'autoscraper',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'app.services.tasks.run_scrape_job': {'queue': 'autoscraper.default'},
    }
)

db_manager = AutoScraperMongoDBManager()


async def _run_scrape_job_async(job_id: str):
    """
    Async helper function for scrape job execution
    """
    logger.info(f"Starting scrape job {job_id}")
    
    try:
        from bson import ObjectId
        
        # Find the scrape job
        scrape_job = await ScrapeJob.get(ObjectId(job_id))
        
        if not scrape_job:
            logger.error(f"Scrape job {job_id} not found")
            return {"success": False, "error": "Job not found"}
        
        # Get job board
        job_board = await JobBoard.get(scrape_job.job_board_id)
        
        if not job_board:
            logger.error(f"Job board {scrape_job.job_board_id} not found")
            scrape_job.status = ScrapeJobStatus.FAILED
            scrape_job.error_message = "Job board not found"
            scrape_job.completed_at = datetime.utcnow()
            await scrape_job.save()
            return {"success": False, "error": "Job board not found"}
            
        # Update job status to running
        scrape_job.status = ScrapeJobStatus.RUNNING
        scrape_job.started_at = datetime.utcnow()
        await scrape_job.save()
            
        # Initialize scraping service
        scraping_service = ScrapingService()
        
        # Execute the scraping
        result = await scraping_service.scrape_job_board(
            job_board_id=str(job_board.id),
            scrape_job_id=str(scrape_job.id)
        )
        
        # Update job status based on result
        if result.success:
            scrape_job.status = ScrapeJobStatus.COMPLETED
            scrape_job.total_items_found = result.items_found
            scrape_job.total_items_processed = result.items_processed
            scrape_job.total_items_created = result.items_saved
            logger.info(f"Scrape job {job_id} completed successfully")
        else:
            scrape_job.status = ScrapeJobStatus.FAILED
            scrape_job.error_message = result.error_message or "Unknown error"
            logger.error(f"Scrape job {job_id} failed: {scrape_job.error_message}")
        
        scrape_job.completed_at = datetime.utcnow()
        await scrape_job.save()
        
        return {
            "success": result.success,
            "items_found": result.items_found,
            "items_processed": result.items_processed,
            "items_saved": result.items_saved,
            "error": result.error_message
        }
            
    except Exception as e:
        logger.error(f"Error executing scrape job {job_id}: {str(e)}")
        
        # Update job status to failed
        try:
            scrape_job = await ScrapeJob.get(ObjectId(job_id))
            if scrape_job:
                scrape_job.status = ScrapeJobStatus.FAILED
                scrape_job.error_message = str(e)
                scrape_job.completed_at = datetime.utcnow()
                await scrape_job.save()
        except Exception as db_error:
            logger.error(f"Failed to update job status: {str(db_error)}")
        
        return {"success": False, "error": str(e)}


@celery_app.task(bind=True, name='app.services.tasks.run_scrape_job')
def run_scrape_job(self, job_id: str):
    """
    Execute a scrape job in the background
    
    Args:
        job_id: The ID of the scrape job to execute
    
    Returns:
        dict: Result of the scrape operation
    """
    # Run the async function in a new event loop
    return asyncio.run(_run_scrape_job_async(job_id))