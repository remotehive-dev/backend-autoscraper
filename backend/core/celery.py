from celery import Celery
from celery.signals import task_failure, task_retry, task_success
from backend.core.config import settings
from backend.core.logging import get_logger
import logging

logger = get_logger(__name__)

# Create Celery instance with proper broker and backend URLs
celery_app = Celery(
    "remotehive",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["backend.tasks", "backend.autoscraper.tasks", "backend.tasks.monitoring"]
)

# Enhanced Celery configuration with monitoring and retry mechanisms
celery_app.conf.update(
    # Serialization
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    accept_content=settings.CELERY_ACCEPT_CONTENT,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    
    # Timezone
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=settings.CELERY_ENABLE_UTC,
    
    # Task tracking and monitoring
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_send_sent_event=True,
    task_store_eager_result=True,
    result_expires=3600,  # Results expire after 1 hour
    
    # Task limits and timeouts
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    
    # Worker configuration
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
    worker_disable_rate_limits=False,
    worker_send_task_events=True,
    
    # Task retry configuration
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    
    # Queue configuration with priority and dead letter support
    task_routes={
        # Main application tasks
        'backend.tasks.scraper.run_scheduled_scrapers': {'queue': 'default', 'priority': 5},
        'backend.tasks.jobs.cleanup_expired_jobs': {'queue': 'maintenance', 'priority': 3},
        'backend.tasks.email.*': {'queue': 'email', 'priority': 7},
        
        # AutoScraper tasks
        'backend.autoscraper.tasks.run_scrape_job': {'queue': 'autoscraper.default', 'priority': 6},
        'backend.autoscraper.tasks.fetch_rss_entries': {'queue': 'autoscraper.default', 'priority': 5},
        'backend.autoscraper.tasks.html_scrape': {'queue': 'autoscraper.heavy', 'priority': 4},
        'backend.autoscraper.tasks.persist_raw_item': {'queue': 'autoscraper.default', 'priority': 6},
        'backend.autoscraper.tasks.normalize_raw_job': {'queue': 'autoscraper.default', 'priority': 5},
        'backend.autoscraper.tasks.heartbeat': {'queue': 'monitoring', 'priority': 8},
    },
    
    task_default_queue='default',
    task_default_exchange='remotehive',
    task_default_exchange_type='topic',
    task_default_routing_key='default',
    
    # Enhanced queue configuration with dead letter queues
    task_queues={
        # Main queues
        'default': {
            'exchange': 'remotehive',
            'exchange_type': 'topic',
            'routing_key': 'default',
            'queue_arguments': {
                'x-max-priority': 10,
                'x-message-ttl': 3600000,  # 1 hour TTL
                'x-dead-letter-exchange': 'remotehive.dlx',
                'x-dead-letter-routing-key': 'failed.default'
            }
        },
        'email': {
            'exchange': 'remotehive',
            'exchange_type': 'topic',
            'routing_key': 'email',
            'queue_arguments': {
                'x-max-priority': 10,
                'x-message-ttl': 1800000,  # 30 minutes TTL
                'x-dead-letter-exchange': 'remotehive.dlx',
                'x-dead-letter-routing-key': 'failed.email'
            }
        },
        'maintenance': {
            'exchange': 'remotehive',
            'exchange_type': 'topic',
            'routing_key': 'maintenance',
            'queue_arguments': {
                'x-max-priority': 10,
                'x-message-ttl': 7200000,  # 2 hours TTL
                'x-dead-letter-exchange': 'remotehive.dlx',
                'x-dead-letter-routing-key': 'failed.maintenance'
            }
        },
        'monitoring': {
            'exchange': 'remotehive',
            'exchange_type': 'topic',
            'routing_key': 'monitoring',
            'queue_arguments': {
                'x-max-priority': 10,
                'x-message-ttl': 300000,  # 5 minutes TTL
                'x-dead-letter-exchange': 'remotehive.dlx',
                'x-dead-letter-routing-key': 'failed.monitoring'
            }
        },
        
        # AutoScraper queues
        'autoscraper.default': {
            'exchange': 'autoscraper',
            'exchange_type': 'topic',
            'routing_key': 'autoscraper.default',
            'queue_arguments': {
                'x-max-priority': 10,
                'x-message-ttl': 3600000,  # 1 hour TTL
                'x-dead-letter-exchange': 'autoscraper.dlx',
                'x-dead-letter-routing-key': 'failed.default'
            }
        },
        'autoscraper.heavy': {
            'exchange': 'autoscraper',
            'exchange_type': 'topic',
            'routing_key': 'autoscraper.heavy',
            'queue_arguments': {
                'x-max-priority': 10,
                'x-message-ttl': 7200000,  # 2 hours TTL for heavy tasks
                'x-dead-letter-exchange': 'autoscraper.dlx',
                'x-dead-letter-routing-key': 'failed.heavy'
            }
        },
        
        # Dead letter queues
        'remotehive.failed': {
            'exchange': 'remotehive.dlx',
            'exchange_type': 'topic',
            'routing_key': 'failed.*',
        },
        'autoscraper.failed': {
            'exchange': 'autoscraper.dlx',
            'exchange_type': 'topic',
            'routing_key': 'failed.*',
        },
    },
)

