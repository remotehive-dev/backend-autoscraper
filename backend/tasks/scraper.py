from celery import current_app as celery_app
from backend.database.database import get_database_manager
from backend.database.services import JobPostService
# from backend.database.models import ScraperConfig, ScraperLog, JobPost  # Using MongoDB models instead
from backend.models.mongodb_models import JobPost
from backend.database.mongodb_models import ScraperConfig, ScraperLog
from backend.performance import performance_tracker, PerformanceContext, MetricType
from backend.scraper.engine import WebScrapingEngine, ScrapingConfig
from backend.scraper.parsers import ParsedJobPost
from backend.scraper.exceptions import ScrapingError, RateLimitError, NetworkError
from backend.tasks.playwright_scraper import playwright_scrape_jobs, batch_playwright_scrape
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any
# from sqlalchemy import and_, or_  # Using MongoDB instead
import requests
import json
import uuid
import time

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def run_scheduled_scrapers(self):
    """
    Run all scheduled scrapers based on their configuration
    
    This task is called by Celery Beat on a schedule and runs
    all active scraper configurations that are due for execution.
    """
    try:
        logger.info("Starting scheduled scraper run")
        
        db_manager = get_database_manager()
        with db_manager.session_scope() as db:
            # Get all active scraper configurations
            active_configs = db.query(ScraperConfig).filter(
                ScraperConfig.is_active == True,
                ScraperConfig.schedule_enabled == True
            ).all()
            
            if not active_configs:
                logger.info("No active scraper configurations found")
                return {
                    'success': True,
                    'message': 'No active scrapers to run',
                    'scrapers_run': 0
                }
            
            results = []
            scrapers_run = 0
            
            for config in active_configs:
                try:
                    # Check if scraper should run based on schedule
                    if should_run_scraper(config):
                        result = run_single_scraper.delay(config.id)
                        results.append({
                            'config_id': config.id,
                            'source': config.source,
                            'task_id': result.id,
                            'status': 'started'
                        })
                        scrapers_run += 1
                        logger.info(f"Started scraper for {config.source} (config_id: {config.id})")
                    else:
                        logger.debug(f"Skipping scraper {config.source} - not due for execution")
                        
                except Exception as e:
                    logger.error(f"Failed to start scraper for config {config.id}: {e}")
                    results.append({
                        'config_id': config.id,
                        'source': config.source,
                        'status': 'failed',
                        'error': str(e)
                    })
            
            logger.info(f"Scheduled scraper run completed. Started {scrapers_run} scrapers")
            
            return {
                'success': True,
                'scrapers_run': scrapers_run,
                'results': results,
                'timestamp': datetime.utcnow().isoformat()
            }
            
    except Exception as exc:
        logger.error(f"Scheduled scraper run failed: {exc}")
        raise self.retry(exc=exc, countdown=60, max_retries=3)

