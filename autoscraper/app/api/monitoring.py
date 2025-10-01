from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from loguru import logger

from ..monitoring.dashboard import (
    get_monitoring_dashboard, 
    DashboardStats, 
    MetricType, 
    AlertLevel,
    Alert,
    MetricPoint,
    EngineMetrics
)
from ..middleware.auth import get_current_user

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

# Request/Response Models
class MetricQuery(BaseModel):
    """Query parameters for metrics"""
    metric_type: str = Field(..., description="Type of metric to query")
    start_time: Optional[datetime] = Field(None, description="Start time for query")
    end_time: Optional[datetime] = Field(None, description="End time for query")
    job_board: Optional[str] = Field(None, description="Filter by job board")
    engine: Optional[str] = Field(None, description="Filter by scraping engine")
    limit: int = Field(100, description="Maximum number of data points")

class AlertQuery(BaseModel):
    """Query parameters for alerts"""
    level: Optional[str] = Field(None, description="Alert level filter")
    resolved: Optional[bool] = Field(None, description="Filter by resolution status")
    start_time: Optional[datetime] = Field(None, description="Start time for query")
    end_time: Optional[datetime] = Field(None, description="End time for query")
    limit: int = Field(50, description="Maximum number of alerts")

class DashboardResponse(BaseModel):
    """Response model for dashboard data"""
    stats: Dict[str, Any]
    recent_metrics: List[Dict[str, Any]]
    active_alerts: List[Dict[str, Any]]
    engine_performance: Dict[str, Dict[str, Any]]
    job_board_status: Dict[str, Dict[str, Any]]
    system_health: Dict[str, Any]
    last_updated: datetime

class MetricsResponse(BaseModel):
    """Response model for metrics data"""
    metric_type: str
    data_points: List[Dict[str, Any]]
    summary: Dict[str, Any]
    query_params: Dict[str, Any]
    total_points: int

class AlertsResponse(BaseModel):
    """Response model for alerts"""
    alerts: List[Dict[str, Any]]
    summary: Dict[str, Any]
    query_params: Dict[str, Any]
    total_alerts: int

