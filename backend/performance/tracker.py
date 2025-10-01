from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
import time
import psutil
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of performance metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

@dataclass
class PerformanceMetric:
    """Individual performance metric"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""

@dataclass
class ScrapingSession:
    """Performance tracking for a scraping session"""
    session_id: str
    config_id: int
    source: str
    start_time: datetime
    end_time: Optional[datetime] = None
    metrics: List[PerformanceMetric] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> float:
        """Get session duration in milliseconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return (datetime.utcnow() - self.start_time).total_seconds() * 1000
    
    def add_metric(self, name: str, value: float, metric_type: MetricType, 
                   tags: Dict[str, str] = None, unit: str = ""):
        """Add a performance metric to the session"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            metric_type=metric_type,
            timestamp=datetime.utcnow(),
            tags=tags or {},
            unit=unit
        )
        self.metrics.append(metric)
    
    def add_error(self, error: str):
        """Add an error to the session"""
        self.errors.append(f"{datetime.utcnow().isoformat()}: {error}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary for the session"""
        metrics_by_type = defaultdict(list)
        for metric in self.metrics:
            metrics_by_type[metric.name].append(metric.value)
        
        summary = {
            'session_id': self.session_id,
            'config_id': self.config_id,
            'source': self.source,
            'duration_ms': self.duration_ms,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'total_metrics': len(self.metrics),
            'total_errors': len(self.errors),
            'error_rate': len(self.errors) / max(1, len(self.metrics)) * 100,
            'metrics_summary': {}
        }
        
        # Calculate aggregated metrics
        for name, values in metrics_by_type.items():
            if values:
                summary['metrics_summary'][name] = {
                    'count': len(values),
                    'sum': sum(values),
                    'avg': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values)
                }
        
        return summary

class PerformanceTracker:
    """Enhanced performance tracking for scraping operations"""
    
    def __init__(self):
        self.sessions: Dict[str, ScrapingSession] = {}
        self.global_metrics: List[PerformanceMetric] = []
        self._lock = threading.Lock()
        self._system_monitor_active = False
        self._system_metrics = {}
    
    def start_session(self, session_id: str, config_id: int, source: str) -> ScrapingSession:
        """Start a new performance tracking session"""
        with self._lock:
            session = ScrapingSession(
                session_id=session_id,
                config_id=config_id,
                source=source,
                start_time=datetime.utcnow()
            )
            self.sessions[session_id] = session
            logger.info(f"Started performance tracking session: {session_id}")
            return session
    
    def end_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """End a performance tracking session and return summary"""
        with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found")
                return None
            
            session.end_time = datetime.utcnow()
            summary = session.get_summary()
            
            # Archive completed session
            self.sessions.pop(session_id, None)
            
            logger.info(f"Ended performance tracking session: {session_id}, "
                       f"Duration: {summary['duration_ms']:.2f}ms")
            
            return summary
    
    def record_metric(self, session_id: str, name: str, value: float, 
                     metric_type: MetricType, tags: Dict[str, str] = None, unit: str = ""):
        """Record a performance metric for a session"""
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.add_metric(name, value, metric_type, tags, unit)
            else:
                # Record as global metric if session not found
                metric = PerformanceMetric(
                    name=name,
                    value=value,
                    metric_type=metric_type,
                    timestamp=datetime.utcnow(),
                    tags=tags or {},
                    unit=unit
                )
                self.global_metrics.append(metric)
    
    def record_error(self, session_id: str, error: str):
        """Record an error for a session"""
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.add_error(error)
                logger.warning(f"Error in session {session_id}: {error}")
    
    def start_system_monitoring(self):
        """Start system resource monitoring"""
        if self._system_monitor_active:
            return
        
        self._system_monitor_active = True
        
        def monitor_system():
            while self._system_monitor_active:
                try:
                    # CPU usage
                    cpu_percent = psutil.cpu_percent(interval=1)
                    self._system_metrics['cpu_percent'] = cpu_percent
                    
                    # Memory usage
                    memory = psutil.virtual_memory()
                    self._system_metrics['memory_percent'] = memory.percent
                    self._system_metrics['memory_available_mb'] = memory.available / 1024 / 1024
                    
                    # Disk usage
                    disk = psutil.disk_usage('/')
                    self._system_metrics['disk_percent'] = disk.percent
                    
                    # Network I/O
                    net_io = psutil.net_io_counters()
                    self._system_metrics['network_bytes_sent'] = net_io.bytes_sent
                    self._system_metrics['network_bytes_recv'] = net_io.bytes_recv
                    
                    time.sleep(5)  # Monitor every 5 seconds
                    
                except Exception as e:
                    logger.error(f"System monitoring error: {e}")
                    time.sleep(10)
        
        monitor_thread = threading.Thread(target=monitor_system, daemon=True)
        monitor_thread.start()
        logger.info("Started system resource monitoring")
    
    def stop_system_monitoring(self):
        """Stop system resource monitoring"""
        self._system_monitor_active = False
        logger.info("Stopped system resource monitoring")
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        return self._system_metrics.copy()
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get information about active sessions"""
        with self._lock:
            return [
                {
                    'session_id': session_id,
                    'config_id': session.config_id,
                    'source': session.source,
                    'duration_ms': session.duration_ms,
                    'metrics_count': len(session.metrics),
                    'errors_count': len(session.errors)
                }
                for session_id, session in self.sessions.items()
            ]
    
    def cleanup_old_metrics(self, max_age_hours: int = 24):
        """Clean up old global metrics"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        with self._lock:
            initial_count = len(self.global_metrics)
            self.global_metrics = [
                metric for metric in self.global_metrics 
                if metric.timestamp > cutoff_time
            ]
            cleaned_count = initial_count - len(self.global_metrics)
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old performance metrics")

# Global performance tracker instance
performance_tracker = PerformanceTracker()

class PerformanceContext:
    """Context manager for performance tracking"""
    
    def __init__(self, session_id: str, config_id: int, source: str):
        self.session_id = session_id
        self.config_id = config_id
        self.source = source
        self.session = None
    
    def __enter__(self) -> ScrapingSession:
        self.session = performance_tracker.start_session(
            self.session_id, self.config_id, self.source
        )
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            performance_tracker.record_error(
                self.session_id, f"{exc_type.__name__}: {exc_val}"
            )
        
        summary = performance_tracker.end_session(self.session_id)
        if summary:
            logger.info(f"Performance summary: {summary}")

def track_performance(session_id: str, config_id: int, source: str):
    """Decorator for performance tracking"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with PerformanceContext(session_id, config_id, source) as session:
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    execution_time = (time.time() - start_time) * 1000
                    session.add_metric(
                        "execution_time", execution_time, MetricType.TIMER, unit="ms"
                    )
                    return result
                except Exception as e:
                    execution_time = (time.time() - start_time) * 1000
                    session.add_metric(
                        "execution_time", execution_time, MetricType.TIMER, unit="ms"
                    )
                    session.add_error(str(e))
                    raise
        return wrapper
    return decorator