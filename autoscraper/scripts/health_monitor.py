#!/usr/bin/env python3
"""
AutoScraper Service Health Monitoring
Comprehensive health checks and monitoring for the AutoScraper service integration
"""

import os
import sys
import time
import json
import asyncio
import requests
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import logging
from dataclasses import dataclass, asdict
from enum import Enum

# Configuration
SERVICE_URL = "http://localhost:8001"
MAIN_APP_URL = "http://localhost:8000"
REDIS_HOST = "localhost"
REDIS_PORT = 6379
CHECK_INTERVAL = 30  # seconds
ALERT_THRESHOLD = 3  # consecutive failures before alert
METRICS_RETENTION = 24 * 60 * 60  # 24 hours in seconds

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class HealthCheck:
    """Health check result"""
    name: str
    status: HealthStatus
    response_time: float
    message: str
    timestamp: datetime
    details: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result['status'] = self.status.value
        result['timestamp'] = self.timestamp.isoformat()
        return result

@dataclass
class SystemMetrics:
    """System metrics"""
    cpu_percent: float
    memory_percent: float
    disk_usage: float
    network_connections: int
    process_count: int
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result

class HealthMonitor:
    """Health monitoring system for AutoScraper service"""
    
    def __init__(self, service_url: str = SERVICE_URL, main_app_url: str = MAIN_APP_URL):
        self.service_url = service_url
        self.main_app_url = main_app_url
        self.session = requests.Session()
        self.session.timeout = 10
        
        # Health check history
        self.health_history: List[HealthCheck] = []
        self.metrics_history: List[SystemMetrics] = []
        self.alert_counts: Dict[str, int] = {}
        
        # Configure session
        self.session.headers.update({
            'User-Agent': 'AutoScraper-HealthMonitor/1.0'
        })
    
    def _make_request(self, url: str, timeout: int = 10) -> Tuple[bool, float, Dict[str, Any]]:
        """Make HTTP request and measure response time"""
        start_time = time.time()
        try:
            response = self.session.get(url, timeout=timeout)
            end_time = time.time()
            
            return (
                response.status_code == 200,
                end_time - start_time,
                {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'content_length': len(response.content)
                }
            )
        except Exception as e:
            end_time = time.time()
            return (
                False,
                end_time - start_time,
                {'error': str(e)}
            )
    
    def check_service_health(self) -> HealthCheck:
        """Check AutoScraper service health endpoint"""
        success, response_time, details = self._make_request(f"{self.service_url}/health")
        
        if success:
            if response_time < 1.0:
                status = HealthStatus.HEALTHY
                message = "Service is healthy"
            elif response_time < 3.0:
                status = HealthStatus.DEGRADED
                message = f"Service responding slowly ({response_time:.2f}s)"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Service responding very slowly ({response_time:.2f}s)"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Service health check failed: {details.get('error', 'Unknown error')}"
        
        return HealthCheck(
            name="service_health",
            status=status,
            response_time=response_time,
            message=message,
            timestamp=datetime.now(),
            details=details
        )
    
    def check_service_readiness(self) -> HealthCheck:
        """Check AutoScraper service readiness"""
        success, response_time, details = self._make_request(f"{self.service_url}/health/readiness")
        
        if success:
            status = HealthStatus.HEALTHY
            message = "Service is ready"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Service readiness check failed: {details.get('error', 'Unknown error')}"
        
        return HealthCheck(
            name="service_readiness",
            status=status,
            response_time=response_time,
            message=message,
            timestamp=datetime.now(),
            details=details
        )
    
    def check_service_liveness(self) -> HealthCheck:
        """Check AutoScraper service liveness"""
        success, response_time, details = self._make_request(f"{self.service_url}/health/liveness")
        
        if success:
            status = HealthStatus.HEALTHY
            message = "Service is alive"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Service liveness check failed: {details.get('error', 'Unknown error')}"
        
        return HealthCheck(
            name="service_liveness",
            status=status,
            response_time=response_time,
            message=message,
            timestamp=datetime.now(),
            details=details
        )
    
    def check_api_endpoints(self) -> List[HealthCheck]:
        """Check critical API endpoints"""
        endpoints = [
            ("/api/v1/autoscraper/dashboard", "dashboard"),
            ("/api/v1/autoscraper/engine/state", "engine_state"),
            ("/api/v1/autoscraper/system/metrics", "system_metrics")
        ]
        
        results = []
        for endpoint, name in endpoints:
            success, response_time, details = self._make_request(f"{self.service_url}{endpoint}")
            
            if success:
                if response_time < 2.0:
                    status = HealthStatus.HEALTHY
                    message = f"API endpoint {name} is healthy"
                else:
                    status = HealthStatus.DEGRADED
                    message = f"API endpoint {name} is slow ({response_time:.2f}s)"
            else:
                # Check if it's an auth error (401) which is expected
                if details.get('status_code') == 401:
                    status = HealthStatus.HEALTHY
                    message = f"API endpoint {name} is healthy (auth required)"
                else:
                    status = HealthStatus.UNHEALTHY
                    message = f"API endpoint {name} failed: {details.get('error', 'Unknown error')}"
            
            results.append(HealthCheck(
                name=f"api_{name}",
                status=status,
                response_time=response_time,
                message=message,
                timestamp=datetime.now(),
                details=details
            ))
        
        return results
    
    def check_redis_connectivity(self) -> HealthCheck:
        """Check Redis connectivity"""
        start_time = time.time()
        try:
            import redis
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
            r.ping()
            end_time = time.time()
            
            response_time = end_time - start_time
            
            return HealthCheck(
                name="redis_connectivity",
                status=HealthStatus.HEALTHY,
                response_time=response_time,
                message="Redis is accessible",
                timestamp=datetime.now(),
                details={'host': REDIS_HOST, 'port': REDIS_PORT}
            )
            
        except Exception as e:
            end_time = time.time()
            return HealthCheck(
                name="redis_connectivity",
                status=HealthStatus.UNHEALTHY,
                response_time=end_time - start_time,
                message=f"Redis connection failed: {str(e)}",
                timestamp=datetime.now(),
                details={'error': str(e)}
            )
    
    def check_main_app_integration(self) -> HealthCheck:
        """Check integration with main app"""
        success, response_time, details = self._make_request(f"{self.main_app_url}/health")
        
        if success:
            status = HealthStatus.HEALTHY
            message = "Main app is accessible"
        else:
            status = HealthStatus.DEGRADED
            message = f"Main app not accessible: {details.get('error', 'Unknown error')}"
        
        return HealthCheck(
            name="main_app_integration",
            status=status,
            response_time=response_time,
            message=message,
            timestamp=datetime.now(),
            details=details
        )
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Collect system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage = (disk.used / disk.total) * 100
            
            # Network connections
            connections = len(psutil.net_connections())
            
            # Process count
            process_count = len(psutil.pids())
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_usage=disk_usage,
                network_connections=connections,
                process_count=process_count,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {str(e)}")
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_usage=0.0,
                network_connections=0,
                process_count=0,
                timestamp=datetime.now()
            )
    
    def check_service_process(self) -> HealthCheck:
        """Check if AutoScraper service process is running"""
        start_time = time.time()
        
        try:
            # Look for uvicorn process with autoscraper
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'uvicorn' in cmdline and 'autoscraper' in cmdline:
                        end_time = time.time()
                        
                        # Get process details
                        process = psutil.Process(proc.info['pid'])
                        process_details = {
                            'pid': proc.info['pid'],
                            'cpu_percent': process.cpu_percent(),
                            'memory_percent': process.memory_percent(),
                            'status': process.status(),
                            'create_time': datetime.fromtimestamp(process.create_time()).isoformat()
                        }
                        
                        return HealthCheck(
                            name="service_process",
                            status=HealthStatus.HEALTHY,
                            response_time=end_time - start_time,
                            message=f"Service process found (PID: {proc.info['pid']})",
                            timestamp=datetime.now(),
                            details=process_details
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Process not found
            end_time = time.time()
            return HealthCheck(
                name="service_process",
                status=HealthStatus.UNHEALTHY,
                response_time=end_time - start_time,
                message="AutoScraper service process not found",
                timestamp=datetime.now(),
                details={}
            )
            
        except Exception as e:
            end_time = time.time()
            return HealthCheck(
                name="service_process",
                status=HealthStatus.UNKNOWN,
                response_time=end_time - start_time,
                message=f"Error checking service process: {str(e)}",
                timestamp=datetime.now(),
                details={'error': str(e)}
            )
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        logger.info("Running comprehensive health checks...")
        
        checks = []
        
        # Core service checks
        checks.append(self.check_service_health())
        checks.append(self.check_service_readiness())
        checks.append(self.check_service_liveness())
        checks.append(self.check_service_process())
        
        # API endpoint checks
        checks.extend(self.check_api_endpoints())
        
        # Dependency checks
        checks.append(self.check_redis_connectivity())
        checks.append(self.check_main_app_integration())
        
        # Collect system metrics
        metrics = self.collect_system_metrics()
        
        # Store in history
        self.health_history.extend(checks)
        self.metrics_history.append(metrics)
        
        # Clean up old data
        self._cleanup_old_data()
        
        # Analyze results
        healthy_checks = sum(1 for check in checks if check.status == HealthStatus.HEALTHY)
        total_checks = len(checks)
        overall_health = HealthStatus.HEALTHY
        
        if healthy_checks == total_checks:
            overall_health = HealthStatus.HEALTHY
        elif healthy_checks >= total_checks * 0.7:  # 70% healthy
            overall_health = HealthStatus.DEGRADED
        else:
            overall_health = HealthStatus.UNHEALTHY
        
        # Check for alerts
        alerts = self._check_for_alerts(checks)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_health": overall_health.value,
            "total_checks": total_checks,
            "healthy_checks": healthy_checks,
            "success_rate": (healthy_checks / total_checks) * 100,
            "checks": [check.to_dict() for check in checks],
            "system_metrics": metrics.to_dict(),
            "alerts": alerts
        }
    
    def _cleanup_old_data(self):
        """Clean up old health check data"""
        cutoff_time = datetime.now() - timedelta(seconds=METRICS_RETENTION)
        
        self.health_history = [
            check for check in self.health_history 
            if check.timestamp > cutoff_time
        ]
        
        self.metrics_history = [
            metrics for metrics in self.metrics_history 
            if metrics.timestamp > cutoff_time
        ]
    
    def _check_for_alerts(self, checks: List[HealthCheck]) -> List[Dict[str, Any]]:
        """Check for alert conditions"""
        alerts = []
        
        for check in checks:
            if check.status in [HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN]:
                # Increment alert count
                self.alert_counts[check.name] = self.alert_counts.get(check.name, 0) + 1
                
                # Generate alert if threshold reached
                if self.alert_counts[check.name] >= ALERT_THRESHOLD:
                    alerts.append({
                        "type": "health_check_failure",
                        "check_name": check.name,
                        "status": check.status.value,
                        "message": check.message,
                        "consecutive_failures": self.alert_counts[check.name],
                        "timestamp": check.timestamp.isoformat()
                    })
            else:
                # Reset alert count on success
                self.alert_counts[check.name] = 0
        
        return alerts
    
    def get_health_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get health summary for the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_checks = [
            check for check in self.health_history 
            if check.timestamp > cutoff_time
        ]
        
        if not recent_checks:
            return {
                "period_hours": hours,
                "total_checks": 0,
                "message": "No health check data available"
            }
        
        # Group by check name
        check_groups = {}
        for check in recent_checks:
            if check.name not in check_groups:
                check_groups[check.name] = []
            check_groups[check.name].append(check)
        
        # Calculate statistics
        summary = {
            "period_hours": hours,
            "total_checks": len(recent_checks),
            "check_types": len(check_groups),
            "checks": {}
        }
        
        for check_name, checks in check_groups.items():
            healthy_count = sum(1 for c in checks if c.status == HealthStatus.HEALTHY)
            avg_response_time = sum(c.response_time for c in checks) / len(checks)
            
            summary["checks"][check_name] = {
                "total": len(checks),
                "healthy": healthy_count,
                "success_rate": (healthy_count / len(checks)) * 100,
                "avg_response_time": avg_response_time,
                "latest_status": checks[-1].status.value,
                "latest_message": checks[-1].message
            }
        
        return summary
    
    async def monitor_continuously(self, interval: int = CHECK_INTERVAL):
        """Run continuous monitoring"""
        logger.info(f"Starting continuous monitoring (interval: {interval}s)")
        
        while True:
            try:
                results = self.run_all_checks()
                
                # Log summary
                logger.info(
                    f"Health check completed: {results['success_rate']:.1f}% success rate "
                    f"({results['healthy_checks']}/{results['total_checks']} checks passed)"
                )
                
                # Log alerts
                if results['alerts']:
                    for alert in results['alerts']:
                        logger.warning(f"ALERT: {alert['message']} ({alert['consecutive_failures']} consecutive failures)")
                
                await asyncio.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error during monitoring: {str(e)}")
                await asyncio.sleep(interval)

def main():
    """Command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AutoScraper Health Monitor")
    parser.add_argument("command", choices=["check", "monitor", "summary"],
                       help="Command to execute")
    parser.add_argument("--service-url", default=SERVICE_URL, help="AutoScraper service URL")
    parser.add_argument("--main-app-url", default=MAIN_APP_URL, help="Main app URL")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL, help="Monitoring interval (seconds)")
    parser.add_argument("--hours", type=int, default=1, help="Hours for summary")
    parser.add_argument("--output", help="Output file for results")
    
    args = parser.parse_args()
    
    monitor = HealthMonitor(args.service_url, args.main_app_url)
    
    if args.command == "check":
        results = monitor.run_all_checks()
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {args.output}")
        else:
            print(json.dumps(results, indent=2))
    
    elif args.command == "monitor":
        try:
            asyncio.run(monitor.monitor_continuously(args.interval))
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
    
    elif args.command == "summary":
        summary = monitor.get_health_summary(args.hours)
        
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(summary, f, indent=2)
            print(f"Summary saved to {args.output}")
        else:
            print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()