@celery_app.task(bind=True, max_retries=3)
def run_single_scraper(self, config_id: int):
    """
    Run a single scraper based on its configuration with enhanced performance tracking
    
    Args:
        config_id (int): ID of the scraper configuration to run
        
    Returns:
        dict: Scraping results and statistics with performance metrics
    """
    session_id = f"scraper_{config_id}_{uuid.uuid4().hex[:8]}"
    
    try:
        logger.info(f"Starting scraper for config_id: {config_id}, session: {session_id}")
        
        db_manager = get_database_manager()
        with db_manager.session_scope() as db:
            config = db.query(ScraperConfig).get(config_id)
            if not config:
                raise ValueError(f"Scraper config {config_id} not found")
            
            if not config.is_active:
                raise ValueError(f"Scraper config {config_id} is not active")
            
            # Create scraper log entry
            scraper_log = ScraperLog(
                source=config.source,
                status='running',
                started_at=datetime.utcnow(),
                metadata={
                    'config_id': config_id,
                    'search_query': config.search_query,
                    'location': config.location,
                    'max_pages': config.max_pages,
                    'session_id': session_id
                }
            )
            db.add(scraper_log)
            db.commit()
            
            log_id = scraper_log.id
        
        # Run the actual scraping logic with performance tracking
        try:
            with PerformanceContext(session_id, config_id, config.source) as perf_session:
                # Record initial metrics
                perf_session.add_metric("scraper_started", 1, MetricType.COUNTER)
                perf_session.add_metric("max_pages_configured", config.max_pages or 1, MetricType.GAUGE)
                
                result = execute_scraper(config, session_id)
                
                # Record completion metrics
                perf_session.add_metric("jobs_found", result.get('jobs_found', 0), MetricType.COUNTER)
                perf_session.add_metric("jobs_created", result.get('jobs_created', 0), MetricType.COUNTER)
                perf_session.add_metric("scraper_completed", 1, MetricType.COUNTER)
            
            # Get performance summary
            perf_summary = performance_tracker.end_session(session_id)
            
            # Update log with results and performance data
            db_manager = get_database_manager()
            with db_manager.session_scope() as db:
                log_entry = db.query(ScraperLog).get(log_id)
                if log_entry:
                    log_entry.status = 'completed'
                    log_entry.completed_at = datetime.utcnow()
                    log_entry.jobs_found = result.get('jobs_found', 0)
                    log_entry.jobs_created = result.get('jobs_created', 0)
                    log_entry.metadata.update(result.get('metadata', {}))
                    if perf_summary:
                        log_entry.metadata['performance_summary'] = perf_summary
                    db.commit()
            
            logger.info(f"Scraper completed for config_id: {config_id}. "
                       f"Found {result.get('jobs_found', 0)} jobs, "
                       f"Duration: {perf_summary.get('duration_ms', 0):.2f}ms")
            
            return {
                'success': True,
                'config_id': config_id,
                'source': config.source,
                'jobs_found': result.get('jobs_found', 0),
                'jobs_created': result.get('jobs_created', 0),
                'log_id': log_id,
                'session_id': session_id,
                'performance_summary': perf_summary
            }
            
        except Exception as e:
            # Record error in performance tracking
            performance_tracker.record_error(session_id, str(e))
            perf_summary = performance_tracker.end_session(session_id)
            
            # Update log with error
            db_manager = get_database_manager()
            with db_manager.session_scope() as db:
                log_entry = db.query(ScraperLog).get(log_id)
                if log_entry:
                    log_entry.status = 'failed'
                    log_entry.completed_at = datetime.utcnow()
                    log_entry.error_message = str(e)
                    if perf_summary:
                        log_entry.metadata['performance_summary'] = perf_summary
                    db.commit()
            
            raise e
            
    except Exception as exc:
        logger.error(f"Scraper failed for config_id {config_id}: {exc}")
        raise self.retry(exc=exc, countdown=300, max_retries=3)

def should_run_scraper(config: ScraperConfig) -> bool:
    """
    Determine if a scraper should run based on its schedule
    
    Args:
        config (ScraperConfig): Scraper configuration
        
    Returns:
        bool: True if scraper should run, False otherwise
    """
    if not config.schedule_enabled:
        return False
    
    # Get the last successful run from logs
    db_manager = get_database_manager()
    with db_manager.session_scope() as db:
        last_run = db.query(ScraperLog).filter(
            ScraperLog.source == config.source,
            ScraperLog.status == 'completed'
        ).order_by(ScraperLog.completed_at.desc()).first()
    
    if not last_run:
        # Never run before, should run now
        return True
    
    # Check if enough time has passed based on schedule interval
    time_since_last_run = datetime.utcnow() - last_run.completed_at
    interval_minutes = config.schedule_interval_minutes or 60
    
    return time_since_last_run >= timedelta(minutes=interval_minutes)

