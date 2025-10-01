#!/usr/bin/env python3
"""
Database Initialization Script
Populates initial data and tests database relationships
"""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add the project root to Python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.database.database import get_db_session
from app.models.models import (
    JobBoard, ScheduleConfig, ScrapeJob, EngineState,
    JobBoardType, ScrapeJobMode, ScrapeJobStatus, EngineStatus
)
from loguru import logger


def init_engine_state():
    """Initialize engine state"""
    session = next(get_db_session())
    try:
        # Check if engine state already exists
        existing_state = session.query(EngineState).first()
        if existing_state:
            logger.info("Engine state already exists")
            return existing_state
        
        # Create initial engine state
        engine_state = EngineState(
            status=EngineStatus.IDLE,
            last_heartbeat=datetime.now(timezone.utc),
            active_jobs_count=0,
            queued_jobs_count=0,
            total_jobs_processed=0,
            total_jobs_today=0,
            success_rate_today=0.0,
            average_job_duration=0.0,
            success_rate=0.0,
            memory_usage_mb=0.0,
            cpu_usage_percent=0.0,
            system_load=0.0,
            max_concurrent_jobs=5,
            maintenance_mode=False,
            version="1.0.0",
            configuration={"initialized": True},
            consecutive_errors=0,
            error_count_today=0,
            uptime_seconds=0
        )
        
        session.add(engine_state)
        session.commit()
        logger.info("Engine state initialized successfully")
        return engine_state
        
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to initialize engine state: {e}")
        raise
    finally:
        session.close()


def init_sample_job_boards():
    """Initialize sample job boards"""
    session = next(get_db_session())
    try:
        # Check if job boards already exist
        existing_count = session.query(JobBoard).count()
        if existing_count > 0:
            logger.info(f"Job boards already exist ({existing_count} found)")
            return
        
        # Sample job boards
        job_boards = [
            JobBoard(
                id=uuid.uuid4(),
                name="Indeed",
                description="Indeed job board scraper",
                type=JobBoardType.HTML,
                base_url="https://indeed.com",
                selectors={
                    "job_title": ".jobsearch-SerpJobCard .title a",
                    "company": ".jobsearch-SerpJobCard .company",
                    "location": ".jobsearch-SerpJobCard .location",
                    "description": ".jobsearch-SerpJobCard .summary"
                },
                headers={"User-Agent": "RemoteHive-AutoScraper/1.0"},
                rate_limit_delay=2,
                max_pages=10,
                request_timeout=30,
                retry_attempts=3,
                quality_threshold=0.8,
                is_active=True,
                success_rate=0.0,
                total_scrapes=0,
                successful_scrapes=0,
                failed_scrapes=0
            ),
            JobBoard(
                id=uuid.uuid4(),
                name="LinkedIn",
                description="LinkedIn job board scraper",
                type=JobBoardType.HTML,
                base_url="https://linkedin.com/jobs",
                selectors={
                    "job_title": ".job-search-card__title",
                    "company": ".job-search-card__company-name",
                    "location": ".job-search-card__location",
                    "description": ".job-search-card__description"
                },
                headers={"User-Agent": "RemoteHive-AutoScraper/1.0"},
                rate_limit_delay=3,
                max_pages=5,
                request_timeout=45,
                retry_attempts=3,
                quality_threshold=0.9,
                is_active=True,
                success_rate=0.0,
                total_scrapes=0,
                successful_scrapes=0,
                failed_scrapes=0
            ),
            JobBoard(
                id=uuid.uuid4(),
                name="RemoteOK",
                description="RemoteOK RSS feed scraper",
                type=JobBoardType.RSS,
                base_url="https://remoteok.io",
                rss_url="https://remoteok.io/remote-jobs.rss",
                headers={"User-Agent": "RemoteHive-AutoScraper/1.0"},
                rate_limit_delay=1,
                max_pages=1,
                request_timeout=20,
                retry_attempts=2,
                quality_threshold=0.7,
                is_active=True,
                success_rate=0.0,
                total_scrapes=0,
                successful_scrapes=0,
                failed_scrapes=0
            )
        ]
        
        for job_board in job_boards:
            session.add(job_board)
        
        session.commit()
        logger.info(f"Initialized {len(job_boards)} sample job boards")
        return job_boards
        
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to initialize job boards: {e}")
        raise
    finally:
        session.close()


def init_sample_schedules():
    """Initialize sample schedule configurations"""
    session = next(get_db_session())
    try:
        # Get job boards
        job_boards = session.query(JobBoard).all()
        if not job_boards:
            logger.warning("No job boards found, skipping schedule initialization")
            return
        
        # Check if schedules already exist
        existing_count = session.query(ScheduleConfig).count()
        if existing_count > 0:
            logger.info(f"Schedule configs already exist ({existing_count} found)")
            return
        
        # Create schedules for each job board
        schedules = []
        for job_board in job_boards:
            schedule = ScheduleConfig(
                id=uuid.uuid4(),
                job_board_id=job_board.id,
                name=f"{job_board.name} Daily Scrape",
                description=f"Daily scraping schedule for {job_board.name}",
                cron_expression="0 9 * * *",  # Daily at 9 AM
                timezone="UTC",
                is_enabled=True,
                max_concurrent_jobs=2,
                max_retries=3,
                retry_delay_minutes=15,
                next_run_at=datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
            )
            schedules.append(schedule)
            session.add(schedule)
        
        session.commit()
        logger.info(f"Initialized {len(schedules)} sample schedule configurations")
        return schedules
        
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to initialize schedules: {e}")
        raise
    finally:
        session.close()


def test_relationships():
    """Test foreign key relationships"""
    session = next(get_db_session())
    try:
        # Test JobBoard -> ScheduleConfig relationship
        job_boards_with_schedules = session.query(JobBoard).join(ScheduleConfig).all()
        logger.info(f"Found {len(job_boards_with_schedules)} job boards with schedules")
        
        # Test ScheduleConfig -> JobBoard relationship
        for schedule in session.query(ScheduleConfig).all():
            assert schedule.job_board is not None, f"Schedule {schedule.id} has no job board"
            logger.info(f"Schedule '{schedule.name}' linked to job board '{schedule.job_board.name}'")
        
        logger.info("All relationship tests passed")
        
    except Exception as e:
        logger.error(f"Relationship test failed: {e}")
        raise
    finally:
        session.close()


def main():
    """Main initialization function"""
    logger.info("Starting database initialization...")
    
    try:
        # Initialize components
        engine_state = init_engine_state()
        job_boards = init_sample_job_boards()
        schedules = init_sample_schedules()
        
        # Test relationships
        test_relationships()
        
        logger.info("Database initialization completed successfully")
        
        # Print summary
        session = next(get_db_session())
        try:
            engine_count = session.query(EngineState).count()
            job_board_count = session.query(JobBoard).count()
            schedule_count = session.query(ScheduleConfig).count()
            scrape_job_count = session.query(ScrapeJob).count()
            
            print("\n=== Database Summary ===")
            print(f"Engine States: {engine_count}")
            print(f"Job Boards: {job_board_count}")
            print(f"Schedule Configs: {schedule_count}")
            print(f"Scrape Jobs: {scrape_job_count}")
            print("========================\n")
            
        finally:
            session.close()
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()