#!/usr/bin/env python3
"""
Metrics Collection and Export
Prometheus metrics for autoscraper service monitoring
"""

import time
import psutil
from typing import Dict, Any
from prometheus_client import (
    Counter, Histogram, Gauge, Info, 
    generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry, REGISTRY
)
from fastapi import APIRouter, Response
from loguru import logger

from config.settings import get_settings

settings = get_settings()


class AutoScraperMetrics:
    """Prometheus metrics for autoscraper service"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, registry: CollectorRegistry = REGISTRY):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, registry: CollectorRegistry = REGISTRY):
        if self._initialized:
            return
        
        self.registry = registry
        
        # Service info
        self.service_info = Info(
            'autoscraper_service_info',
            'Autoscraper service information',
            registry=registry
        )
        self.service_info.info({
            'version': '1.0.0',
            'environment': settings.ENVIRONMENT,
            'service_name': 'autoscraper'
        })
        
        self._setup_metrics(registry)
        self._initialized = True
    
    def _setup_metrics(self, registry):
        """Setup all metrics - called only once"""
        
        # HTTP metrics
        self.http_requests_total = Counter(
            'autoscraper_http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code'],
            registry=registry
        )
        
        self.http_request_duration = Histogram(
            'autoscraper_http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint'],
            registry=registry
        )
        
        # Authentication metrics
        self.auth_attempts_total = Counter(
            'autoscraper_auth_attempts_total',
            'Total authentication attempts',
            ['status'],
            registry=registry
        )
        
        # Rate limiting metrics
        self.rate_limit_hits_total = Counter(
            'autoscraper_rate_limit_hits_total',
            'Total rate limit hits',
            ['client_type'],
            registry=registry
        )
        
        # Database metrics
        self.db_connections_active = Gauge(
            'autoscraper_db_connections_active',
            'Active database connections',
            registry=registry
        )
        
        self.db_query_duration = Histogram(
            'autoscraper_db_query_duration_seconds',
            'Database query duration in seconds',
            ['operation'],
            registry=registry
        )
        
        self.db_errors_total = Counter(
            'autoscraper_db_errors_total',
            'Total database errors',
            ['error_type'],
            registry=registry
        )
        
        # Redis metrics
        self.redis_operations_total = Counter(
            'autoscraper_redis_operations_total',
            'Total Redis operations',
            ['operation', 'status'],
            registry=registry
        )
        
        self.redis_connection_errors_total = Counter(
            'autoscraper_redis_connection_errors_total',
            'Total Redis connection errors',
            registry=registry
        )
        
        # Celery metrics
        self.celery_tasks_total = Counter(
            'autoscraper_celery_tasks_total',
            'Total Celery tasks',
            ['task_name', 'status'],
            registry=registry
        )
        
        self.celery_task_duration = Histogram(
            'autoscraper_celery_task_duration_seconds',
            'Celery task duration in seconds',
            ['task_name'],
            registry=registry
        )
        
        self.celery_workers_active = Gauge(
            'autoscraper_celery_workers_active',
            'Active Celery workers',
            registry=registry
        )
        
        # Scraping metrics
        self.scrape_jobs_total = Counter(
            'autoscraper_scrape_jobs_total',
            'Total scrape jobs',
            ['job_board_type', 'status'],
            registry=registry
        )
        
        self.scrape_job_duration = Histogram(
            'autoscraper_scrape_job_duration_seconds',
            'Scrape job duration in seconds',
            ['job_board_type'],
            registry=registry
        )
        
        self.jobs_scraped_total = Counter(
            'autoscraper_jobs_scraped_total',
            'Total jobs scraped',
            ['job_board', 'status'],
            registry=registry
        )
        
        self.jobs_normalized_total = Counter(
            'autoscraper_jobs_normalized_total',
            'Total jobs normalized',
            ['status'],
            registry=registry
        )
        
        # System metrics
        self.system_cpu_usage = Gauge(
            'autoscraper_system_cpu_usage_percent',
            'System CPU usage percentage',
            registry=registry
        )
        
        self.system_memory_usage = Gauge(
            'autoscraper_system_memory_usage_bytes',
            'System memory usage in bytes',
            registry=registry
        )
        
        self.system_memory_total = Gauge(
            'autoscraper_system_memory_total_bytes',
            'Total system memory in bytes',
            registry=registry
        )
        
        self.system_disk_usage = Gauge(
            'autoscraper_system_disk_usage_bytes',
            'System disk usage in bytes',
            registry=registry
        )
        
        self.system_disk_total = Gauge(
            'autoscraper_system_disk_total_bytes',
            'Total system disk space in bytes',
            registry=registry
        )
        
        # Health check metrics
        self.health_check_status = Gauge(
            'autoscraper_health_check_status',
            'Health check status (1=healthy, 0=unhealthy)',
            ['component'],
            registry=registry
        )
        
        self.health_check_duration = Histogram(
            'autoscraper_health_check_duration_seconds',
            'Health check duration in seconds',
            ['component'],
            registry=registry
        )
    
    def record_http_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics"""
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        self.http_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_auth_attempt(self, success: bool):
        """Record authentication attempt"""
        status = 'success' if success else 'failure'
        self.auth_attempts_total.labels(status=status).inc()
    
    def record_rate_limit_hit(self, client_type: str = 'unknown'):
        """Record rate limit hit"""
        self.rate_limit_hits_total.labels(client_type=client_type).inc()
    
    def update_db_connections(self, active_connections: int):
        """Update active database connections"""
        self.db_connections_active.set(active_connections)
    
    def record_db_query(self, operation: str, duration: float):
        """Record database query metrics"""
        self.db_query_duration.labels(operation=operation).observe(duration)
    
    def record_db_error(self, error_type: str):
        """Record database error"""
        self.db_errors_total.labels(error_type=error_type).inc()
    
    def record_redis_operation(self, operation: str, success: bool):
        """Record Redis operation"""
        status = 'success' if success else 'failure'
        self.redis_operations_total.labels(
            operation=operation,
            status=status
        ).inc()
    
    def record_redis_connection_error(self):
        """Record Redis connection error"""
        self.redis_connection_errors_total.inc()
    
    def record_celery_task(self, task_name: str, status: str, duration: float = None):
        """Record Celery task metrics"""
        self.celery_tasks_total.labels(
            task_name=task_name,
            status=status
        ).inc()
        
        if duration is not None:
            self.celery_task_duration.labels(task_name=task_name).observe(duration)
    
    def update_celery_workers(self, active_workers: int):
        """Update active Celery workers count"""
        self.celery_workers_active.set(active_workers)
    
    def record_scrape_job(self, job_board_type: str, status: str, duration: float = None):
        """Record scrape job metrics"""
        self.scrape_jobs_total.labels(
            job_board_type=job_board_type,
            status=status
        ).inc()
        
        if duration is not None:
            self.scrape_job_duration.labels(job_board_type=job_board_type).observe(duration)
    
    def record_job_scraped(self, job_board: str, status: str):
        """Record individual job scraped"""
        self.jobs_scraped_total.labels(
            job_board=job_board,
            status=status
        ).inc()
    
    def record_job_normalized(self, success: bool):
        """Record job normalization"""
        status = 'success' if success else 'failure'
        self.jobs_normalized_total.labels(status=status).inc()
    
    def update_system_metrics(self):
        """Update system resource metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.system_cpu_usage.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.system_memory_usage.set(memory.used)
            self.system_memory_total.set(memory.total)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.system_disk_usage.set(disk.used)
            self.system_disk_total.set(disk.total)
            
        except Exception as e:
            logger.error(f"Failed to update system metrics: {e}")
    
    def record_health_check(self, component: str, healthy: bool, duration: float):
        """Record health check metrics"""
        status = 1 if healthy else 0
        self.health_check_status.labels(component=component).set(status)
        self.health_check_duration.labels(component=component).observe(duration)
    
    def get_metrics(self) -> str:
        """Get all metrics in Prometheus format"""
        # Update system metrics before export
        self.update_system_metrics()
        
        return generate_latest(self.registry)


# Create global metrics instance
metrics = AutoScraperMetrics()

# Create metrics router
metrics_router = APIRouter()


@metrics_router.get("/")
async def get_metrics():
    """Prometheus metrics endpoint"""
    metrics_data = metrics.get_metrics()
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )


@metrics_router.get("/health")
async def metrics_health():
    """Metrics endpoint health check"""
    return {
        "status": "healthy",
        "metrics_enabled": True,
        "registry_collectors": len(metrics.registry._collector_to_names)
    }


class MetricsMiddleware:
    """Middleware to collect HTTP request metrics"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = time.time()
        method = scope["method"]
        path = scope["path"]
        
        # Normalize path for metrics (remove IDs, etc.)
        normalized_path = self._normalize_path(path)
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration = time.time() - start_time
                
                # Record metrics
                metrics.record_http_request(
                    method=method,
                    endpoint=normalized_path,
                    status_code=status_code,
                    duration=duration
                )
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics (replace IDs with placeholders)"""
        import re
        
        # Replace UUIDs with placeholder
        path = re.sub(
            r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '/{id}',
            path,
            flags=re.IGNORECASE
        )
        
        # Replace numeric IDs with placeholder
        path = re.sub(r'/\d+', '/{id}', path)
        
        return path