# Periodic tasks with enhanced scheduling
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "run-job-scrapers": {
        "task": "backend.tasks.scraper.run_scheduled_scrapers",
        "schedule": crontab(minute='*/5'),  # Every 5 minutes
        "options": {"queue": "default", "priority": 5}
    },
    "cleanup-expired-jobs": {
        "task": "backend.tasks.jobs.cleanup_expired_jobs",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
        "options": {"queue": "maintenance", "priority": 3}
    },
    "autoscraper-heartbeat": {
        "task": "backend.autoscraper.tasks.heartbeat",
        "schedule": crontab(minute='*/1'),  # Every minute
        "options": {"queue": "monitoring", "priority": 8}
    },
    "task-health-check": {
        "task": "backend.tasks.monitoring.health_check",
        "schedule": crontab(minute='*/2'),  # Every 2 minutes
        "options": {"queue": "monitoring", "priority": 9}
    },
    "queue-metrics-collection": {
        "task": "backend.tasks.monitoring.collect_queue_metrics",
        "schedule": crontab(minute='*/10'),  # Every 10 minutes
        "options": {"queue": "monitoring", "priority": 7}
    },
}

# Task monitoring and error handling signals
from celery import signals
structured_logger = get_logger(__name__)

@signals.task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Log task start and setup monitoring."""
    try:
        structured_logger.info(
            "Task started",
            extra={
                "task_id": task_id,
                "task_name": task.name if task else sender,
                "args_count": len(args) if args else 0,
                "kwargs_keys": list(kwargs.keys()) if kwargs else [],
                "event_type": "task_start"
            }
        )
    except Exception as e:
        logging.error(f"Error in task_prerun_handler: {e}")

@signals.task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Log task completion and collect metrics."""
    try:
        structured_logger.info(
            "Task completed",
            extra={
                "task_id": task_id,
                "task_name": task.name if task else sender,
                "state": state,
                "has_retval": retval is not None,
                "event_type": "task_complete"
            }
        )
    except Exception as e:
        logging.error(f"Error in task_postrun_handler: {e}")

@signals.task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, traceback=None, einfo=None, **kwds):
    """Log task retries and track retry patterns."""
    try:
        structured_logger.warning(
            "Task retry",
            extra={
                "task_id": task_id,
                "task_name": sender.name if sender else "unknown",
                "reason": str(reason),
                "retry_count": getattr(sender, 'request', {}).get('retries', 0),
                "event_type": "task_retry"
            }
        )
    except Exception as e:
        logging.error(f"Error in task_retry_handler: {e}")

@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Log task failures and send alerts for critical tasks."""
    try:
        structured_logger.error(
            "Task failed",
            extra={
                "task_id": task_id,
                "task_name": sender.name if sender else "unknown",
                "exception_type": type(exception).__name__ if exception else "unknown",
                "exception_message": str(exception) if exception else "unknown",
                "retry_count": getattr(sender, 'request', {}).get('retries', 0),
                "event_type": "task_failure"
            }
        )
        
        # Send alerts for critical task failures
        if sender and hasattr(sender, 'name'):
            critical_tasks = [
                'app.tasks.scraper.run_scheduled_scrapers',
                'app.autoscraper.tasks.heartbeat',
                'app.tasks.monitoring.health_check'
            ]
            if sender.name in critical_tasks:
                # TODO: Implement alert mechanism (email, Slack, etc.)
                structured_logger.critical(
                    "Critical task failure - alert required",
                    extra={
                        "task_id": task_id,
                        "task_name": sender.name,
                        "exception": str(exception),
                        "event_type": "critical_failure"
                    }
                )
    except Exception as e:
        logging.error(f"Error in task_failure_handler: {e}")

@signals.worker_ready.connect
def worker_ready_handler(sender=None, **kwds):
    """Log worker startup and initialize database manager."""
    try:
        # Initialize database manager for worker processes
        from backend.database.database import get_database_manager
        import asyncio
        
        db_manager = get_database_manager()
        
        # Initialize database manager in worker process
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(db_manager.initialize())
            structured_logger.info("Database manager initialized in worker process")
        except Exception as db_error:
            structured_logger.error(f"Failed to initialize database manager in worker: {db_error}")
        finally:
            loop.close()
        
        structured_logger.info(
            "Celery worker ready",
            extra={
                "worker_hostname": sender.hostname if sender else "unknown",
                "event_type": "worker_ready"
            }
        )
    except Exception as e:
        logging.error(f"Error in worker_ready_handler: {e}")

@signals.worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwds):
    """Log worker shutdown."""
    try:
        structured_logger.info(
            "Celery worker shutdown",
            extra={
                "worker_hostname": sender.hostname if sender else "unknown",
                "event_type": "worker_shutdown"
            }
        )
    except Exception as e:
        logging.error(f"Error in worker_shutdown_handler: {e}")

if __name__ == "__main__":
    celery_app.start()