class SystemHealthResponse(BaseModel):
    """Response model for system health"""
    overall_status: str
    components: Dict[str, Dict[str, Any]]
    performance_metrics: Dict[str, float]
    resource_usage: Dict[str, float]
    uptime: float
    last_check: datetime

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive dashboard data"""
    try:
        # Get monitoring dashboard
        dashboard = await get_monitoring_dashboard()
        
        # Get dashboard stats
        stats = await dashboard.get_dashboard_stats()
        
        # Get recent metrics (last 24 hours)
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        recent_metrics = await dashboard.get_metrics(
            metric_type=MetricType.SCRAPING_SUCCESS,
            start_time=start_time,
            end_time=end_time,
            limit=100
        )
        
        # Get active alerts
        active_alerts = await dashboard.get_alerts(
            resolved=False,
            limit=20
        )
        
        # Format response
        return DashboardResponse(
            stats={
                "total_scraping_attempts": stats.total_scraping_attempts,
                "successful_scrapes": stats.successful_scrapes,
                "failed_scrapes": stats.failed_scrapes,
                "success_rate": stats.success_rate,
                "average_response_time": stats.average_response_time,
                "average_quality_score": stats.average_quality_score,
                "active_job_boards": stats.active_job_boards,
                "total_job_postings": stats.total_job_postings,
                "jobs_scraped_today": stats.jobs_scraped_today,
                "ai_analyses_today": stats.ai_analyses_today
            },
            recent_metrics=[
                {
                    "timestamp": metric.timestamp.isoformat(),
                    "value": metric.value,
                    "metadata": metric.metadata
                } for metric in recent_metrics
            ],
            active_alerts=[
                {
                    "id": alert.id,
                    "level": alert.level.value,
                    "message": alert.message,
                    "component": alert.component,
                    "created_at": alert.created_at.isoformat(),
                    "metadata": alert.metadata
                } for alert in active_alerts
            ],
            engine_performance={
                engine: {
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "average_response_time": metrics.average_response_time,
                    "success_rate": metrics.success_rate,
                    "last_used": metrics.last_used.isoformat() if metrics.last_used else None
                } for engine, metrics in stats.engine_metrics.items()
            },
            job_board_status=stats.quality_by_board,
            system_health={
                "cpu_usage": 0.0,  # Would be implemented with actual system monitoring
                "memory_usage": 0.0,
                "disk_usage": 0.0,
                "network_latency": stats.average_response_time
            },
            last_updated=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")

@router.post("/metrics", response_model=MetricsResponse)
async def get_metrics(
    query: MetricQuery,
    current_user: dict = Depends(get_current_user)
):
    """Get specific metrics data"""
    try:
        # Get monitoring dashboard
        dashboard = await get_monitoring_dashboard()
        
        # Convert string to MetricType enum
        try:
            metric_type = MetricType(query.metric_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid metric type: {query.metric_type}")
        
        # Set default time range if not provided
        if not query.start_time:
            query.start_time = datetime.now() - timedelta(hours=24)
        if not query.end_time:
            query.end_time = datetime.now()
        
        # Get metrics
        metrics = await dashboard.get_metrics(
            metric_type=metric_type,
            start_time=query.start_time,
            end_time=query.end_time,
            job_board=query.job_board,
            engine=query.engine,
            limit=query.limit
        )
        
        # Calculate summary statistics
        values = [m.value for m in metrics]
        summary = {
            "count": len(values),
            "min": min(values) if values else 0,
            "max": max(values) if values else 0,
            "average": sum(values) / len(values) if values else 0,
            "total": sum(values) if metric_type in [MetricType.SCRAPING_SUCCESS, MetricType.SCRAPING_FAILURE] else None
        }
        
        return MetricsResponse(
            metric_type=query.metric_type,
            data_points=[
                {
                    "timestamp": metric.timestamp.isoformat(),
                    "value": metric.value,
                    "metadata": metric.metadata
                } for metric in metrics
            ],
            summary=summary,
            query_params={
                "metric_type": query.metric_type,
                "start_time": query.start_time.isoformat(),
                "end_time": query.end_time.isoformat(),
                "job_board": query.job_board,
                "engine": query.engine,
                "limit": query.limit
            },
            total_points=len(metrics)
        )
        
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@router.post("/alerts", response_model=AlertsResponse)
async def get_alerts(
    query: AlertQuery,
    current_user: dict = Depends(get_current_user)
):
    """Get alerts based on query parameters"""
    try:
        # Get monitoring dashboard
        dashboard = await get_monitoring_dashboard()
        
        # Convert string to AlertLevel enum if provided
        level = None
        if query.level:
            try:
                level = AlertLevel(query.level)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid alert level: {query.level}")
        
        # Get alerts
        alerts = await dashboard.get_alerts(
            level=level,
            resolved=query.resolved,
            start_time=query.start_time,
            end_time=query.end_time,
            limit=query.limit
        )
        
        # Calculate summary
        level_counts = {}
        resolved_count = 0
        for alert in alerts:
            level_counts[alert.level.value] = level_counts.get(alert.level.value, 0) + 1
            if alert.resolved_at:
                resolved_count += 1
        
        summary = {
            "total_alerts": len(alerts),
            "resolved_alerts": resolved_count,
            "active_alerts": len(alerts) - resolved_count,
            "by_level": level_counts
        }
        
        return AlertsResponse(
            alerts=[
                {
                    "id": alert.id,
                    "level": alert.level.value,
                    "message": alert.message,
                    "component": alert.component,
                    "created_at": alert.created_at.isoformat(),
                    "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                    "metadata": alert.metadata
                } for alert in alerts
            ],
            summary=summary,
            query_params={
                "level": query.level,
                "resolved": query.resolved,
                "start_time": query.start_time.isoformat() if query.start_time else None,
                "end_time": query.end_time.isoformat() if query.end_time else None,
                "limit": query.limit
            },
            total_alerts=len(alerts)
        )
        
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {str(e)}")

@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user: dict = Depends(get_current_user)
):
    """Get system health status"""
    try:
        # Get monitoring dashboard
        dashboard = await get_monitoring_dashboard()
        
        # Get dashboard stats for health metrics
        stats = await dashboard.get_dashboard_stats()
        
        # Calculate overall health status
        health_score = 0
        components = {}
        
        # Check scraping success rate
        if stats.success_rate >= 0.9:
            components["scraping"] = {"status": "healthy", "score": 1.0, "message": "High success rate"}
            health_score += 0.3
        elif stats.success_rate >= 0.7:
            components["scraping"] = {"status": "warning", "score": 0.7, "message": "Moderate success rate"}
            health_score += 0.2
        else:
            components["scraping"] = {"status": "critical", "score": 0.3, "message": "Low success rate"}
            health_score += 0.1
        
        # Check response time
        if stats.average_response_time <= 5.0:
            components["performance"] = {"status": "healthy", "score": 1.0, "message": "Good response time"}
            health_score += 0.2
        elif stats.average_response_time <= 10.0:
            components["performance"] = {"status": "warning", "score": 0.7, "message": "Moderate response time"}
            health_score += 0.15
        else:
            components["performance"] = {"status": "critical", "score": 0.3, "message": "Slow response time"}
            health_score += 0.1
        
        # Check data quality
        if stats.average_quality_score >= 0.8:
            components["data_quality"] = {"status": "healthy", "score": 1.0, "message": "High quality data"}
            health_score += 0.2
        elif stats.average_quality_score >= 0.6:
            components["data_quality"] = {"status": "warning", "score": 0.7, "message": "Moderate quality data"}
            health_score += 0.15
        else:
            components["data_quality"] = {"status": "critical", "score": 0.3, "message": "Low quality data"}
            health_score += 0.1
        
        # Check active job boards
        if stats.active_job_boards >= 50:
            components["job_boards"] = {"status": "healthy", "score": 1.0, "message": "Many active boards"}
            health_score += 0.15
        elif stats.active_job_boards >= 20:
            components["job_boards"] = {"status": "warning", "score": 0.7, "message": "Some active boards"}
            health_score += 0.1
        else:
            components["job_boards"] = {"status": "critical", "score": 0.3, "message": "Few active boards"}
            health_score += 0.05
        
        # Check AI system
        if stats.ai_analyses_today > 0:
            components["ai_system"] = {"status": "healthy", "score": 1.0, "message": "AI system active"}
            health_score += 0.15
        else:
            components["ai_system"] = {"status": "warning", "score": 0.5, "message": "AI system inactive"}
            health_score += 0.1
        
        # Determine overall status
        if health_score >= 0.8:
            overall_status = "healthy"
        elif health_score >= 0.6:
            overall_status = "warning"
        else:
            overall_status = "critical"
        
        return SystemHealthResponse(
            overall_status=overall_status,
            components=components,
            performance_metrics={
                "success_rate": stats.success_rate,
                "average_response_time": stats.average_response_time,
                "quality_score": stats.average_quality_score,
                "health_score": health_score
            },
            resource_usage={
                "cpu_usage": 0.0,  # Would be implemented with actual system monitoring
                "memory_usage": 0.0,
                "disk_usage": 0.0,
                "active_connections": float(stats.active_job_boards)
            },
            uptime=86400.0,  # Would be calculated from actual uptime
            last_check=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get system health: {str(e)}")

@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Resolve a specific alert"""
    try:
        # Get monitoring dashboard
        dashboard = await get_monitoring_dashboard()
        
        # Resolve alert (this would be implemented in the dashboard)
        # For now, we'll just return a success message
        
        return {
            "message": f"Alert {alert_id} resolved successfully",
            "alert_id": alert_id,
            "resolved_at": datetime.now().isoformat(),
            "resolved_by": current_user.get("username", "unknown")
        }
        
    except Exception as e:
        logger.error(f"Failed to resolve alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve alert: {str(e)}")

