"""Enhanced Celery tasks for Playwright-based web scraping"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from celery import Task
from celery.exceptions import Retry, WorkerLostError

from backend.core.celery import celery_app
from backend.core.enums import ScraperSource, ScraperStatus
from backend.scraper.playwright_engine import PlaywrightScrapingEngine, PlaywrightConfig
from backend.scraper.exceptions import (
    ScrapingError, RateLimitError, CaptchaError, TimeoutError,
    NetworkError, BrowserError, SessionError
)
from backend.models.jobs import JobPost, ScrapingSession
from backend.models.tasks import TaskResult
from backend.database.database import get_db_session
from backend.core.monitoring import app_monitor
from backend.performance.tracker import PerformanceTracker
from backend.utils.notifications import NotificationService

logger = logging.getLogger(__name__)

class PlaywrightScrapingTask(Task):
    """Base class for Playwright scraping tasks with enhanced error handling"""
    
    autoretry_for = (
        RateLimitError,
        NetworkError,
        TimeoutError,
        BrowserError,
        ConnectionError,
        WorkerLostError
    )
    
    retry_kwargs = {
        'max_retries': 3,
        'default_retry_delay': 60,
        'retry_backoff': True,
        'retry_backoff_max': 600,
        'retry_jitter': True
    }
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"Playwright scraping task {task_id} failed: {exc}")
        
        # Record failure metrics
        app_monitor.record_task_failure(task_id, str(exc))
        
        # Update task status in database
        try:
            with get_db_session() as db:
                task_result = db.query(TaskResult).filter(
                    TaskResult.task_id == task_id
                ).first()
                
                if task_result:
                    task_result.status = ScraperStatus.FAILED
                    task_result.error_message = str(exc)
                    task_result.completed_at = datetime.utcnow()
                    db.commit()
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f"Playwright scraping task {task_id} completed successfully")
        
        # Record success metrics
        app_monitor.record_task_success(task_id)
        
        # Update task status in database
        try:
            with get_db_session() as db:
                task_result = db.query(TaskResult).filter(
                    TaskResult.task_id == task_id
                ).first()
                
                if task_result:
                    task_result.status = ScraperStatus.COMPLETED
                    task_result.result = retval
                    task_result.completed_at = datetime.utcnow()
                    db.commit()
        except Exception as e:
            logger.error(f"Failed to update task status: {e}")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry"""
        logger.warning(f"Retrying Playwright scraping task {task_id}: {exc}")
        
        # Record retry metrics
        app_monitor.record_task_retry(task_id, str(exc))

@celery_app.task(bind=True, base=PlaywrightScrapingTask, name='scraper.playwright_scrape_jobs')
def playwright_scrape_jobs(self, source: str, urls: List[str], 
                          config: Dict[str, Any] = None,
                          session_id: str = None) -> Dict[str, Any]:
    """Scrape job listings using Playwright engine"""
    task_id = self.request.id
    performance_tracker = PerformanceTracker(task_id)
    
    try:
        # Record task start
        with get_db_session() as db:
            task_result = TaskResult(
                task_id=task_id,
                task_name='playwright_scrape_jobs',
                status=ScraperStatus.RUNNING,
                started_at=datetime.utcnow(),
                parameters={
                    'source': source,
                    'urls': urls,
                    'config': config,
                    'session_id': session_id
                }
            )
            db.add(task_result)
            db.commit()
        
        # Parse source enum
        try:
            scraper_source = ScraperSource(source.upper())
        except ValueError:
            raise ValueError(f"Invalid scraper source: {source}")
        
        # Create Playwright configuration
        playwright_config = PlaywrightConfig(**(config or {}))
        
        # Run scraping in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _run_playwright_scraping(
                    scraper_source, urls, playwright_config, 
                    session_id, performance_tracker
                )
            )
        finally:
            loop.close()
        
        # Store results in database
        jobs_stored = _store_scraped_jobs(result['jobs'], session_id)
        
        # Update session statistics
        if session_id:
            _update_scraping_session(session_id, result, jobs_stored)
        
        # Send notifications if configured
        _send_scraping_notifications(result, scraper_source)
        
        return {
            'task_id': task_id,
            'session_id': session_id,
            'source': source,
            'jobs_found': len(result['jobs']),
            'jobs_stored': jobs_stored,
            'pages_scraped': result['stats']['pages_scraped'],
            'errors': result['stats']['errors'],
            'duplicates_filtered': result['stats']['duplicates_filtered'],
            'performance_metrics': performance_tracker.get_summary(),
            'completed_at': datetime.utcnow().isoformat()
        }
        
    except CaptchaError as e:
        logger.warning(f"CAPTCHA detected during scraping: {e}")
        # Don't retry immediately for CAPTCHA errors
        raise self.retry(countdown=300, exc=e)
        
    except RateLimitError as e:
        logger.warning(f"Rate limit hit during scraping: {e}")
        # Retry with exponential backoff
        countdown = min(600, 60 * (2 ** self.request.retries))
        raise self.retry(countdown=countdown, exc=e)
        
    except (NetworkError, TimeoutError, BrowserError) as e:
        logger.error(f"Technical error during scraping: {e}")
        # Retry with standard backoff
        raise self.retry(exc=e)
        
    except Exception as e:
        logger.error(f"Unexpected error in Playwright scraping task: {e}")
        performance_tracker.record_error(str(e))
        raise

