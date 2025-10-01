#!/usr/bin/env python3
"""
Test Scrape Job Creation
Tests creating scrape jobs and runs to verify complete ORM integration
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
    JobBoard, ScheduleConfig, ScrapeJob, ScrapeRun, RawJob, NormalizedJob,
    ScrapeJobMode, ScrapeJobStatus, EngineState
)
from loguru import logger


def create_test_scrape_job():
    """Create a test scrape job with complete workflow"""
    session = next(get_db_session())
    try:
        # Get a job board and schedule
        job_board = session.query(JobBoard).filter_by(name="Indeed").first()
        schedule = session.query(ScheduleConfig).filter_by(job_board_id=job_board.id).first()
        
        if not job_board or not schedule:
            logger.error("Required job board or schedule not found")
            return None
        
        # Create scrape job
        scrape_job = ScrapeJob(
            id=uuid.uuid4(),
            job_board_id=job_board.id,
            schedule_config_id=schedule.id,
            mode=ScrapeJobMode.SCHEDULED,
            status=ScrapeJobStatus.PENDING,
            priority=1,
            max_pages=5,
            config_snapshot={
                "selectors": job_board.selectors,
                "rate_limit_delay": job_board.rate_limit_delay,
                "max_pages": 5
            }
        )
        
        session.add(scrape_job)
        session.commit()
        logger.info(f"Created scrape job: {scrape_job.id}")
        
        # Create scrape run
        scrape_run = ScrapeRun(
            id=uuid.uuid4(),
            scrape_job_id=scrape_job.id,
            run_type="html",
            url="https://indeed.com/jobs?q=python+developer",
            page_number=1,
            started_at=datetime.now(timezone.utc),
            items_found=0,
            items_processed=0
        )
        
        session.add(scrape_run)
        session.commit()
        logger.info(f"Created scrape run: {scrape_run.id}")
        
        # Create sample raw job
        raw_job = RawJob(
            id=uuid.uuid4(),
            scrape_run_id=scrape_run.id,
            title="Senior Python Developer",
            company="Tech Corp",
            location="Remote",
            description="We are looking for a senior Python developer...",
            url="https://indeed.com/viewjob?jk=test123",
            salary="$120,000 - $150,000",
            job_type="full-time",
            posted_date="2025-01-20",
            raw_data={
                "title": "Senior Python Developer",
                "company": "Tech Corp",
                "location": "Remote",
                "description": "We are looking for a senior Python developer...",
                "salary": "$120,000 - $150,000",
                "posted_date": "2025-01-20"
            },
            is_processed=False,
            is_duplicate=False
        )
        
        session.add(raw_job)
        session.commit()
        logger.info(f"Created raw job: {raw_job.id}")
        
        # Create normalized job
        normalized_job = NormalizedJob(
            id=uuid.uuid4(),
            raw_job_id=raw_job.id,
            title="Senior Python Developer",
            company="Tech Corp",
            location="Remote",
            description="We are looking for a senior Python developer with 5+ years of experience...",
            url="https://indeed.com/viewjob?jk=test123",
            salary_min=120000,
            salary_max=150000,
            salary_currency="USD",
            salary_period="yearly",
            job_type="full-time",
            experience_level="senior",
            remote_allowed=True,
            posted_date=datetime(2025, 1, 20, tzinfo=timezone.utc),
            skills_required=["Python", "Django/Flask", "PostgreSQL", "AWS"],
            education_required="Bachelor's degree",
            normalization_confidence=0.92,
            normalization_method="rule_based",
            is_published=False
        )
        
        session.add(normalized_job)
        session.commit()
        logger.info(f"Created normalized job: {normalized_job.id}")
        
        # Update scrape run with results
        scrape_run.completed_at = datetime.now(timezone.utc)
        scrape_run.items_found = 1
        scrape_run.items_processed = 1
        scrape_run.items_created = 1
        scrape_run.duration_seconds = 30
        scrape_run.http_status_code = 200
        
        # Update scrape job
        scrape_job.status = ScrapeJobStatus.COMPLETED
        scrape_job.completed_at = datetime.now(timezone.utc)
        scrape_job.duration_seconds = 35
        scrape_job.items_processed = 1
        scrape_job.total_items_found = 1
        scrape_job.total_items_created = 1
        scrape_job.success_rate = 1.0
        
        session.commit()
        logger.info("Updated scrape job and run with completion status")
        
        return scrape_job
        
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create test scrape job: {e}")
        raise
    finally:
        session.close()


def test_relationships_complete():
    """Test all relationships in the complete workflow"""
    session = next(get_db_session())
    try:
        # Test ScrapeJob relationships
        scrape_jobs = session.query(ScrapeJob).all()
        for job in scrape_jobs:
            assert job.job_board is not None, f"ScrapeJob {job.id} has no job_board"
            assert job.schedule_config is not None, f"ScrapeJob {job.id} has no schedule_config"
            logger.info(f"ScrapeJob {job.id} -> JobBoard: {job.job_board.name}, Schedule: {job.schedule_config.name}")
        
        # Test ScrapeRun relationships
        scrape_runs = session.query(ScrapeRun).all()
        for run in scrape_runs:
            assert run.scrape_job is not None, f"ScrapeRun {run.id} has no scrape_job"
            logger.info(f"ScrapeRun {run.id} -> ScrapeJob: {run.scrape_job.id}")
        
        # Test RawJob relationships
        raw_jobs = session.query(RawJob).all()
        for raw_job in raw_jobs:
            assert raw_job.scrape_run is not None, f"RawJob {raw_job.id} has no scrape_run"
            logger.info(f"RawJob {raw_job.id} -> ScrapeRun: {raw_job.scrape_run.id}")
        
        # Test NormalizedJob relationships
        normalized_jobs = session.query(NormalizedJob).all()
        for norm_job in normalized_jobs:
            assert norm_job.raw_job is not None, f"NormalizedJob {norm_job.id} has no raw_job"
            logger.info(f"NormalizedJob {norm_job.id} -> RawJob: {norm_job.raw_job.id}")
        
        # Test reverse relationships
        for job_board in session.query(JobBoard).all():
            logger.info(f"JobBoard {job_board.name} has {len(job_board.scrape_jobs)} scrape jobs")
            logger.info(f"JobBoard {job_board.name} has {len(job_board.schedule_configs)} schedules")
        
        logger.info("All relationship tests passed successfully")
        
    except Exception as e:
        logger.error(f"Relationship test failed: {e}")
        raise
    finally:
        session.close()


def print_database_summary():
    """Print complete database summary"""
    session = next(get_db_session())
    try:
        engine_count = session.query(EngineState).count()
        job_board_count = session.query(JobBoard).count()
        schedule_count = session.query(ScheduleConfig).count()
        scrape_job_count = session.query(ScrapeJob).count()
        scrape_run_count = session.query(ScrapeRun).count()
        raw_job_count = session.query(RawJob).count()
        normalized_job_count = session.query(NormalizedJob).count()
        
        print("\n=== Complete Database Summary ===")
        print(f"Engine States: {engine_count}")
        print(f"Job Boards: {job_board_count}")
        print(f"Schedule Configs: {schedule_count}")
        print(f"Scrape Jobs: {scrape_job_count}")
        print(f"Scrape Runs: {scrape_run_count}")
        print(f"Raw Jobs: {raw_job_count}")
        print(f"Normalized Jobs: {normalized_job_count}")
        print("=================================\n")
        
    finally:
        session.close()


def main():
    """Main test function"""
    logger.info("Starting complete ORM integration test...")
    
    try:
        # Create test scrape job workflow
        scrape_job = create_test_scrape_job()
        
        # Test all relationships
        test_relationships_complete()
        
        # Print summary
        print_database_summary()
        
        logger.info("Complete ORM integration test passed successfully")
        
    except Exception as e:
        logger.error(f"ORM integration test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()