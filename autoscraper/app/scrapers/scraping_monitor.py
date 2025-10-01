#!/usr/bin/env python3
"""
Scraping Monitor and Logging System
Comprehensive monitoring, logging, and alerting for web scraping operations
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import sqlite3
import aiosqlite
from pathlib import Path
from enum import Enum
from contextlib import asynccontextmanager

# Database setup
from app.database.database import db_manager

# Import shared types
from .types import ScrapingResult, ScrapingStatus, ScrapingMetrics

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ScrapingMetrics:
    """Metrics for scraping operations"""
    job_board_name: str
    total_scrapes: int
    successful_scrapes: int
    failed_scrapes: int
    total_jobs_found: int
    average_execution_time: float
    success_rate: float
    last_successful_scrape: Optional[datetime]
    last_failed_scrape: Optional[datetime]
    common_errors: List[str]
    timestamp: datetime

@dataclass
class Alert:
    """Alert for monitoring issues"""
    level: AlertLevel
    message: str
    job_board_name: str
    timestamp: datetime
    details: Dict[str, Any]

class ScrapingLogger:
    """Enhanced logging for scraping operations"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup different loggers
        self.setup_loggers()
    
    def setup_loggers(self):
        """Setup different types of loggers"""
        # Main scraping logger
        self.scraping_logger = logging.getLogger('scraping')
        self.scraping_logger.setLevel(logging.INFO)
        
        # Performance logger
        self.performance_logger = logging.getLogger('performance')
        self.performance_logger.setLevel(logging.INFO)
        
        # Error logger
        self.error_logger = logging.getLogger('errors')
        self.error_logger.setLevel(logging.WARNING)
        
        # Setup file handlers
        self._setup_file_handlers()
        
        # Setup console handler
        self._setup_console_handler()
    
    def _setup_file_handlers(self):
        """Setup file handlers for different log types"""
        # Scraping operations log
        scraping_handler = logging.FileHandler(
            self.log_dir / 'scraping_operations.log'
        )
        scraping_handler.setLevel(logging.INFO)
        scraping_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        scraping_handler.setFormatter(scraping_formatter)
        self.scraping_logger.addHandler(scraping_handler)
        
        # Performance log
        performance_handler = logging.FileHandler(
            self.log_dir / 'performance.log'
        )
        performance_handler.setLevel(logging.INFO)
        performance_formatter = logging.Formatter(
            '%(asctime)s - %(message)s'
        )
        performance_handler.setFormatter(performance_formatter)
        self.performance_logger.addHandler(performance_handler)
        
        # Error log
        error_handler = logging.FileHandler(
            self.log_dir / 'errors.log'
        )
        error_handler.setLevel(logging.WARNING)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(exc_info)s'
        )
        error_handler.setFormatter(error_formatter)
        self.error_logger.addHandler(error_handler)
    
    def _setup_console_handler(self):
        """Setup console handler for immediate feedback"""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        # Add to all loggers
        self.scraping_logger.addHandler(console_handler)
        self.performance_logger.addHandler(console_handler)
        self.error_logger.addHandler(console_handler)
    
    def log_scraping_start(self, job_board_name: str, query: str, location: str):
        """Log the start of a scraping operation"""
        self.scraping_logger.info(
            f"Starting scrape - Board: {job_board_name}, Query: {query}, Location: {location}"
        )
    
    def log_scraping_result(self, result: ScrapingResult):
        """Log the result of a scraping operation"""
        self.scraping_logger.info(
            f"Scrape completed - Board: {result.job_board_name}, "
            f"Status: {result.status.value}, Jobs: {result.total_found}, "
            f"Pages: {result.pages_scraped}, Time: {result.execution_time:.2f}s"
        )
        
        # Log performance metrics
        self.performance_logger.info(
            json.dumps({
                'job_board': result.job_board_name,
                'execution_time': result.execution_time,
                'jobs_found': result.total_found,
                'pages_scraped': result.pages_scraped,
                'status': result.status.value,
                'timestamp': result.timestamp.isoformat()
            })
        )
        
        # Log errors if any
        if result.errors:
            for error in result.errors:
                self.error_logger.error(
                    f"Scraping error - Board: {result.job_board_name}, Error: {error}"
                )
    
    def log_rate_limit(self, job_board_name: str, wait_time: float):
        """Log rate limiting events"""
        self.scraping_logger.info(
            f"Rate limit applied - Board: {job_board_name}, Wait: {wait_time:.2f}s"
        )
    
    def log_retry_attempt(self, job_board_name: str, attempt: int, error: str):
        """Log retry attempts"""
        self.scraping_logger.warning(
            f"Retry attempt {attempt} - Board: {job_board_name}, Error: {error}"
        )

