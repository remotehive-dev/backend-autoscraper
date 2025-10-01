#!/usr/bin/env python3
"""
RemoteHive Monitoring and Metrics System
Provides comprehensive application monitoring, metrics collection, and health checks
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from threading import Lock

# Optional imports with fallbacks
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = object

try:
    from fastapi import Request, Response
except ImportError:
    Request = None
    Response = None

try:
    from backend.logging import get_logger, LogLevel
except ImportError:
    # Fallback logger
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)
    LogLevel = None

try:
    from backend.core.config import settings
except ImportError:
    # Fallback settings
    class FallbackSettings:
        LOG_LEVEL = "INFO"
    settings = FallbackSettings()


@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class HealthCheck:
    """Health check configuration"""
    name: str
    check_func: Any  # Changed from Callable to Any to avoid schema issues
    interval: int = 30  # seconds
    timeout: int = 10   # seconds
    critical: bool = False
    last_check: Optional[datetime] = None
    last_result: Optional[bool] = None
    last_error: Optional[str] = None


class MetricsCollector:
    """Collects and stores application metrics"""
    
    def __init__(self, max_points: int = 1000):
        self.max_points = max_points
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points))
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.lock = Lock()
        self.logger = get_logger("metrics")
    
    def counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.counters[key] += value
            self._add_point(name, self.counters[key], labels)
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Alias for counter method for backward compatibility"""
        self.counter(name, value, labels)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Alias for gauge method for backward compatibility"""
        self.gauge(name, value, labels)
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Alias for histogram method for backward compatibility"""
        self.histogram(name, value, labels)
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric"""
        with self.lock:
            key = self._make_key(name, labels)
            self.gauges[key] = value
            self._add_point(name, value, labels)
    
    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Add a value to histogram"""
        with self.lock:
            key = self._make_key(name, labels)
            self.histograms[key].append(value)
            # Keep only recent values
            if len(self.histograms[key]) > self.max_points:
                self.histograms[key] = self.histograms[key][-self.max_points:]
            self._add_point(name, value, labels)
    
    def timing(self, name: str, duration: float, labels: Optional[Dict[str, str]] = None):
        """Record timing metric"""
        self.histogram(f"{name}_duration", duration, labels)
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create metric key with labels"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def _add_point(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Add metric point to time series"""
        point = MetricPoint(
            timestamp=datetime.now(),
            value=value,
            labels=labels or {}
        )
        self.metrics[name].append(point)
    
    def get_metric_summary(self, name: str, duration_minutes: int = 60) -> Dict[str, Any]:
        """Get metric summary for specified duration"""
        cutoff = datetime.now() - timedelta(minutes=duration_minutes)
        points = [p for p in self.metrics[name] if p.timestamp >= cutoff]
        
        if not points:
            return {"count": 0, "min": None, "max": None, "avg": None}
        
        values = [p.value for p in points]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1] if values else None
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics"""
        with self.lock:
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms": {k: list(v) for k, v in self.histograms.items()}
            }


class SystemMonitor:
    """Monitor system resources"""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.metrics = metrics_collector or MetricsCollector()
        self.logger = get_logger("system_monitor")
        self.monitoring = False
    
    async def start_monitoring(self, interval: int = 30):
        """Start system monitoring"""
        self._monitoring = True
        self.logger.info(f"Starting system monitoring with {interval}s interval")
        
        while self._monitoring:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(interval)
            except Exception as e:
                self.logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(interval)
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self._monitoring = False
        self.logger.info("Stopped system monitoring")
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        if not PSUTIL_AVAILABLE:
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "disk_percent": 0.0,
                "psutil_available": False
            }
        
        try:
            # Get current system metrics
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": (disk.used / disk.total) * 100,
                "memory_used_bytes": memory.used,
                "memory_available_bytes": memory.available,
                "disk_used_bytes": disk.used,
                "disk_free_bytes": disk.free,
                "psutil_available": True
            }
        except Exception as e:
            self.logger.error(f"Failed to get system metrics: {e}")
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "disk_percent": 0.0,
                "error": str(e),
                "psutil_available": True
            }
    
    async def _collect_system_metrics(self):
        """Collect system resource metrics"""
        if not PSUTIL_AVAILABLE:
            self.logger.warning("psutil not available, skipping system metrics collection")
            return
            
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        self.metrics.gauge("system_cpu_percent", cpu_percent)
        
        # Memory metrics
        memory = psutil.virtual_memory()
        self.metrics.gauge("system_memory_percent", memory.percent)
        self.metrics.gauge("system_memory_available_mb", memory.available / 1024 / 1024)
        self.metrics.gauge("system_memory_used_mb", memory.used / 1024 / 1024)
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        self.metrics.gauge("system_disk_percent", disk.percent)
        self.metrics.gauge("system_disk_free_gb", disk.free / 1024 / 1024 / 1024)
        
        # Network metrics
        network = psutil.net_io_counters()
        self.metrics.counter("system_network_bytes_sent", network.bytes_sent)
        self.metrics.counter("system_network_bytes_recv", network.bytes_recv)
        
        # Process metrics
        process = psutil.Process()
        self.metrics.gauge("process_memory_mb", process.memory_info().rss / 1024 / 1024)
        self.metrics.gauge("process_cpu_percent", process.cpu_percent())
        self.metrics.gauge("process_threads", process.num_threads())
        
        # File descriptors (Unix only)
        try:
            self.metrics.gauge("process_open_files", process.num_fds())
        except AttributeError:
            pass  # Windows doesn't have num_fds


class HealthChecker:
    """Manage and run health checks"""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.metrics = metrics_collector or MetricsCollector()
        self.logger = get_logger("health_checker")
        self.checks: Dict[str, HealthCheck] = {}
        self.running = False
    
    def register_check(self, check: HealthCheck):
        """Register a health check"""
        self.checks[check.name] = check
        self.logger.info(f"Registered health check: {check.name}")
    
    def register_simple_check(
        self, 
        name: str, 
        check_func: Any,  # Changed from Callable to Any
        interval: int = 30,
        critical: bool = False
    ):
        """Register a simple health check"""
        check = HealthCheck(
            name=name,
            check_func=check_func,
            interval=interval,
            critical=critical
        )
        self.register_check(check)
    
    async def start_health_checks(self):
        """Start running health checks"""
        self._checking = True
        self.logger.info("Starting health checks")
        
        # Start a task for each health check
        tasks = []
        for check in self.checks.values():
            task = asyncio.create_task(self._run_health_check(check))
            tasks.append(task)
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            self.logger.error(f"Error in health checks: {e}")
    
    def stop_health_checks(self):
        """Stop health checks"""
        self._checking = False
        self.logger.info("Stopped health checks")
    
    async def _run_health_check(self, check: HealthCheck):
        """Run a single health check continuously"""
        while self._checking:
            try:
                start_time = time.time()
                
                # Run the check with timeout
                try:
                    result = await asyncio.wait_for(
                        self._execute_check(check.check_func),
                        timeout=check.timeout
                    )
                    check.last_result = result
                    check.last_error = None
                    
                    # Record metrics
                    self.metrics.gauge(
                        f"health_check_{check.name}", 
                        1.0 if result else 0.0
                    )
                    
                except asyncio.TimeoutError:
                    check.last_result = False
                    check.last_error = "Timeout"
                    self.metrics.gauge(f"health_check_{check.name}", 0.0)
                    
                except Exception as e:
                    check.last_result = False
                    check.last_error = str(e)
                    self.metrics.gauge(f"health_check_{check.name}", 0.0)
                    
                    if check.critical:
                        self.logger.error(
                            f"Critical health check failed: {check.name} - {e}"
                        )
                    else:
                        self.logger.warning(
                            f"Health check failed: {check.name} - {e}"
                        )
                
                check.last_check = datetime.now()
                
                # Record check duration
                duration = time.time() - start_time
                self.metrics.timing(f"health_check_{check.name}_duration", duration)
                
                await asyncio.sleep(check.interval)
                
            except Exception as e:
                self.logger.error(f"Error running health check {check.name}: {e}")
                await asyncio.sleep(check.interval)
    
    async def _execute_check(self, check_func: Any) -> bool:  # Changed from Callable to Any
        """Execute a health check function"""
        if asyncio.iscoroutinefunction(check_func):
            return await check_func()
        else:
            return check_func()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        status = {
            "healthy": True,
            "checks": {},
            "summary": {
                "total": len(self.checks),
                "passing": 0,
                "failing": 0,
                "critical_failing": 0
            }
        }
        
        for name, check in self.checks.items():
            # Only include serializable data, exclude check_func
            check_status = {
                "name": check.name,
                "healthy": check.last_result,
                "last_check": check.last_check.isoformat() if check.last_check else None,
                "error": check.last_error,
                "critical": check.critical,
                "interval": check.interval,
                "timeout": check.timeout
            }
            status["checks"][name] = check_status
            
            if check.last_result:
                status["summary"]["passing"] += 1
            else:
                status["summary"]["failing"] += 1
                if check.critical:
                    status["summary"]["critical_failing"] += 1
                    status["healthy"] = False
        
        return status
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks synchronously and return status"""
        for name, check in self.checks.items():
            try:
                # Run the check synchronously
                if asyncio.iscoroutinefunction(check.check_func):
                    # For async functions, we'll mark as skipped in sync mode
                    check.last_result = None
                    check.last_error = "Async check skipped in sync mode"
                else:
                    check.last_result = check.check_func()
                    check.last_error = None
                check.last_check = datetime.now()
            except Exception as e:
                check.last_result = False
                check.last_error = str(e)
                check.last_check = datetime.now()
        
        return self.get_health_status()


