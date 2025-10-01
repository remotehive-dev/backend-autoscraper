import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import json
from collections import defaultdict, deque
from loguru import logger
import time
from statistics import mean, median

from ..models.mongodb_models import JobBoard, ScrapingSession, JobPosting
from ..database.mongodb_client import get_mongodb_client
from ..job_boards.job_board_manager import get_job_board_manager
from ..scrapers.types import ScrapingEngine
from ..ai.decision_engine import get_ai_decision_engine

class MetricType(str, Enum):
    """Types of metrics tracked"""
    SCRAPING_SUCCESS_RATE = "scraping_success_rate"
    RESPONSE_TIME = "response_time"
    JOBS_SCRAPED = "jobs_scraped"
    AI_ANALYSIS_TIME = "ai_analysis_time"
    ENGINE_PERFORMANCE = "engine_performance"
    ERROR_RATE = "error_rate"
    RATE_LIMIT_HITS = "rate_limit_hits"
    ANTI_BOT_DETECTIONS = "anti_bot_detections"
    DATA_QUALITY_SCORE = "data_quality_score"
    COST_PER_JOB = "cost_per_job"

class AlertLevel(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class Alert:
    """System alert"""
    id: str
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str
    metadata: Dict[str, Any] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class DashboardStats:
    """Dashboard statistics"""
    total_job_boards: int
    active_job_boards: int
    total_jobs_scraped: int
    jobs_scraped_today: int
    success_rate: float
    avg_response_time: float
    ai_analysis_count: int
    ai_success_rate: float
    active_sessions: int
    errors_last_hour: int
    top_performing_boards: List[Dict[str, Any]]
    engine_performance: Dict[str, float]
    recent_alerts: List[Alert]
    system_health: str  # healthy, degraded, critical

@dataclass
class EngineMetrics:
    """Scraping engine performance metrics"""
    engine: ScrapingEngine
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    success_rate: float
    jobs_scraped: int
    last_used: datetime
    error_types: Dict[str, int]

class MonitoringDashboard:
    """Real-time monitoring dashboard for the autoscraper system"""
    
    def __init__(self):
        self.mongodb_client = get_mongodb_client()
        self.job_board_manager = None
        self.ai_decision_engine = None
        
        # In-memory metrics storage (for real-time data)
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.alerts: List[Alert] = []
        self.engine_metrics: Dict[ScrapingEngine, EngineMetrics] = {}
        
        # Performance tracking
        self.session_start_time = datetime.now()
        self.last_update = datetime.now()
        
        # Alert thresholds
        self.alert_thresholds = {
            MetricType.SCRAPING_SUCCESS_RATE: 0.8,  # Alert if below 80%
            MetricType.RESPONSE_TIME: 10.0,  # Alert if above 10 seconds
            MetricType.ERROR_RATE: 0.1,  # Alert if above 10%
            MetricType.DATA_QUALITY_SCORE: 0.7,  # Alert if below 70%
        }
        
        # Initialize engine metrics
        for engine in ScrapingEngine:
            self.engine_metrics[engine] = EngineMetrics(
                engine=engine,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                avg_response_time=0.0,
                success_rate=0.0,
                jobs_scraped=0,
                last_used=datetime.now(),
                error_types={}
            )
    
    async def initialize(self):
        """Initialize the monitoring dashboard"""
        try:
            self.job_board_manager = await get_job_board_manager()
            self.ai_decision_engine = get_ai_decision_engine()
            
            # Load historical metrics from database
            await self._load_historical_metrics()
            
            logger.info("Monitoring dashboard initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize monitoring dashboard: {e}")
            raise
    
    async def _load_historical_metrics(self):
        """Load recent historical metrics from database"""
        try:
            db = await self.mongodb_client.get_database()
            
            # Load recent scraping sessions (last 24 hours)
            sessions_collection = db.scraping_sessions
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            async for session_doc in sessions_collection.find(
                {'created_at': {'$gte': cutoff_time}}
            ).sort('created_at', -1).limit(1000):
                try:
                    session = ScrapingSession(**session_doc)
                    
                    # Add metrics from session
                    self._add_metric(
                        MetricType.SCRAPING_SUCCESS_RATE,
                        1.0 if session.status == 'completed' else 0.0,
                        session.created_at,
                        {'job_board': session.job_board_name, 'engine': session.engine}
                    )
                    
                    if session.total_time:
                        self._add_metric(
                            MetricType.RESPONSE_TIME,
                            session.total_time,
                            session.created_at,
                            {'job_board': session.job_board_name, 'engine': session.engine}
                        )
                    
                    if session.jobs_found:
                        self._add_metric(
                            MetricType.JOBS_SCRAPED,
                            session.jobs_found,
                            session.created_at,
                            {'job_board': session.job_board_name, 'engine': session.engine}
                        )
                    
                except Exception as e:
                    logger.error(f"Failed to process session {session_doc.get('_id')}: {e}")
            
            logger.info(f"Loaded historical metrics: {sum(len(q) for q in self.metrics.values())} data points")
            
        except Exception as e:
            logger.error(f"Failed to load historical metrics: {e}")
    
    def _add_metric(self, metric_type: MetricType, value: float, timestamp: datetime = None, metadata: Dict[str, Any] = None):
        """Add a metric data point"""
        if timestamp is None:
            timestamp = datetime.now()
        
        metric_point = MetricPoint(
            timestamp=timestamp,
            value=value,
            metadata=metadata or {}
        )
        
        self.metrics[metric_type.value].append(metric_point)
        
        # Check for alerts
        self._check_alert_thresholds(metric_type, value, metadata)
    
    def _check_alert_thresholds(self, metric_type: MetricType, value: float, metadata: Dict[str, Any] = None):
        """Check if metric value triggers an alert"""
        try:
            if metric_type not in self.alert_thresholds:
                return
            
            threshold = self.alert_thresholds[metric_type]
            
            # Determine if alert should be triggered
            should_alert = False
            alert_level = AlertLevel.WARNING
            
            if metric_type == MetricType.SCRAPING_SUCCESS_RATE:
                if value < threshold:
                    should_alert = True
                    alert_level = AlertLevel.ERROR if value < 0.5 else AlertLevel.WARNING
            elif metric_type == MetricType.RESPONSE_TIME:
                if value > threshold:
                    should_alert = True
                    alert_level = AlertLevel.ERROR if value > 30 else AlertLevel.WARNING
            elif metric_type == MetricType.ERROR_RATE:
                if value > threshold:
                    should_alert = True
                    alert_level = AlertLevel.CRITICAL if value > 0.3 else AlertLevel.ERROR
            elif metric_type == MetricType.DATA_QUALITY_SCORE:
                if value < threshold:
                    should_alert = True
                    alert_level = AlertLevel.WARNING
            
            if should_alert:
                self._create_alert(
                    level=alert_level,
                    title=f"{metric_type.value.replace('_', ' ').title()} Alert",
                    message=f"{metric_type.value} is {value:.2f}, threshold is {threshold:.2f}",
                    source="monitoring_dashboard",
                    metadata=metadata
                )
        
        except Exception as e:
            logger.error(f"Failed to check alert thresholds: {e}")
    
    def _create_alert(self, level: AlertLevel, title: str, message: str, source: str, metadata: Dict[str, Any] = None):
        """Create a new alert"""
        try:
            alert_id = f"{source}_{int(time.time())}_{len(self.alerts)}"
            
            alert = Alert(
                id=alert_id,
                level=level,
                title=title,
                message=message,
                timestamp=datetime.now(),
                source=source,
                metadata=metadata or {}
            )
            
            self.alerts.append(alert)
            
            # Keep only recent alerts (last 100)
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-100:]
            
            logger.warning(f"Alert created: {title} - {message}")
            
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
    
    async def record_scraping_attempt(self, 
                                    job_board_name: str, 
                                    engine: ScrapingEngine, 
                                    success: bool, 
                                    response_time: float,
                                    jobs_found: int = 0,
                                    error_type: str = None):
        """Record a scraping attempt"""
        try:
            timestamp = datetime.now()
            metadata = {
                'job_board': job_board_name,
                'engine': engine.value
            }
            
            # Record basic metrics
            self._add_metric(MetricType.SCRAPING_SUCCESS_RATE, 1.0 if success else 0.0, timestamp, metadata)
            self._add_metric(MetricType.RESPONSE_TIME, response_time, timestamp, metadata)
            
            if jobs_found > 0:
                self._add_metric(MetricType.JOBS_SCRAPED, jobs_found, timestamp, metadata)
            
            # Update engine metrics
            engine_metric = self.engine_metrics[engine]
            engine_metric.total_requests += 1
            engine_metric.last_used = timestamp
            
            if success:
                engine_metric.successful_requests += 1
                engine_metric.jobs_scraped += jobs_found
            else:
                engine_metric.failed_requests += 1
                if error_type:
                    engine_metric.error_types[error_type] = engine_metric.error_types.get(error_type, 0) + 1
            
            # Recalculate engine metrics
            if engine_metric.total_requests > 0:
                engine_metric.success_rate = engine_metric.successful_requests / engine_metric.total_requests
            
            # Update average response time (simple moving average)
            if engine_metric.total_requests == 1:
                engine_metric.avg_response_time = response_time
            else:
                # Weighted average favoring recent requests
                weight = 0.1
                engine_metric.avg_response_time = (1 - weight) * engine_metric.avg_response_time + weight * response_time
            
            self.last_update = timestamp
            
        except Exception as e:
            logger.error(f"Failed to record scraping attempt: {e}")
    
    async def record_ai_analysis(self, analysis_time: float, success: bool, job_board_name: str = None):
        """Record AI analysis metrics"""
        try:
            timestamp = datetime.now()
            metadata = {'job_board': job_board_name} if job_board_name else {}
            
            self._add_metric(MetricType.AI_ANALYSIS_TIME, analysis_time, timestamp, metadata)
            
            # Track AI success rate
            ai_success_points = [p for p in self.metrics.get('ai_success_rate', []) if p.timestamp > datetime.now() - timedelta(hours=1)]
            ai_success_points.append(MetricPoint(timestamp, 1.0 if success else 0.0, metadata))
            
            if len(ai_success_points) > 100:
                ai_success_points = ai_success_points[-100:]
            
            self.metrics['ai_success_rate'] = deque(ai_success_points, maxlen=1000)
            
        except Exception as e:
            logger.error(f"Failed to record AI analysis: {e}")
    
    async def record_data_quality_score(self, score: float, job_board_name: str, sample_size: int = 1):
        """Record data quality score"""
        try:
            metadata = {
                'job_board': job_board_name,
                'sample_size': sample_size
            }
            
            self._add_metric(MetricType.DATA_QUALITY_SCORE, score, metadata=metadata)
            
        except Exception as e:
            logger.error(f"Failed to record data quality score: {e}")
    
    async def get_dashboard_stats(self) -> DashboardStats:
        """Get current dashboard statistics"""
        try:
            db = await self.mongodb_client.get_database()
            
            # Get job board counts
            job_boards_collection = db.job_boards
            total_job_boards = await job_boards_collection.count_documents({})
            active_job_boards = await job_boards_collection.count_documents({'is_active': True})
            
            # Get job counts
            jobs_collection = db.job_postings
            total_jobs = await jobs_collection.count_documents({})
            
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            jobs_today = await jobs_collection.count_documents({'scraped_at': {'$gte': today_start}})
            
            # Calculate success rate (last 100 attempts)
            success_points = list(self.metrics.get(MetricType.SCRAPING_SUCCESS_RATE.value, []))[-100:]
            success_rate = mean([p.value for p in success_points]) if success_points else 0.0
            
            # Calculate average response time
            response_points = list(self.metrics.get(MetricType.RESPONSE_TIME.value, []))[-100:]
            avg_response_time = mean([p.value for p in response_points]) if response_points else 0.0
            
            # AI metrics
            ai_points = list(self.metrics.get('ai_success_rate', []))[-100:]
            ai_success_rate = mean([p.value for p in ai_points]) if ai_points else 0.0
            ai_analysis_count = len(self.metrics.get(MetricType.AI_ANALYSIS_TIME.value, []))
            
            # Active sessions (sessions created in last hour)
            sessions_collection = db.scraping_sessions
            hour_ago = datetime.now() - timedelta(hours=1)
            active_sessions = await sessions_collection.count_documents({
                'created_at': {'$gte': hour_ago},
                'status': {'$in': ['running', 'pending']}
            })
            
            # Errors in last hour
            errors_last_hour = len([
                p for p in self.metrics.get(MetricType.ERROR_RATE.value, [])
                if p.timestamp > hour_ago and p.value > 0
            ])
            
            # Top performing job boards
            top_performing_boards = await self._get_top_performing_boards()
            
            # Engine performance
            engine_performance = {
                engine.value: metrics.success_rate
                for engine, metrics in self.engine_metrics.items()
            }
            
            # Recent alerts
            recent_alerts = [alert for alert in self.alerts if not alert.resolved][-10:]
            
            # System health
            system_health = self._calculate_system_health(success_rate, avg_response_time, errors_last_hour)
            
            return DashboardStats(
                total_job_boards=total_job_boards,
                active_job_boards=active_job_boards,
                total_jobs_scraped=total_jobs,
                jobs_scraped_today=jobs_today,
                success_rate=success_rate,
                avg_response_time=avg_response_time,
                ai_analysis_count=ai_analysis_count,
                ai_success_rate=ai_success_rate,
                active_sessions=active_sessions,
                errors_last_hour=errors_last_hour,
                top_performing_boards=top_performing_boards,
                engine_performance=engine_performance,
                recent_alerts=recent_alerts,
                system_health=system_health
            )
            
        except Exception as e:
            logger.error(f"Failed to get dashboard stats: {e}")
            return DashboardStats(
                total_job_boards=0,
                active_job_boards=0,
                total_jobs_scraped=0,
                jobs_scraped_today=0,
                success_rate=0.0,
                avg_response_time=0.0,
                ai_analysis_count=0,
                ai_success_rate=0.0,
                active_sessions=0,
                errors_last_hour=0,
                top_performing_boards=[],
                engine_performance={},
                recent_alerts=[],
                system_health="unknown"
            )
    
    async def _get_top_performing_boards(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top performing job boards"""
        try:
            db = await self.mongodb_client.get_database()
            
            # Aggregate job board performance from recent sessions
            pipeline = [
                {
                    '$match': {
                        'created_at': {'$gte': datetime.now() - timedelta(days=7)}
                    }
                },
                {
                    '$group': {
                        '_id': '$job_board_name',
                        'total_sessions': {'$sum': 1},
                        'successful_sessions': {
                            '$sum': {'$cond': [{'$eq': ['$status', 'completed']}, 1, 0]}
                        },
                        'total_jobs': {'$sum': '$jobs_found'},
                        'avg_time': {'$avg': '$total_time'}
                    }
                },
                {
                    '$addFields': {
                        'success_rate': {
                            '$divide': ['$successful_sessions', '$total_sessions']
                        }
                    }
                },
                {
                    '$sort': {'success_rate': -1, 'total_jobs': -1}
                },
                {
                    '$limit': limit
                }
            ]
            
            top_boards = []
            async for result in db.scraping_sessions.aggregate(pipeline):
                top_boards.append({
                    'name': result['_id'],
                    'success_rate': result['success_rate'],
                    'total_jobs': result['total_jobs'],
                    'avg_time': result['avg_time'],
                    'total_sessions': result['total_sessions']
                })
            
            return top_boards
            
        except Exception as e:
            logger.error(f"Failed to get top performing boards: {e}")
            return []
    
    def _calculate_system_health(self, success_rate: float, avg_response_time: float, errors_last_hour: int) -> str:
        """Calculate overall system health status"""
        try:
            # Health scoring
            health_score = 0
            
            # Success rate component (40% weight)
            if success_rate >= 0.9:
                health_score += 40
            elif success_rate >= 0.8:
                health_score += 30
            elif success_rate >= 0.6:
                health_score += 20
            else:
                health_score += 10
            
            # Response time component (30% weight)
            if avg_response_time <= 5:
                health_score += 30
            elif avg_response_time <= 10:
                health_score += 20
            elif avg_response_time <= 20:
                health_score += 10
            else:
                health_score += 5
            
            # Error rate component (30% weight)
            if errors_last_hour == 0:
                health_score += 30
            elif errors_last_hour <= 5:
                health_score += 20
            elif errors_last_hour <= 15:
                health_score += 10
            else:
                health_score += 5
            
            # Determine health status
            if health_score >= 80:
                return "healthy"
            elif health_score >= 60:
                return "degraded"
            else:
                return "critical"
                
        except Exception as e:
            logger.error(f"Failed to calculate system health: {e}")
            return "unknown"
    
    async def get_metric_history(self, 
                               metric_type: MetricType, 
                               hours: int = 24, 
                               job_board: str = None) -> List[MetricPoint]:
        """Get metric history for specified time period"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            points = [
                p for p in self.metrics.get(metric_type.value, [])
                if p.timestamp >= cutoff_time
            ]
            
            # Filter by job board if specified
            if job_board:
                points = [
                    p for p in points
                    if p.metadata.get('job_board') == job_board
                ]
            
            return sorted(points, key=lambda x: x.timestamp)
            
        except Exception as e:
            logger.error(f"Failed to get metric history: {e}")
            return []
    
    async def get_engine_metrics(self) -> Dict[ScrapingEngine, EngineMetrics]:
        """Get current engine performance metrics"""
        return self.engine_metrics.copy()
    
    async def get_alerts(self, level: AlertLevel = None, limit: int = 50) -> List[Alert]:
        """Get recent alerts"""
        try:
            alerts = self.alerts.copy()
            
            if level:
                alerts = [alert for alert in alerts if alert.level == level]
            
            # Sort by timestamp (newest first)
            alerts.sort(key=lambda x: x.timestamp, reverse=True)
            
            return alerts[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get alerts: {e}")
            return []
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        try:
            for alert in self.alerts:
                if alert.id == alert_id:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    logger.info(f"Alert resolved: {alert_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to resolve alert {alert_id}: {e}")
            return False
    
    async def export_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Export metrics data for analysis"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            export_data = {
                'export_time': datetime.now().isoformat(),
                'time_range_hours': hours,
                'metrics': {},
                'engine_metrics': {},
                'alerts': []
            }
            
            # Export metric data
            for metric_type, points in self.metrics.items():
                recent_points = [
                    {
                        'timestamp': p.timestamp.isoformat(),
                        'value': p.value,
                        'metadata': p.metadata
                    }
                    for p in points
                    if p.timestamp >= cutoff_time
                ]
                export_data['metrics'][metric_type] = recent_points
            
            # Export engine metrics
            for engine, metrics in self.engine_metrics.items():
                export_data['engine_metrics'][engine.value] = asdict(metrics)
                export_data['engine_metrics'][engine.value]['last_used'] = metrics.last_used.isoformat()
            
            # Export recent alerts
            recent_alerts = [
                alert for alert in self.alerts
                if alert.timestamp >= cutoff_time
            ]
            
            for alert in recent_alerts:
                alert_dict = asdict(alert)
                alert_dict['timestamp'] = alert.timestamp.isoformat()
                if alert.resolved_at:
                    alert_dict['resolved_at'] = alert.resolved_at.isoformat()
                export_data['alerts'].append(alert_dict)
            
            return export_data
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return {}

# Global instance
_monitoring_dashboard = None

async def get_monitoring_dashboard() -> MonitoringDashboard:
    """Get global monitoring dashboard instance"""
    global _monitoring_dashboard
    if _monitoring_dashboard is None:
        _monitoring_dashboard = MonitoringDashboard()
        await _monitoring_dashboard.initialize()
    return _monitoring_dashboard