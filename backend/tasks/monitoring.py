"""Celery monitoring and health check tasks."""

import time
from typing import Dict, Any, List
from celery import current_app
from backend.core.celery import celery_app
from backend.core.logging import get_logger
from backend.core.monitoring import health_checker

logger = get_logger(__name__)

@celery_app.task(bind=True, name='app.tasks.monitoring.health_check')
def health_check(self) -> Dict[str, Any]:
    """Perform comprehensive health check of the system."""
    try:
        start_time = time.time()
        
        # Run all health checks
        health_results = health_checker.run_all_checks()
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Determine overall health status
        overall_status = "healthy"
        failed_checks = []
        
        for check_name, result in health_results.items():
            if not result.get('healthy', False):
                overall_status = "unhealthy"
                failed_checks.append({
                    'check': check_name,
                    'error': result.get('error', 'Unknown error')
                })
        
        health_summary = {
            'status': overall_status,
            'timestamp': time.time(),
            'execution_time': execution_time,
            'checks_count': len(health_results),
            'failed_checks': failed_checks,
            'details': health_results
        }
        
        # Log health status
        if overall_status == "healthy":
            logger.info(
                "System health check passed",
                extra={
                    'execution_time': execution_time,
                    'checks_count': len(health_results),
                    'event_type': 'health_check_success'
                }
            )
        else:
            logger.warning(
                "System health check failed",
                extra={
                    'execution_time': execution_time,
                    'failed_checks_count': len(failed_checks),
                    'failed_checks': failed_checks,
                    'event_type': 'health_check_failure'
                }
            )
        
        return health_summary
        
    except Exception as e:
        error_msg = f"Health check task failed: {str(e)}"
        logger.error(
            error_msg,
            extra={
                'exception_type': type(e).__name__,
                'event_type': 'health_check_error'
            }
        )
        
        return {
            'status': 'error',
            'timestamp': time.time(),
            'error': error_msg,
            'details': {}
        }

@celery_app.task(bind=True, name='app.tasks.monitoring.collect_queue_metrics')
def collect_queue_metrics(self) -> Dict[str, Any]:
    """Collect metrics about Celery queues and workers."""
    try:
        start_time = time.time()
        
        # Get Celery inspect instance
        inspect = current_app.control.inspect()
        
        # Collect various metrics
        metrics = {
            'timestamp': time.time(),
            'active_tasks': {},
            'scheduled_tasks': {},
            'reserved_tasks': {},
            'worker_stats': {},
            'queue_lengths': {},
            'registered_tasks': []
        }
        
        try:
            # Get active tasks
            active = inspect.active()
            if active:
                metrics['active_tasks'] = active
                total_active = sum(len(tasks) for tasks in active.values())
                logger.debug(f"Active tasks across all workers: {total_active}")
        except Exception as e:
            logger.warning(f"Failed to get active tasks: {e}")
        
        try:
            # Get scheduled tasks
            scheduled = inspect.scheduled()
            if scheduled:
                metrics['scheduled_tasks'] = scheduled
                total_scheduled = sum(len(tasks) for tasks in scheduled.values())
                logger.debug(f"Scheduled tasks across all workers: {total_scheduled}")
        except Exception as e:
            logger.warning(f"Failed to get scheduled tasks: {e}")
        
        try:
            # Get reserved tasks
            reserved = inspect.reserved()
            if reserved:
                metrics['reserved_tasks'] = reserved
                total_reserved = sum(len(tasks) for tasks in reserved.values())
                logger.debug(f"Reserved tasks across all workers: {total_reserved}")
        except Exception as e:
            logger.warning(f"Failed to get reserved tasks: {e}")
        
        try:
            # Get worker statistics
            stats = inspect.stats()
            if stats:
                metrics['worker_stats'] = stats
                logger.debug(f"Worker stats collected for {len(stats)} workers")
        except Exception as e:
            logger.warning(f"Failed to get worker stats: {e}")
        
        try:
            # Get registered tasks
            registered = inspect.registered()
            if registered:
                # Flatten the registered tasks from all workers
                all_tasks = set()
                for worker_tasks in registered.values():
                    all_tasks.update(worker_tasks)
                metrics['registered_tasks'] = sorted(list(all_tasks))
                logger.debug(f"Total registered tasks: {len(all_tasks)}")
        except Exception as e:
            logger.warning(f"Failed to get registered tasks: {e}")
        
        # Calculate execution time
        execution_time = time.time() - start_time
        metrics['collection_time'] = execution_time
        
        # Log metrics collection
        logger.info(
            "Queue metrics collected",
            extra={
                'execution_time': execution_time,
                'workers_count': len(metrics.get('worker_stats', {})),
                'registered_tasks_count': len(metrics.get('registered_tasks', [])),
                'event_type': 'metrics_collection'
            }
        )
        
        return metrics
        
    except Exception as e:
        error_msg = f"Queue metrics collection failed: {str(e)}"
        logger.error(
            error_msg,
            extra={
                'exception_type': type(e).__name__,
                'event_type': 'metrics_collection_error'
            }
        )
        
        return {
            'timestamp': time.time(),
            'error': error_msg,
            'collection_time': time.time() - start_time if 'start_time' in locals() else 0
        }

