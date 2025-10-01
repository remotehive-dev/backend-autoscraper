#!/usr/bin/env python3
"""
Settings Service for AutoScraper
Handles system settings management
"""

from typing import Dict, Any
from loguru import logger

from app.schemas import SystemSettings, SystemSettingsUpdate
from config.settings import get_settings


class SettingsService:
    """Service for managing system settings"""
    
    def __init__(self):
        self.config_settings = get_settings()
        self._current_settings = None
        self._load_default_settings()
    
    def _load_default_settings(self):
        """Load default settings from configuration"""
        self._current_settings = SystemSettings(
            # Rate Limiting
            global_rate_limit=100,
            requests_per_minute=60,
            burst_limit=10,
            cooldown_period=300,
            
            # Retry Policy
            max_retries=3,
            retry_delay=5000,
            exponential_backoff=True,
            retry_on_errors=["TIMEOUT", "CONNECTION_ERROR", "RATE_LIMITED"],
            
            # Performance
            max_concurrent_jobs=getattr(self.config_settings, 'MAX_CONCURRENT_JOBS', 5),
            job_timeout=300000,
            memory_limit=1024,
            disk_space_threshold=85,
            
            # Data Management
            data_retention_days=90,
            auto_cleanup=True,
            compress_old_data=True,
            backup_enabled=False,
            
            # Notifications
            email_notifications=False,
            slack_notifications=False,
            webhook_notifications=False,
            
            # Monitoring
            health_check_interval=30,
            metrics_retention=7,
            log_level="info",
            enable_debug_mode=self.config_settings.ENVIRONMENT == "development",
            
            # Security
            api_key_rotation=False,
            encrypt_data=True,
            audit_logging=True,
            ip_whitelist=[]
        )
    
    def get_settings(self) -> SystemSettings:
        """Get current system settings"""
        logger.debug("Retrieving system settings")
        return self._current_settings
    
    def update_settings(self, updates: Dict[str, Any]) -> SystemSettings:
        """Update system settings"""
        logger.info(f"Updating system settings: {list(updates.keys())}")
        
        try:
            # Create update object
            settings_update = SystemSettingsUpdate(**updates)
            
            # Apply updates to current settings
            current_dict = self._current_settings.dict()
            
            for key, value in updates.items():
                if value is not None and hasattr(self._current_settings, key):
                    current_dict[key] = value
                    logger.debug(f"Updated setting {key} = {value}")
            
            # Create new settings object with updates
            self._current_settings = SystemSettings(**current_dict)
            
            logger.info("System settings updated successfully")
            return self._current_settings
            
        except Exception as e:
            logger.error(f"Failed to update settings: {str(e)}")
            raise ValueError(f"Invalid settings update: {str(e)}")
    
    def reset_settings(self) -> SystemSettings:
        """Reset settings to defaults"""
        logger.info("Resetting system settings to defaults")
        self._load_default_settings()
        return self._current_settings


# Global settings service instance
settings_service = SettingsService()