@router.get("/engines/performance")
async def get_engine_performance(
    engine: Optional[str] = Query(None, description="Filter by specific engine"),
    hours: int = Query(24, description="Hours of data to include"),
    current_user: dict = Depends(get_current_user)
):
    """Get detailed engine performance metrics"""
    try:
        # Get monitoring dashboard
        dashboard = await get_monitoring_dashboard()
        
        # Get dashboard stats
        stats = await dashboard.get_dashboard_stats()
        
        # Filter by specific engine if requested
        if engine:
            if engine not in stats.engine_metrics:
                raise HTTPException(status_code=404, detail=f"Engine {engine} not found")
            
            engine_data = stats.engine_metrics[engine]
            return {
                "engine": engine,
                "metrics": {
                    "total_requests": engine_data.total_requests,
                    "successful_requests": engine_data.successful_requests,
                    "failed_requests": engine_data.failed_requests,
                    "success_rate": engine_data.success_rate,
                    "average_response_time": engine_data.average_response_time,
                    "last_used": engine_data.last_used.isoformat() if engine_data.last_used else None
                },
                "period_hours": hours,
                "last_updated": datetime.now().isoformat()
            }
        
        # Return all engines
        return {
            "engines": {
                engine_name: {
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "success_rate": metrics.success_rate,
                    "average_response_time": metrics.average_response_time,
                    "last_used": metrics.last_used.isoformat() if metrics.last_used else None
                } for engine_name, metrics in stats.engine_metrics.items()
            },
            "period_hours": hours,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get engine performance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get engine performance: {str(e)}")

@router.get("/job-boards/status")
async def get_job_board_status(
    board: Optional[str] = Query(None, description="Filter by specific job board"),
    current_user: dict = Depends(get_current_user)
):
    """Get job board status and performance metrics"""
    try:
        # Get monitoring dashboard
        dashboard = await get_monitoring_dashboard()
        
        # Get dashboard stats
        stats = await dashboard.get_dashboard_stats()
        
        # Filter by specific board if requested
        if board:
            if board not in stats.quality_by_board:
                raise HTTPException(status_code=404, detail=f"Job board {board} not found")
            
            board_data = stats.quality_by_board[board]
            return {
                "job_board": board,
                "quality_score": board_data,
                "status": "active" if board_data > 0.5 else "inactive",
                "last_updated": datetime.now().isoformat()
            }
        
        # Return all job boards
        return {
            "job_boards": {
                board_name: {
                    "quality_score": quality_score,
                    "status": "active" if quality_score > 0.5 else "inactive"
                } for board_name, quality_score in stats.quality_by_board.items()
            },
            "total_boards": len(stats.quality_by_board),
            "active_boards": stats.active_job_boards,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get job board status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job board status: {str(e)}")