def execute_scraper(config: ScraperConfig, session_id: str = None) -> Dict[str, Any]:
    """
    Execute the actual scraping logic for a configuration
    
    This function integrates with the real scraping engine and includes
    performance tracking capabilities for production use.
    
    Args:
        config (ScraperConfig): Scraper configuration
        
    Returns:
        dict: Scraping results with performance metrics
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting scraper execution for {config.source}")
    
    # Enhanced performance tracking
    if session_id:
        performance_tracker.record_metric(
            session_id, "scraper_execution_started", 1, MetricType.COUNTER
        )
        performance_tracker.record_metric(
            session_id, "config_max_pages", config.max_pages or 1, MetricType.GAUGE
        )
    
    # Performance tracking variables
    performance_metrics = {
        'start_time': start_time.isoformat(),
        'pages_processed': 0,
        'requests_made': 0,
        'errors_encountered': 0,
        'rate_limit_hits': 0,
        'processing_time_ms': 0,
        'session_id': session_id
    }
    
    try:
        # Create scraping configuration
        scraping_config = ScrapingConfig(
            source=config.source,
            base_url=getattr(config, 'base_url', ''),
            max_pages=config.max_pages or 5,
            rate_limit_delay=getattr(config, 'rate_limit_delay', 1.0),
            request_timeout=getattr(config, 'request_timeout', 30.0),
            max_retries=getattr(config, 'max_retries', 3),
            headers=getattr(config, 'custom_headers', {}),
            parsing_rules=getattr(config, 'parsing_rules', {}),
            search_query=config.search_query,
            location=config.location,
            job_type=getattr(config, 'job_type', None),
            remote_only=getattr(config, 'remote_only', False)
        )
        
        # Initialize web scraping engine with performance tracking
        engine = WebScrapingEngine(scraping_config, session_id)
        
        # Record scraping start metrics
        if session_id:
            performance_tracker.record_metric(
                session_id, "scraping_engine_initialized", 1, MetricType.COUNTER
            )
        
        try:
            # Execute scraping
            scraping_session = engine.scrape_jobs(
                search_query=config.search_query,
                location=config.location,
                job_type=getattr(config, 'job_type', None)
            )
            
            jobs_found = scraping_session.jobs_found
            jobs_created = 0
            
            # Process and validate each job with performance tracking
            db_manager = get_database_manager()
            
            for i, parsed_job in enumerate(scraping_session.parsed_jobs):
                try:
                    job_start_time = time.time()
                    
                    if parsed_job.is_valid():
                        # Store job in database using JobPostService
                        with db_manager.session_scope() as job_db:
                            job_data = parsed_job.to_dict()
                            # Add required fields for job post creation
                            job_data.update({
                                'status': 'active',
                                'is_remote': 'remote' in job_data.get('location', '').lower(),
                                'job_type': job_data.get('employment_type', 'full-time'),
                                'work_location': 'remote' if 'remote' in job_data.get('location', '').lower() else 'onsite'
                            })
                            
                            # Use static method from JobPostService
                            job_post = JobPostService.create_job_post(job_db, None, job_data)
                            jobs_created += 1
                            
                            logger.debug(f"Created job post {job_post.id}: {job_data.get('title', 'Unknown')}")
                        
                        # Record job processing metrics
                        if session_id:
                            job_processing_time = (time.time() - job_start_time) * 1000
                            performance_tracker.record_metric(
                                session_id, "job_processing_time", job_processing_time, 
                                MetricType.TIMER, unit="ms"
                            )
                            performance_tracker.record_metric(
                                session_id, "job_created", 1, MetricType.COUNTER
                            )
                    else:
                        if session_id:
                            performance_tracker.record_metric(
                                session_id, "job_validation_failed", 1, MetricType.COUNTER
                            )
                            
                except Exception as parse_error:
                    logger.warning(f"Failed to process job {i+1}: {parse_error}")
                    performance_metrics['errors_encountered'] += 1
                    if session_id:
                        performance_tracker.record_error(session_id, f"Job processing error: {parse_error}")
                        performance_tracker.record_metric(
                            session_id, "job_processing_error", 1, MetricType.COUNTER
                        )
            
            # Update performance metrics from scraping result
            performance_metrics.update({
                'pages_processed': scraping_session.pages_scraped,
                'requests_made': getattr(scraping_session, 'requests_made', 0),
                'rate_limit_hits': getattr(scraping_session, 'rate_limit_hits', 0)
            })
            
            # Record final scraping metrics
            if session_id:
                performance_tracker.record_metric(
                    session_id, "pages_processed", scraping_session.pages_scraped, MetricType.COUNTER
                )
                performance_tracker.record_metric(
                    session_id, "jobs_found", scraping_session.jobs_found, MetricType.COUNTER
                )
                performance_tracker.record_metric(
                    session_id, "jobs_valid", scraping_session.jobs_valid, MetricType.COUNTER
                )
                performance_tracker.record_metric(
                    session_id, "scraping_errors", len(scraping_session.errors), MetricType.COUNTER
                )
            
            # Clean up engine resources
            engine.close()
            
        except (ScrapingError, RateLimitError, NetworkError) as scraping_error:
            logger.error(f"Scraping engine error: {scraping_error}")
            performance_metrics['errors_encountered'] += 1
            if session_id:
                performance_tracker.record_error(session_id, f"Scraping engine error: {scraping_error}")
            
            # Set fallback values
            jobs_found = 0
            jobs_created = 0
            
            # Clean up engine resources
            try:
                engine.close()
            except:
                pass
        
        # Calculate execution time and record final metrics
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds() * 1000
        performance_metrics['processing_time_ms'] = execution_time
        performance_metrics['end_time'] = end_time.isoformat()
        
        # Record final performance metrics
        if session_id:
            performance_tracker.record_metric(
                session_id, "total_execution_time", execution_time, MetricType.TIMER, unit="ms"
            )
            performance_tracker.record_metric(
                session_id, "scraper_execution_completed", 1, MetricType.COUNTER
            )
        
        logger.info(f"Scraper execution completed for {config.source}. "
                   f"Found: {jobs_found}, Created: {jobs_created}, "
                   f"Time: {execution_time:.2f}ms")
        
        return {
            'jobs_found': jobs_found,
            'jobs_created': jobs_created,
            'performance_metrics': performance_metrics,
            'metadata': {
                'config_id': config.id,
                'source': config.source,
                'scraper_version': '2.0.0',
                'status': 'ready_for_integration',
                'execution_summary': {
                    'total_time_ms': execution_time,
                    'success_rate': 100.0 if performance_metrics['errors_encountered'] == 0 else 
                                  (1 - performance_metrics['errors_encountered'] / max(1, performance_metrics['requests_made'])) * 100,
                    'avg_request_time': execution_time / max(1, performance_metrics['requests_made'])
                }
            }
        }
        
    except Exception as e:
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds() * 1000
        performance_metrics['processing_time_ms'] = execution_time
        performance_metrics['end_time'] = end_time.isoformat()
        performance_metrics['errors_encountered'] += 1
        
        # Record error metrics
        if session_id:
            performance_tracker.record_metric(
                session_id, "scraper_execution_failed", 1, MetricType.COUNTER
            )
            performance_tracker.record_metric(
                session_id, "total_execution_time", execution_time, MetricType.TIMER, unit="ms"
            )
            performance_tracker.record_error(session_id, f"Scraper execution error: {e}")
        
        logger.error(f"Scraper execution failed for {config.source}: {e}. "
                    f"Execution time: {execution_time:.2f}ms")
        
        # Return error details with performance metrics for debugging
        return {
            'jobs_found': 0,
            'jobs_created': 0,
            'performance_metrics': performance_metrics,
            'metadata': {
                'config_id': config.id,
                'source': config.source,
                'scraper_version': '2.0.0',
                'status': 'failed',
                'error': str(e),
                'execution_summary': {
                    'total_time_ms': execution_time,
                    'success_rate': 0.0,
                    'error_details': str(e)
                }
            }
        }

@celery_app.task
def test_scraper_connection():
    """
    Test task to verify scraper system is working
    """
    logger.info("Testing scraper connection")
    
    try:
        db_manager = get_database_manager()
        with db_manager.session_scope() as db:
            config_count = db.query(ScraperConfig).count()
            
        return {
            'success': True,
            'message': 'Scraper system is operational',
            'config_count': config_count,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Scraper connection test failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }