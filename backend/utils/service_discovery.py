#!/usr/bin/env python3
"""
Service Discovery and Health Check Utilities
Enables reliable communication between RemoteHive services
"""

import asyncio
import aiohttp
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from loguru import logger
import os
from enum import Enum


class ServiceStatus(Enum):
    """Service health status enumeration"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    STARTING = "starting"
    STOPPING = "stopping"


@dataclass
class ServiceInfo:
    """Service information and health status"""
    name: str
    url: str
    health_endpoint: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_check: Optional[datetime] = None
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    consecutive_failures: int = 0
    metadata: Dict = field(default_factory=dict)

    @property
    def health_url(self) -> str:
        """Get the full health check URL"""
        return f"{self.url.rstrip('/')}{self.health_endpoint}"

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy"""
        return self.status == ServiceStatus.HEALTHY

    def update_health(self, status: ServiceStatus, response_time: Optional[float] = None, error: Optional[str] = None):
        """Update service health status"""
        self.status = status
        self.last_check = datetime.now()
        self.response_time = response_time
        self.error_message = error
        
        if status == ServiceStatus.HEALTHY:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1


class ServiceRegistry:
    """Service registry for managing service discovery"""
    
    def __init__(self):
        self.services: Dict[str, ServiceInfo] = {}
        self._load_services_from_env()
    
    def _load_services_from_env(self):
        """Load service configurations from environment variables"""
        # Main Service
        main_url = os.getenv("MAIN_SERVICE_URL", "http://localhost:8000")
        main_health = os.getenv("MAIN_SERVICE_HEALTH_ENDPOINT", "/health")
        self.register_service("main", main_url, main_health)
        
        # AutoScraper Service
        autoscraper_url = os.getenv("AUTOSCRAPER_SERVICE_URL", "http://localhost:8001")
        autoscraper_health = os.getenv("AUTOSCRAPER_SERVICE_HEALTH_ENDPOINT", "/health")
        self.register_service("autoscraper", autoscraper_url, autoscraper_health)
        
        # Admin Service
        admin_url = os.getenv("ADMIN_SERVICE_URL", "http://localhost:8002")
        admin_health = os.getenv("ADMIN_SERVICE_HEALTH_ENDPOINT", "/health")
        self.register_service("admin", admin_url, admin_health)
        
        logger.info(f"Loaded {len(self.services)} services from environment")
    
    def register_service(self, name: str, url: str, health_endpoint: str, metadata: Optional[Dict] = None) -> ServiceInfo:
        """Register a new service"""
        service = ServiceInfo(
            name=name,
            url=url,
            health_endpoint=health_endpoint,
            metadata=metadata or {}
        )
        self.services[name] = service
        logger.info(f"Registered service: {name} at {url}")
        return service
    
    def get_service(self, name: str) -> Optional[ServiceInfo]:
        """Get service information by name"""
        return self.services.get(name)
    
    def get_healthy_services(self) -> List[ServiceInfo]:
        """Get list of healthy services"""
        return [service for service in self.services.values() if service.is_healthy]
    
    def get_all_services(self) -> List[ServiceInfo]:
        """Get all registered services"""
        return list(self.services.values())


class HealthChecker:
    """Health checker for monitoring service availability"""
    
    def __init__(self, registry: ServiceRegistry, timeout: int = 30):
        self.registry = registry
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def check_service_health(self, service: ServiceInfo) -> ServiceStatus:
        """Check health of a single service"""
        if not self.session:
            raise RuntimeError("HealthChecker must be used as async context manager")
        
        start_time = time.time()
        
        try:
            async with self.session.get(service.health_url) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    # Try to parse response for additional info
                    try:
                        data = await response.json()
                        service.metadata.update(data)
                    except:
                        pass  # Ignore JSON parsing errors
                    
                    service.update_health(ServiceStatus.HEALTHY, response_time)
                    logger.debug(f"Service {service.name} is healthy (response time: {response_time:.3f}s)")
                    return ServiceStatus.HEALTHY
                else:
                    error_msg = f"HTTP {response.status}"
                    service.update_health(ServiceStatus.UNHEALTHY, response_time, error_msg)
                    logger.warning(f"Service {service.name} returned {response.status}")
                    return ServiceStatus.UNHEALTHY
        
        except asyncio.TimeoutError:
            error_msg = f"Timeout after {self.timeout}s"
            service.update_health(ServiceStatus.UNHEALTHY, None, error_msg)
            logger.warning(f"Service {service.name} health check timed out")
            return ServiceStatus.UNHEALTHY
        
        except Exception as e:
            error_msg = str(e)
            service.update_health(ServiceStatus.UNHEALTHY, None, error_msg)
            logger.warning(f"Service {service.name} health check failed: {error_msg}")
            return ServiceStatus.UNHEALTHY
    
    async def check_all_services(self) -> Dict[str, ServiceStatus]:
        """Check health of all registered services"""
        results = {}
        
        # Create tasks for concurrent health checks
        tasks = []
        for service in self.registry.get_all_services():
            task = asyncio.create_task(self.check_service_health(service))
            tasks.append((service.name, task))
        
        # Wait for all health checks to complete
        for service_name, task in tasks:
            try:
                status = await task
                results[service_name] = status
            except Exception as e:
                logger.error(f"Failed to check health of {service_name}: {e}")
                results[service_name] = ServiceStatus.UNKNOWN
        
        return results