@celery_app.task(bind=True, name='app.tasks.monitoring.cleanup_failed_tasks')
def cleanup_failed_tasks(self, max_age_hours: int = 24) -> Dict[str, Any]:
    """Clean up old failed tasks from dead letter queues."""
    try:
        start_time = time.time()
        
        # This is a placeholder for actual cleanup logic
        # In a real implementation, you would:
        # 1. Connect to the message broker (Redis/RabbitMQ)
        # 2. Query dead letter queues
        # 3. Remove tasks older than max_age_hours
        # 4. Log cleanup statistics
        
        cleanup_result = {
            'timestamp': time.time(),
            'max_age_hours': max_age_hours,
            'cleaned_tasks': 0,  # Placeholder
            'execution_time': time.time() - start_time,
            'status': 'completed'
        }
        
        logger.info(
            "Failed tasks cleanup completed",
            extra={
                'max_age_hours': max_age_hours,
                'cleaned_tasks': cleanup_result['cleaned_tasks'],
                'execution_time': cleanup_result['execution_time'],
                'event_type': 'cleanup_completed'
            }
        )
        
        return cleanup_result
        
    except Exception as e:
        error_msg = f"Failed tasks cleanup error: {str(e)}"
        logger.error(
            error_msg,
            extra={
                'exception_type': type(e).__name__,
                'max_age_hours': max_age_hours,
                'event_type': 'cleanup_error'
            }
        )
        
        return {
            'timestamp': time.time(),
            'error': error_msg,
            'status': 'failed',
            'execution_time': time.time() - start_time if 'start_time' in locals() else 0
        }

@celery_app.task(bind=True, name='app.tasks.monitoring.alert_on_queue_backlog')
def alert_on_queue_backlog(self, threshold: int = 100) -> Dict[str, Any]:
    """Monitor queue backlogs and send alerts if thresholds are exceeded."""
    try:
        start_time = time.time()
        
        # Get current queue metrics
        metrics = collect_queue_metrics.apply().get()
        
        alerts = []
        
        # Check active tasks across all workers
        if 'active_tasks' in metrics:
            for worker, tasks in metrics['active_tasks'].items():
                if len(tasks) > threshold:
                    alerts.append({
                        'type': 'high_active_tasks',
                        'worker': worker,
                        'count': len(tasks),
                        'threshold': threshold
                    })
        
        # Check reserved tasks
        if 'reserved_tasks' in metrics:
            for worker, tasks in metrics['reserved_tasks'].items():
                if len(tasks) > threshold:
                    alerts.append({
                        'type': 'high_reserved_tasks',
                        'worker': worker,
                        'count': len(tasks),
                        'threshold': threshold
                    })
        
        result = {
            'timestamp': time.time(),
            'threshold': threshold,
            'alerts_count': len(alerts),
            'alerts': alerts,
            'execution_time': time.time() - start_time
        }
        
        if alerts:
            logger.warning(
                "Queue backlog alerts triggered",
                extra={
                    'alerts_count': len(alerts),
                    'threshold': threshold,
                    'alerts': alerts,
                    'event_type': 'queue_backlog_alert'
                }
            )
        else:
            logger.debug(
                "Queue backlog check passed",
                extra={
                    'threshold': threshold,
                    'execution_time': result['execution_time'],
                    'event_type': 'queue_backlog_check'
                }
            )
        
        return result
        
    except Exception as e:
        error_msg = f"Queue backlog monitoring failed: {str(e)}"
        logger.error(
            error_msg,
            extra={
                'exception_type': type(e).__name__,
                'threshold': threshold,
                'event_type': 'queue_backlog_error'
            }
        )
        
        return {
            'timestamp': time.time(),
            'error': error_msg,
            'execution_time': time.time() - start_time if 'start_time' in locals() else 0
        }