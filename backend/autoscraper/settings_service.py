import json
import os
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import psutil
from pathlib import Path

from backend.schemas import SystemSettings, SystemSettingsUpdate, SettingsTestResponse, SystemHealthResponse, PerformanceMetrics
from backend.core.config import settings
import logging

logger = logging.getLogger(__name__)

class AutoScraperSettingsService:
    def __init__(self):
        self.config = settings
        self.settings_file = Path("autoscraper_settings.json")
        self._current_settings: Optional[SystemSettings] = None
        self._load_settings()
    
    def _load_settings(self) -> SystemSettings:
        """Load settings from file or create default settings"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                    # Convert camelCase to snake_case for backend compatibility
                    converted_data = self._convert_camel_to_snake(data)
                    self._current_settings = SystemSettings(**converted_data)
                    logger.info("Loaded autoscraper settings from file")
            else:
                self._current_settings = SystemSettings()
                self._save_settings()
                logger.info("Created default autoscraper settings")
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self._current_settings = SystemSettings()
            self._save_settings()
        
        return self._current_settings
    
    def _save_settings(self) -> None:
        """Save current settings to file"""
        try:
            if self._current_settings:
                # Convert snake_case to camelCase for frontend compatibility
                data = self._convert_snake_to_camel(self._current_settings.dict())
                with open(self.settings_file, 'w') as f:
                    json.dump(data, f, indent=2)
                logger.info("Saved autoscraper settings to file")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
    
    def _convert_camel_to_snake(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert camelCase keys to snake_case"""
        def camel_to_snake(name: str) -> str:
            import re
            s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
            return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
        
        converted = {}
        for key, value in data.items():
            snake_key = camel_to_snake(key)
            if isinstance(value, dict):
                converted[snake_key] = self._convert_camel_to_snake(value)
            else:
                converted[snake_key] = value
        return converted
    
    def _convert_snake_to_camel(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert snake_case keys to camelCase"""
        def snake_to_camel(name: str) -> str:
            components = name.split('_')
            return components[0] + ''.join(x.capitalize() for x in components[1:])
        
        converted = {}
        for key, value in data.items():
            camel_key = snake_to_camel(key)
            if isinstance(value, dict):
                converted[camel_key] = self._convert_snake_to_camel(value)
            else:
                converted[camel_key] = value
        return converted
    
    async def get_settings(self) -> SystemSettings:
        """Get current system settings"""
        if not self._current_settings:
            self._load_settings()
        return self._current_settings
    
    async def update_settings(self, settings_update: SystemSettingsUpdate) -> SystemSettings:
        """Update system settings"""
        try:
            if not self._current_settings:
                self._load_settings()
            
            # Update only provided fields
            update_data = settings_update.dict(exclude_unset=True)
            current_data = self._current_settings.dict()
            current_data.update(update_data)
            
            self._current_settings = SystemSettings(**current_data)
            self._save_settings()
            
            logger.info("Updated autoscraper settings")
            return self._current_settings
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            raise
    
    async def reset_settings(self) -> SystemSettings:
        """Reset settings to default values"""
        try:
            self._current_settings = SystemSettings()
            self._save_settings()
            logger.info("Reset autoscraper settings to defaults")
            return self._current_settings
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            raise
    
    async def test_settings(self, test_type: str, settings: Optional[SystemSettings] = None) -> SettingsTestResponse:
        """Test specific settings configuration"""
        try:
            test_settings = settings or self._current_settings or SystemSettings()
            
            if test_type == "rate_limit":
                return await self._test_rate_limit(test_settings)
            elif test_type == "memory":
                return await self._test_memory_settings(test_settings)
            elif test_type == "connectivity":
                return await self._test_connectivity(test_settings)
            elif test_type == "all":
                return await self._test_all_settings(test_settings)
            else:
                return SettingsTestResponse(
                    success=False,
                    message=f"Unknown test type: {test_type}"
                )
        except Exception as e:
            logger.error(f"Error testing settings: {e}")
            return SettingsTestResponse(
                success=False,
                message=f"Test failed: {str(e)}"
            )
    
    async def _test_rate_limit(self, settings: SystemSettings) -> SettingsTestResponse:
        """Test rate limiting configuration"""
        try:
            # Simulate rate limit test
            if settings.global_rate_limit > 0 and settings.requests_per_minute > 0:
                return SettingsTestResponse(
                    success=True,
                    message="Rate limiting configuration is valid",
                    details={
                        "global_rate_limit": settings.global_rate_limit,
                        "requests_per_minute": settings.requests_per_minute
                    }
                )
            else:
                return SettingsTestResponse(
                    success=False,
                    message="Invalid rate limiting configuration"
                )
        except Exception as e:
            return SettingsTestResponse(
                success=False,
                message=f"Rate limit test failed: {str(e)}"
            )
    
    async def _test_memory_settings(self, settings: SystemSettings) -> SettingsTestResponse:
        """Test memory configuration"""
        try:
            current_memory = psutil.virtual_memory()
            available_mb = current_memory.available // (1024 * 1024)
            
            if settings.memory_limit <= available_mb:
                return SettingsTestResponse(
                    success=True,
                    message="Memory configuration is valid",
                    details={
                        "configured_limit_mb": settings.memory_limit,
                        "available_memory_mb": available_mb
                    }
                )
            else:
                return SettingsTestResponse(
                    success=False,
                    message=f"Memory limit ({settings.memory_limit}MB) exceeds available memory ({available_mb}MB)"
                )
        except Exception as e:
            return SettingsTestResponse(
                success=False,
                message=f"Memory test failed: {str(e)}"
            )
    
    async def _test_connectivity(self, settings: SystemSettings) -> SettingsTestResponse:
        """Test connectivity and network settings"""
        try:
            # Basic connectivity test
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('https://httpbin.org/status/200', timeout=5) as response:
                    if response.status == 200:
                        return SettingsTestResponse(
                            success=True,
                            message="Connectivity test passed",
                            details={"response_time_ms": "< 5000"}
                        )
                    else:
                        return SettingsTestResponse(
                            success=False,
                            message=f"Connectivity test failed with status {response.status}"
                        )
        except Exception as e:
            return SettingsTestResponse(
                success=False,
                message=f"Connectivity test failed: {str(e)}"
            )
    
    async def _test_all_settings(self, settings: SystemSettings) -> SettingsTestResponse:
        """Run all available tests"""
        try:
            tests = [
                await self._test_rate_limit(settings),
                await self._test_memory_settings(settings),
                await self._test_connectivity(settings)
            ]
            
            failed_tests = [test for test in tests if not test.success]
            
            if not failed_tests:
                return SettingsTestResponse(
                    success=True,
                    message="All tests passed",
                    details={"total_tests": len(tests), "passed": len(tests)}
                )
            else:
                return SettingsTestResponse(
                    success=False,
                    message=f"{len(failed_tests)} out of {len(tests)} tests failed",
                    details={
                        "total_tests": len(tests),
                        "passed": len(tests) - len(failed_tests),
                        "failed": len(failed_tests),
                        "failures": [test.message for test in failed_tests]
                    }
                )
        except Exception as e:
            return SettingsTestResponse(
                success=False,
                message=f"Test suite failed: {str(e)}"
            )
    
    async def get_system_health(self) -> SystemHealthResponse:
        """Get current system health status"""
        try:
            # Get system metrics
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            disk = psutil.disk_usage('/')
            
            # Calculate uptime (simplified)
            import time
            uptime = int(time.time() - psutil.boot_time())
            
            return SystemHealthResponse(
                status="healthy" if cpu_percent < 80 and memory.percent < 90 else "warning",
                uptime=uptime,
                memory_usage=memory.percent,
                cpu_usage=cpu_percent,
                disk_usage=disk.percent,
                active_jobs=0,  # TODO: Implement job tracking
                queue_size=0,   # TODO: Implement queue tracking
                last_check=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            raise
    
    async def get_performance_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics"""
        try:
            # Get system metrics
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            disk = psutil.disk_usage('/')
            
            return PerformanceMetrics(
                requests_per_second=0.0,  # TODO: Implement request tracking
                average_response_time=0.0,  # TODO: Implement response time tracking
                error_rate=0.0,  # TODO: Implement error tracking
                success_rate=100.0,  # TODO: Implement success tracking
                active_connections=0,  # TODO: Implement connection tracking
                memory_usage_mb=memory.used // (1024 * 1024),
                cpu_usage_percent=cpu_percent,
                disk_usage_percent=disk.percent,
                timestamp=datetime.now().isoformat()
            )
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            raise

# Global instance
settings_service = AutoScraperSettingsService()