class ServiceCommunicator:
    """Handles communication between services with retry logic"""
    
    def __init__(self, registry: ServiceRegistry, max_retries: int = 3, retry_delay: float = 1.0):
        self.registry = registry
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def call_service(self, service_name: str, endpoint: str, method: str = "GET", 
                          data: Optional[Dict] = None, headers: Optional[Dict] = None,
                          timeout: int = 30) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """Call a service endpoint with retry logic"""
        if not self.session:
            raise RuntimeError("ServiceCommunicator must be used as async context manager")
        
        service = self.registry.get_service(service_name)
        if not service:
            return False, None, f"Service {service_name} not found"
        
        if not service.is_healthy:
            return False, None, f"Service {service_name} is not healthy"
        
        url = f"{service.url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        for attempt in range(self.max_retries + 1):
            try:
                async with self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status < 400:
                        try:
                            result = await response.json()
                            return True, result, None
                        except:
                            # Return text if not JSON
                            result = await response.text()
                            return True, {"response": result}, None
                    else:
                        error_msg = f"HTTP {response.status}: {await response.text()}"
                        if attempt == self.max_retries:
                            return False, None, error_msg
            
            except Exception as e:
                error_msg = str(e)
                if attempt == self.max_retries:
                    return False, None, error_msg
            
            # Wait before retry
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * (attempt + 1))
                logger.debug(f"Retrying call to {service_name}/{endpoint} (attempt {attempt + 2})")
        
        return False, None, "Max retries exceeded"


# Global service registry instance
_service_registry = None


def get_service_registry() -> ServiceRegistry:
    """Get the global service registry instance"""
    global _service_registry
    if _service_registry is None:
        _service_registry = ServiceRegistry()
    return _service_registry


async def wait_for_service(service_name: str, timeout: int = 60, check_interval: int = 5) -> bool:
    """Wait for a service to become healthy"""
    registry = get_service_registry()
    service = registry.get_service(service_name)
    
    if not service:
        logger.error(f"Service {service_name} not found in registry")
        return False
    
    start_time = time.time()
    
    async with HealthChecker(registry) as health_checker:
        while time.time() - start_time < timeout:
            status = await health_checker.check_service_health(service)
            
            if status == ServiceStatus.HEALTHY:
                logger.info(f"Service {service_name} is now healthy")
                return True
            
            logger.debug(f"Waiting for service {service_name} to become healthy...")
            await asyncio.sleep(check_interval)
    
    logger.error(f"Service {service_name} did not become healthy within {timeout} seconds")
    return False


async def wait_for_all_services(timeout: int = 120, check_interval: int = 10) -> bool:
    """Wait for all registered services to become healthy"""
    registry = get_service_registry()
    services = registry.get_all_services()
    
    if not services:
        logger.warning("No services registered")
        return True
    
    start_time = time.time()
    
    async with HealthChecker(registry) as health_checker:
        while time.time() - start_time < timeout:
            results = await health_checker.check_all_services()
            
            healthy_count = sum(1 for status in results.values() if status == ServiceStatus.HEALTHY)
            total_count = len(results)
            
            logger.info(f"Service health: {healthy_count}/{total_count} services healthy")
            
            if healthy_count == total_count:
                logger.info("All services are healthy")
                return True
            
            # Log unhealthy services
            for service_name, status in results.items():
                if status != ServiceStatus.HEALTHY:
                    service = registry.get_service(service_name)
                    error_msg = service.error_message if service else "Unknown error"
                    logger.debug(f"Service {service_name} is {status.value}: {error_msg}")
            
            await asyncio.sleep(check_interval)
    
    logger.error(f"Not all services became healthy within {timeout} seconds")
    return False