class ScrapingMonitor:
    """Monitor scraping operations and generate alerts"""
    
    def __init__(self, db_path: str = "scraping_monitor.db"):
        self.db_path = db_path
        self.logger = ScrapingLogger()
        self.alerts = []
        self.init_database()
    
    def init_database(self):
        """Initialize monitoring database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scraping_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_board_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    jobs_found INTEGER NOT NULL,
                    pages_scraped INTEGER NOT NULL,
                    execution_time REAL NOT NULL,
                    errors TEXT,
                    timestamp DATETIME NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    job_board_name TEXT NOT NULL,
                    details TEXT,
                    timestamp DATETIME NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_board_name TEXT NOT NULL,
                    total_scrapes INTEGER NOT NULL,
                    successful_scrapes INTEGER NOT NULL,
                    failed_scrapes INTEGER NOT NULL,
                    total_jobs_found INTEGER NOT NULL,
                    average_execution_time REAL NOT NULL,
                    success_rate REAL NOT NULL,
                    timestamp DATETIME NOT NULL
                )
            """)
    
    def record_scraping_result(self, result: ScrapingResult):
        """Record scraping result in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO scraping_results 
                (job_board_name, status, jobs_found, pages_scraped, 
                 execution_time, errors, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                result.job_board_name,
                result.status.value,
                result.total_found,
                result.pages_scraped,
                result.execution_time,
                json.dumps(result.errors),
                result.timestamp
            ))
        
        # Log the result
        self.logger.log_scraping_result(result)
        
        # Check for alerts
        self._check_for_alerts(result)
    
    def _check_for_alerts(self, result: ScrapingResult):
        """Check if alerts should be generated based on scraping result"""
        # Alert on failed scrapes
        if result.status == ScrapingStatus.FAILED:
            self._create_alert(
                AlertLevel.ERROR,
                f"Scraping failed for {result.job_board_name}",
                result.job_board_name,
                {'errors': result.errors, 'execution_time': result.execution_time}
            )
        
        # Alert on low job count
        if result.status == ScrapingStatus.SUCCESS and result.total_found < 5:
            self._create_alert(
                AlertLevel.WARNING,
                f"Low job count ({result.total_found}) for {result.job_board_name}",
                result.job_board_name,
                {'jobs_found': result.total_found}
            )
        
        # Alert on slow execution
        if result.execution_time > 60:  # More than 1 minute
            self._create_alert(
                AlertLevel.WARNING,
                f"Slow scraping ({result.execution_time:.2f}s) for {result.job_board_name}",
                result.job_board_name,
                {'execution_time': result.execution_time}
            )
        
        # Check success rate over time
        self._check_success_rate_alert(result.job_board_name)
    
    def _check_success_rate_alert(self, job_board_name: str):
        """Check if success rate has dropped below threshold"""
        metrics = self.get_job_board_metrics(job_board_name, days=7)
        if metrics and metrics.success_rate < 0.5:  # Less than 50% success rate
            self._create_alert(
                AlertLevel.ERROR,
                f"Low success rate ({metrics.success_rate:.2%}) for {job_board_name}",
                job_board_name,
                {'success_rate': metrics.success_rate, 'period': '7 days'}
            )
    
    def _create_alert(self, level: AlertLevel, message: str, 
                     job_board_name: str, details: Dict[str, Any]):
        """Create and store an alert"""
        alert = Alert(
            level=level,
            message=message,
            job_board_name=job_board_name,
            timestamp=datetime.now(),
            details=details
        )
        
        self.alerts.append(alert)
        
        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO alerts (level, message, job_board_name, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                alert.level.value,
                alert.message,
                alert.job_board_name,
                json.dumps(alert.details),
                alert.timestamp
            ))
        
        # Log the alert
        if level == AlertLevel.CRITICAL:
            self.logger.error_logger.critical(f"CRITICAL ALERT: {message}")
        elif level == AlertLevel.ERROR:
            self.logger.error_logger.error(f"ERROR ALERT: {message}")
        elif level == AlertLevel.WARNING:
            self.logger.error_logger.warning(f"WARNING ALERT: {message}")
        else:
            self.logger.scraping_logger.info(f"INFO ALERT: {message}")
    
    def get_job_board_metrics(self, job_board_name: str, 
                             days: int = 30) -> Optional[ScrapingMetrics]:
        """Get metrics for a specific job board"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_scrapes,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_scrapes,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_scrapes,
                    SUM(jobs_found) as total_jobs_found,
                    AVG(execution_time) as avg_execution_time,
                    MAX(CASE WHEN status = 'success' THEN timestamp END) as last_success,
                    MAX(CASE WHEN status = 'failed' THEN timestamp END) as last_failure
                FROM scraping_results 
                WHERE job_board_name = ? AND timestamp >= ?
            """, (job_board_name, cutoff_date))
            
            row = cursor.fetchone()
            if not row or row[0] == 0:
                return None
            
            total_scrapes = row[0]
            successful_scrapes = row[1] or 0
            failed_scrapes = row[2] or 0
            total_jobs_found = row[3] or 0
            avg_execution_time = row[4] or 0.0
            last_success = datetime.fromisoformat(row[5]) if row[5] else None
            last_failure = datetime.fromisoformat(row[6]) if row[6] else None
            
            success_rate = successful_scrapes / total_scrapes if total_scrapes > 0 else 0.0
            
            # Get common errors
            cursor = conn.execute("""
                SELECT errors FROM scraping_results 
                WHERE job_board_name = ? AND timestamp >= ? AND errors != '[]'
                ORDER BY timestamp DESC LIMIT 10
            """, (job_board_name, cutoff_date))
            
            error_rows = cursor.fetchall()
            common_errors = []
            for error_row in error_rows:
                try:
                    errors = json.loads(error_row[0])
                    common_errors.extend(errors)
                except:
                    continue
            
            # Get most common errors (top 5)
            error_counts = {}
            for error in common_errors:
                error_counts[error] = error_counts.get(error, 0) + 1
            
            top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            common_errors = [error for error, count in top_errors]
            
            return ScrapingMetrics(
                job_board_name=job_board_name,
                total_scrapes=total_scrapes,
                successful_scrapes=successful_scrapes,
                failed_scrapes=failed_scrapes,
                total_jobs_found=total_jobs_found,
                average_execution_time=avg_execution_time,
                success_rate=success_rate,
                last_successful_scrape=last_success,
                last_failed_scrape=last_failure,
                common_errors=common_errors,
                timestamp=datetime.now()
            )
    
    def get_all_metrics(self, days: int = 30) -> List[ScrapingMetrics]:
        """Get metrics for all job boards"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT job_board_name FROM scraping_results
                WHERE timestamp >= ?
            """, (datetime.now() - timedelta(days=days),))
            
            job_boards = [row[0] for row in cursor.fetchall()]
        
        metrics = []
        for job_board in job_boards:
            board_metrics = self.get_job_board_metrics(job_board, days)
            if board_metrics:
                metrics.append(board_metrics)
        
        return metrics
    
    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Get recent alerts"""
        cutoff_date = datetime.now() - timedelta(hours=hours)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT level, message, job_board_name, details, timestamp
                FROM alerts 
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            """, (cutoff_date,))
            
            alerts = []
            for row in cursor.fetchall():
                try:
                    details = json.loads(row[3]) if row[3] else {}
                except:
                    details = {}
                
                alerts.append(Alert(
                    level=AlertLevel(row[0]),
                    message=row[1],
                    job_board_name=row[2],
                    details=details,
                    timestamp=datetime.fromisoformat(row[4])
                ))
            
            return alerts
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        metrics = self.get_all_metrics(days=7)
        alerts = self.get_recent_alerts(hours=24)
        
        # Overall statistics
        total_scrapes = sum(m.total_scrapes for m in metrics)
        total_jobs = sum(m.total_jobs_found for m in metrics)
        avg_success_rate = sum(m.success_rate for m in metrics) / len(metrics) if metrics else 0
        
        # Health status
        critical_alerts = [a for a in alerts if a.level == AlertLevel.CRITICAL]
        error_alerts = [a for a in alerts if a.level == AlertLevel.ERROR]
        
        if critical_alerts:
            health_status = "CRITICAL"
        elif error_alerts:
            health_status = "WARNING"
        elif avg_success_rate < 0.7:
            health_status = "DEGRADED"
        else:
            health_status = "HEALTHY"
        
        return {
            'health_status': health_status,
            'report_timestamp': datetime.now().isoformat(),
            'period': '7 days',
            'summary': {
                'total_scrapes': total_scrapes,
                'total_jobs_found': total_jobs,
                'average_success_rate': avg_success_rate,
                'active_job_boards': len(metrics)
            },
            'job_board_metrics': [asdict(m) for m in metrics],
            'recent_alerts': {
                'critical': len(critical_alerts),
                'error': len(error_alerts),
                'warning': len([a for a in alerts if a.level == AlertLevel.WARNING]),
                'info': len([a for a in alerts if a.level == AlertLevel.INFO])
            },
            'alerts': [asdict(a) for a in alerts[:10]]  # Last 10 alerts
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scraping statistics for dashboard"""
        try:
            metrics = self.get_all_metrics(days=7)
            alerts = self.get_recent_alerts(hours=24)
            
            # Calculate overall statistics
            total_scrapes = sum(m.total_scrapes for m in metrics)
            total_jobs_found = sum(m.total_jobs_found for m in metrics)
            total_successful = sum(m.successful_scrapes for m in metrics)
            total_failed = sum(m.failed_scrapes for m in metrics)
            
            # Calculate averages
            avg_execution_time = sum(m.average_execution_time for m in metrics) / len(metrics) if metrics else 0.0
            overall_success_rate = (total_successful / total_scrapes * 100) if total_scrapes > 0 else 0.0
            
            # Count errors
            error_alerts = [a for a in alerts if a.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]]
            
            return {
                'total_scrapes': total_scrapes,
                'total_jobs_found': total_jobs_found,
                'successful_scrapes': total_successful,
                'failed_scrapes': total_failed,
                'success_rate': overall_success_rate,
                'average_execution_time': avg_execution_time,
                'total_errors': len(error_alerts),
                'active_job_boards': len(metrics),
                'recent_alerts': len(alerts),
                'last_updated': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error_logger.error(f"Error getting statistics: {e}")
            return {
                'total_scrapes': 0,
                'total_jobs_found': 0,
                'successful_scrapes': 0,
                'failed_scrapes': 0,
                'success_rate': 0.0,
                'average_execution_time': 0.0,
                'total_errors': 0,
                'active_job_boards': 0,
                'recent_alerts': 0,
                'last_updated': datetime.now().isoformat()
            }

    def cleanup_old_data(self, days: int = 90):
        """Clean up old monitoring data"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            # Clean up old results
            cursor = conn.execute(
                "DELETE FROM scraping_results WHERE timestamp < ?", 
                (cutoff_date,)
            )
            results_deleted = cursor.rowcount
            
            # Clean up old alerts
            cursor = conn.execute(
                "DELETE FROM alerts WHERE timestamp < ?", 
                (cutoff_date,)
            )
            alerts_deleted = cursor.rowcount
            
            self.logger.scraping_logger.info(
                f"Cleanup completed: {results_deleted} results, {alerts_deleted} alerts deleted"
            )

# Global monitor instance
_monitor_instance = None

def get_monitor() -> ScrapingMonitor:
    """Get global monitor instance"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = ScrapingMonitor()
    return _monitor_instance

@asynccontextmanager
async def monitored_scraping(job_board_name: str, query: str, location: str):
    """Context manager for monitored scraping operations"""
    monitor = get_monitor()
    monitor.logger.log_scraping_start(job_board_name, query, location)
    
    start_time = time.time()
    try:
        yield monitor
    except Exception as e:
        # Log the exception
        monitor.logger.error_logger.error(
            f"Unhandled exception in scraping {job_board_name}: {e}",
            exc_info=True
        )
        raise
    finally:
        execution_time = time.time() - start_time
        monitor.logger.scraping_logger.info(
            f"Scraping session completed for {job_board_name} in {execution_time:.2f}s"
        )