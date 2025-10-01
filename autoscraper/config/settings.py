#!/usr/bin/env python3
"""
Autoscraper Service Configuration
Enterprise-grade configuration management
"""

import os
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings
from pathlib import Path


class AutoscraperSettings(BaseSettings):
    """Autoscraper service configuration"""
    
    # Service Configuration
    SERVICE_NAME: str = "remotehive-autoscraper"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    WORKERS: int = 4
    ENVIRONMENT: str = "development"
    
    # Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    JWT_ISSUER: str = os.getenv("JWT_ISSUER", "RemoteHive")  # Match main backend issuer
    JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "RemoteHive-Services")  # Match main backend audience
    ALLOWED_HOSTS: List[str] = ["localhost", "127.0.0.1", "*.remotehive.com"]
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ]
    
    # Database Configuration
    DATABASE_URL: Optional[str] = None  # For SQLite fallback
    
    # MongoDB Atlas Configuration
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017/remotehive")
    MONGODB_DATABASE_NAME: str = os.getenv("MONGODB_DATABASE_NAME", "remotehive_autoscraper")
    MONGODB_MAX_POOL_SIZE: int = int(os.getenv("MONGODB_MAX_POOL_SIZE", "50"))
    MONGODB_MIN_POOL_SIZE: int = int(os.getenv("MONGODB_MIN_POOL_SIZE", "5"))
    MONGODB_SERVER_SELECTION_TIMEOUT: int = int(os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT", "10000"))
    MONGODB_CONNECT_TIMEOUT: int = int(os.getenv("MONGODB_CONNECT_TIMEOUT", "15000"))
    MONGODB_SOCKET_TIMEOUT: int = int(os.getenv("MONGODB_SOCKET_TIMEOUT", "30000"))
    DB_SLOW_QUERY_THRESHOLD: float = float(os.getenv("DB_SLOW_QUERY_THRESHOLD", "1.0"))
    
    # Redis Configuration (for rate limiting and caching)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    REDIS_POOL_SIZE: int = int(os.getenv("REDIS_POOL_SIZE", "10"))
    
    # Celery Configuration
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_ENABLE_UTC: bool = True
    
    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None
    LOG_FORMAT: str = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    LOG_ROTATION: str = "10 MB"
    LOG_RETENTION: str = "30 days"
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_WINDOW: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60  # seconds
    
    # Health Check Configuration
    HEALTH_CHECK_TIMEOUT: int = 30
    HEALTH_CHECK_INTERVAL: int = 60
    
    # Monitoring
    METRICS_ENABLED: bool = True
    METRICS_PATH: str = "/metrics"
    
    # Service Discovery
    MAIN_SERVICE_URL: str = os.getenv("MAIN_SERVICE_URL", "http://localhost:8000")
    MAIN_SERVICE_HEALTH_ENDPOINT: str = os.getenv("MAIN_SERVICE_HEALTH_ENDPOINT", "/health")
    ADMIN_SERVICE_URL: str = os.getenv("ADMIN_SERVICE_URL", "http://localhost:8002")
    ADMIN_SERVICE_HEALTH_ENDPOINT: str = os.getenv("ADMIN_SERVICE_HEALTH_ENDPOINT", "/health")
    
    # Scraping Configuration
    SCRAPE_TIMEOUT: int = int(os.getenv("SCRAPE_TIMEOUT", "30"))
    SCRAPE_RETRY_ATTEMPTS: int = int(os.getenv("SCRAPE_RETRY_ATTEMPTS", "3"))
    SCRAPE_DELAY_BETWEEN_REQUESTS: int = int(os.getenv("SCRAPE_DELAY_BETWEEN_REQUESTS", "1"))
    SCRAPE_USER_AGENT: str = os.getenv("SCRAPE_USER_AGENT", "RemoteHive-AutoScraper/1.0")
    
    # Playwright Configuration
    PLAYWRIGHT_HEADLESS: bool = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    PLAYWRIGHT_TIMEOUT: int = int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000"))
    PLAYWRIGHT_VIEWPORT_WIDTH: int = int(os.getenv("PLAYWRIGHT_VIEWPORT_WIDTH", "1920"))
    PLAYWRIGHT_VIEWPORT_HEIGHT: int = int(os.getenv("PLAYWRIGHT_VIEWPORT_HEIGHT", "1080"))
    
    # Anti-Bot Configuration
    USE_PROXY: bool = os.getenv("USE_PROXY", "false").lower() == "true"
    PROXY_URL: str = os.getenv("PROXY_URL", "")
    ROTATE_USER_AGENTS: bool = os.getenv("ROTATE_USER_AGENTS", "true").lower() == "true"
    RANDOM_DELAYS: bool = os.getenv("RANDOM_DELAYS", "true").lower() == "true"
    
    # OpenRouter AI Configuration
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-nemo:free")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MAX_TOKENS: int = int(os.getenv("OPENROUTER_MAX_TOKENS", "4096"))
    OPENROUTER_TEMPERATURE: float = float(os.getenv("OPENROUTER_TEMPERATURE", "0.3"))
    OPENROUTER_TIMEOUT: int = int(os.getenv("OPENROUTER_TIMEOUT", "30"))
    
    # Performance Configuration
    MAX_CONCURRENT_SCRAPES: int = int(os.getenv("MAX_CONCURRENT_SCRAPES", "5"))
    MEMORY_LIMIT_MB: int = int(os.getenv("MEMORY_LIMIT_MB", "512"))
    CPU_LIMIT_PERCENT: int = int(os.getenv("CPU_LIMIT_PERCENT", "80"))
    
    # Development Settings
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    TESTING: bool = os.getenv("TESTING", "false").lower() == "true"
    RELOAD: bool = os.getenv("RELOAD", "false").lower() == "true"
    
    # File Paths
    BASE_DIR: Path = Path(__file__).parent.parent
    CONFIG_DIR: Path = BASE_DIR / "config"
    LOGS_DIR: Path = BASE_DIR / "logs"
    SCRIPTS_DIR: Path = BASE_DIR / "scripts"
    
    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v):
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v):
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v.upper()
    
    @field_validator("PORT")
    @classmethod
    def validate_port(cls, v):
        if not 1024 <= v <= 65535:
            raise ValueError("Port must be between 1024 and 65535")
        return v
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Create directories if they don't exist
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Set log file path if not provided
        if not self.LOG_FILE and self.ENVIRONMENT != "development":
            self.LOG_FILE = str(self.LOGS_DIR / f"{self.SERVICE_NAME}.log")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        # Environment variable prefixes
        env_prefix = "AUTOSCRAPER_"


# Create settings instance
settings = AutoscraperSettings()


# Environment-specific configurations
if settings.ENVIRONMENT == "production":
    # Production overrides
    settings.LOG_LEVEL = "WARNING"
    settings.WORKERS = max(4, os.cpu_count() or 4)
    settings.RATE_LIMIT_REQUESTS_PER_WINDOW = 1000
    settings.MONGODB_MAX_POOL_SIZE = 100
    settings.MONGODB_MIN_POOL_SIZE = 10
    
elif settings.ENVIRONMENT == "staging":
    # Staging overrides
    settings.LOG_LEVEL = "INFO"
    settings.WORKERS = 2
    settings.RATE_LIMIT_REQUESTS_PER_WINDOW = 500
    
elif settings.ENVIRONMENT == "development":
    # Development overrides
    settings.LOG_LEVEL = "DEBUG"
    settings.WORKERS = 1
    settings.RATE_LIMIT_ENABLED = False
    settings.CORS_ORIGINS.extend([
        "http://localhost:8080",
        "http://localhost:4200"
    ])


def get_settings() -> AutoscraperSettings:
    """Get application settings"""
    return settings