async def _run_playwright_scraping(source: ScraperSource, urls: List[str],
                                  config: PlaywrightConfig, session_id: str,
                                  performance_tracker: PerformanceTracker) -> Dict[str, Any]:
    """Run the actual Playwright scraping operation"""
    
    async with PlaywrightScrapingEngine(config, performance_tracker.session_id) as engine:
        try:
            # Start performance tracking
            performance_tracker.start_operation('scraping')
            
            # Scrape job listings
            jobs = await engine.scrape_job_listings(urls, source)
            
            # End performance tracking
            performance_tracker.end_operation('scraping')
            
            # Get engine statistics
            stats = engine.get_stats()
            
            return {
                'jobs': [job.to_dict() for job in jobs],
                'stats': stats,
                'performance': performance_tracker.get_summary()
            }
            
        except Exception as e:
            performance_tracker.record_error(str(e))
            raise

def _store_scraped_jobs(jobs_data: List[Dict[str, Any]], session_id: str = None) -> int:
    """Store scraped jobs in the database"""
    stored_count = 0
    
    try:
        with get_db_session() as db:
            for job_data in jobs_data:
                try:
                    # Check for existing job to avoid duplicates
                    existing_job = db.query(JobPost).filter(
                        JobPost.title == job_data.get('title'),
                        JobPost.company == job_data.get('company'),
                        JobPost.source_url == job_data.get('source_url')
                    ).first()
                    
                    if existing_job:
                        logger.debug(f"Job already exists: {job_data.get('title')} at {job_data.get('company')}")
                        continue
                    
                    # Create new job post
                    job_post = JobPost(
                        title=job_data.get('title'),
                        company=job_data.get('company'),
                        location=job_data.get('location'),
                        description=job_data.get('description'),
                        requirements=job_data.get('requirements'),
                        salary_min=job_data.get('salary_min'),
                        salary_max=job_data.get('salary_max'),
                        salary_currency=job_data.get('salary_currency'),
                        job_type=job_data.get('job_type'),
                        experience_level=job_data.get('experience_level'),
                        posted_date=job_data.get('posted_date'),
                        application_url=job_data.get('application_url'),
                        company_url=job_data.get('company_url'),
                        remote_friendly=job_data.get('remote_friendly', False),
                        benefits=job_data.get('benefits', []),
                        skills=job_data.get('skills', []),
                        tags=job_data.get('tags', []),
                        source_url=job_data.get('source_url'),
                        source_platform=job_data.get('source_platform'),
                        confidence_score=job_data.get('confidence_score', 0.0),
                        raw_data=job_data.get('raw_data', {}),
                        scraping_session_id=session_id,
                        created_at=datetime.utcnow()
                    )
                    
                    db.add(job_post)
                    stored_count += 1
                    
                except Exception as e:
                    logger.error(f"Error storing job: {e}")
                    continue
            
            db.commit()
            logger.info(f"Stored {stored_count} new jobs in database")
            
    except Exception as e:
        logger.error(f"Error storing scraped jobs: {e}")
    
    return stored_count

def _update_scraping_session(session_id: str, result: Dict[str, Any], jobs_stored: int):
    """Update scraping session with results"""
    try:
        with get_db_session() as db:
            session = db.query(ScrapingSession).filter(
                ScrapingSession.session_id == session_id
            ).first()
            
            if session:
                session.jobs_found = len(result['jobs'])
                session.jobs_stored = jobs_stored
                session.pages_scraped = result['stats']['pages_scraped']
                session.errors = result['stats']['errors']
                session.duplicates_filtered = result['stats']['duplicates_filtered']
                session.performance_metrics = result['performance']
                session.completed_at = datetime.utcnow()
                session.success = result['stats']['errors'] == 0
                
                db.commit()
                logger.info(f"Updated scraping session {session_id}")
                
    except Exception as e:
        logger.error(f"Error updating scraping session: {e}")