class ApplicationMonitor:
    """Main application monitoring system"""
    
    def __init__(self):
        self.metrics = MetricsCollector()
        self.system_monitor = SystemMonitor(self.metrics)
        self.health_checker = HealthChecker(self.metrics)
        self.logger = get_logger("app_monitor")
        self._monitoring_tasks: List[asyncio.Task] = []
    
    async def start(self):
        """Start all monitoring systems"""
        self.logger.info("Starting application monitoring")
        
        # Register default health checks
        self._register_default_health_checks()
        
        # Start monitoring tasks
        system_task = asyncio.create_task(self.system_monitor.start_monitoring())
        health_task = asyncio.create_task(self.health_checker.start_health_checks())
        
        self._monitoring_tasks = [system_task, health_task]
        
        self.logger.info("Application monitoring started")
    
    async def stop(self):
        """Stop all monitoring systems"""
        self.logger.info("Stopping application monitoring")
        
        self.system_monitor.stop_monitoring()
        self.health_checker.stop_health_checks()
        
        # Cancel monitoring tasks
        for task in self._monitoring_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)
        
        self.logger.info("Application monitoring stopped")
    
    def _register_default_health_checks(self):
        """Register default health checks"""
        # Database health check
        async def check_database():
            try:
                from backend.database.mongodb_models import User
                # Simple MongoDB health check by attempting to find a user
                await User.find_one()
                return True
            except Exception:
                return False
        
        self.health_checker.register_simple_check(
            "database", check_database, interval=30, critical=True
        )
        
        # Memory health check
        if PSUTIL_AVAILABLE:
            def check_memory():
                memory = psutil.virtual_memory()
                return memory.percent < 90  # Alert if memory usage > 90%
            
            self.health_checker.register_simple_check(
                "memory", check_memory, interval=60, critical=False
            )
            
            # Disk space health check
            def check_disk_space():
                disk = psutil.disk_usage('/')
                return disk.percent < 95  # Alert if disk usage > 95%
            
            self.health_checker.register_simple_check(
                "disk_space", check_disk_space, interval=300, critical=True
            )
    
    def get_monitoring_data(self) -> Dict[str, Any]:
        """Get comprehensive monitoring data"""
        return {
            "health": self.health_checker.get_health_status(),
            "metrics": self.metrics.get_all_metrics(),
            "system": {
                "cpu_summary": self.metrics.get_metric_summary("system_cpu_percent"),
                "memory_summary": self.metrics.get_metric_summary("system_memory_percent"),
                "disk_summary": self.metrics.get_metric_summary("system_disk_percent")
            }
        }


# Global monitoring instance
app_monitor = ApplicationMonitor()


# Context manager for timing operations
@asynccontextmanager
async def time_operation(name: str, labels: Optional[Dict[str, str]] = None):
    """Context manager to time operations"""
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        app_monitor.metrics.timing(name, duration, labels)


# Decorator for timing functions
def monitor_performance(name: Optional[str] = None, labels: Optional[Dict[str, str]] = None):
    """Decorator to monitor function performance"""
    def decorator(func):
        metric_name = name or f"function_{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                async with time_operation(metric_name, labels):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = time.time() - start_time
                    app_monitor.metrics.timing(metric_name, duration, labels)
            return sync_wrapper
    
    return decorator


# Export main components
__all__ = [
    'ApplicationMonitor',
    'MetricsCollector',
    'SystemMonitor',
    'HealthChecker',
    'app_monitor',
    'time_operation',
    'monitor_performance'
]

# Export health_checker for convenience
health_checker = app_monitor.health_checker