def _send_scraping_notifications(result: Dict[str, Any], source: ScraperSource):
    """Send notifications about scraping results"""
    try:
        notification_service = NotificationService()
        
        # Send success notification
        if result['stats']['errors'] == 0:
            notification_service.send_scraping_success(
                source=source.value,
                jobs_found=len(result['jobs']),
                pages_scraped=result['stats']['pages_scraped']
            )
        else:
            # Send warning notification for errors
            notification_service.send_scraping_warning(
                source=source.value,
                jobs_found=len(result['jobs']),
                errors=result['stats']['errors'],
                captchas=result['stats'].get('captchas_detected', 0)
            )
            
    except Exception as e:
        logger.error(f"Error sending scraping notifications: {e}")

@celery_app.task(bind=True, base=PlaywrightScrapingTask, name='scraper.batch_playwright_scrape')
def batch_playwright_scrape(self, scraping_configs: List[Dict[str, Any]],
                           session_id: str = None) -> Dict[str, Any]:
    """Run multiple Playwright scraping operations in batch"""
    task_id = self.request.id
    results = []
    total_jobs = 0
    total_errors = 0
    
    try:
        for i, config in enumerate(scraping_configs):
            try:
                logger.info(f"Running batch scraping {i+1}/{len(scraping_configs)}")
                
                # Run individual scraping task
                result = playwright_scrape_jobs.apply(
                    args=[
                        config['source'],
                        config['urls'],
                        config.get('config', {}),
                        f"{session_id}_{i}" if session_id else None
                    ]
                ).get()
                
                results.append(result)
                total_jobs += result['jobs_found']
                total_errors += result['errors']
                
                # Add delay between batch operations
                if i < len(scraping_configs) - 1:
                    import time
                    time.sleep(30)  # 30 second delay between batches
                    
            except Exception as e:
                logger.error(f"Error in batch scraping operation {i+1}: {e}")
                total_errors += 1
                results.append({
                    'error': str(e),
                    'config': config
                })
        
        return {
            'task_id': task_id,
            'session_id': session_id,
            'batch_size': len(scraping_configs),
            'total_jobs_found': total_jobs,
            'total_errors': total_errors,
            'results': results,
            'completed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in batch Playwright scraping: {e}")
        raise

@celery_app.task(bind=True, name='scraper.cleanup_old_sessions')
def cleanup_old_sessions(self, days_old: int = 7) -> Dict[str, Any]:
    """Clean up old scraping sessions and associated data"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        with get_db_session() as db:
            # Delete old scraping sessions
            old_sessions = db.query(ScrapingSession).filter(
                ScrapingSession.created_at < cutoff_date
            ).all()
            
            sessions_deleted = len(old_sessions)
            
            for session in old_sessions:
                db.delete(session)
            
            # Delete old task results
            old_tasks = db.query(TaskResult).filter(
                TaskResult.started_at < cutoff_date,
                TaskResult.task_name.in_([
                    'playwright_scrape_jobs',
                    'batch_playwright_scrape'
                ])
            ).all()
            
            tasks_deleted = len(old_tasks)
            
            for task in old_tasks:
                db.delete(task)
            
            db.commit()
            
        logger.info(f"Cleaned up {sessions_deleted} old sessions and {tasks_deleted} old tasks")
        
        return {
            'sessions_deleted': sessions_deleted,
            'tasks_deleted': tasks_deleted,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up old sessions: {e}")
        raise

@celery_app.task(bind=True, name='scraper.health_check_playwright')
def health_check_playwright(self) -> Dict[str, Any]:
    """Health check for Playwright scraping system"""
    try:
        # Test Playwright initialization
        config = PlaywrightConfig(headless=True, timeout=10000)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            async def test_playwright():
                async with PlaywrightScrapingEngine(config) as engine:
                    # Simple test navigation
                    await engine.page.goto('https://httpbin.org/get')
                    content = await engine.page.content()
                    return len(content) > 0
            
            success = loop.run_until_complete(test_playwright())
        finally:
            loop.close()
        
        return {
            'status': 'healthy' if success else 'unhealthy',
            'playwright_available': success,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Playwright health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }