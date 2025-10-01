#!/usr/bin/env python3
"""
RemoteHive Centralized Logging Infrastructure
Provides structured logging, error tracking, and monitoring capabilities
"""

import sys
import os
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from contextlib import contextmanager
from functools import wraps
import asyncio
from enum import Enum

from loguru import logger
from pydantic import BaseModel

from backend.core.config import settings


class LogLevel(str, Enum):
    """Log levels enum"""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogContext(BaseModel):
    """Structured log context"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    service_name: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    correlation_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class ErrorInfo(BaseModel):
    """Structured error information"""
    error_type: str
    error_message: str
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Optional[LogContext] = None
    timestamp: datetime
    severity: LogLevel
    resolved: bool = False
    resolution_notes: Optional[str] = None


class LoggingConfig:
    """Centralized logging configuration"""
    
    def __init__(self):
        self.service_name = getattr(settings, 'SERVICE_NAME', 'remotehive')
        self.log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
        self.environment = getattr(settings, 'ENVIRONMENT', 'development')
        self.log_file = getattr(settings, 'LOG_FILE', None)
        self.enable_json_logs = getattr(settings, 'ENABLE_JSON_LOGS', False)
        self.enable_file_logging = getattr(settings, 'ENABLE_FILE_LOGGING', True)
        self.log_rotation = getattr(settings, 'LOG_ROTATION', '10 MB')
        self.log_retention = getattr(settings, 'LOG_RETENTION', '30 days')
        
        # Error tracking
        self.error_tracking_enabled = getattr(settings, 'ERROR_TRACKING_ENABLED', True)
        self.error_log_file = getattr(settings, 'ERROR_LOG_FILE', 'logs/errors.jsonl')
        
        # Performance monitoring
        self.performance_logging = getattr(settings, 'PERFORMANCE_LOGGING', True)
        self.slow_query_threshold = getattr(settings, 'SLOW_QUERY_THRESHOLD', 1.0)
        
    def setup_logging(self):
        """Setup centralized logging configuration"""
        # Remove default logger
        logger.remove()
        
        # Console logging format
        console_format = self._get_console_format()
        file_format = self._get_file_format()
        
        # Add console handler
        logger.add(
            sys.stdout,
            format=console_format,
            level=self.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True
        )
        
        # Add file logging if enabled
        if self.enable_file_logging:
            log_file = self.log_file or f"logs/{self.service_name}.log"
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.add(
                log_file,
                format=file_format,
                level="INFO",
                rotation=self.log_rotation,
                retention=self.log_retention,
                compression="zip",
                backtrace=True,
                diagnose=True
            )
        
        # Add error tracking file
        if self.error_tracking_enabled:
            error_log_path = Path(self.error_log_file)
            error_log_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.add(
                self.error_log_file,
                format="{message}",
                level="ERROR",
                rotation=self.log_rotation,
                retention=self.log_retention,
                serialize=True,  # JSON format for structured error tracking
                backtrace=True,
                diagnose=True
            )
        
        # Add service context
        logger.configure(extra={
            "service": self.service_name,
            "environment": self.environment
        })
        
        logger.info(f"Logging initialized for {self.service_name} in {self.environment} mode")
    
    def _get_console_format(self) -> str:
        """Get console logging format"""
        if self.environment == "development":
            return (
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            )
        else:
            return (
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}"
            )
    
    def _get_file_format(self) -> str:
        """Get file logging format"""
        if self.enable_json_logs:
            return "{message}"
        else:
            return (
                "{time:YYYY-MM-DD HH:mm:ss} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{extra[service]} | "
                "{message}"
            )


class StructuredLogger:
    """Enhanced structured logger with context management"""
    
    def __init__(self, name: str = None):
        self.name = name or "remotehive"
        self.context: LogContext = LogContext()
        self._error_count = 0
        self._warning_count = 0
    
    def set_context(self, **kwargs):
        """Set logging context"""
        for key, value in kwargs.items():
            if hasattr(self.context, key):
                setattr(self.context, key, value)
    
    def clear_context(self):
        """Clear logging context"""
        self.context = LogContext()
    
    @contextmanager
    def context_manager(self, **kwargs):
        """Context manager for temporary context"""
        old_context = self.context.copy()
        try:
            self.set_context(**kwargs)
            yield self
        finally:
            self.context = old_context
    
    def _log_with_context(self, level: str, message: str, **kwargs):
        """Log with context information"""
        extra_data = {
            "context": self.context.dict(exclude_none=True),
            **kwargs
        }
        
        getattr(logger, level.lower())(message, **extra_data)
    
    def trace(self, message: str, **kwargs):
        """Log trace message"""
        self._log_with_context("TRACE", message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log_with_context("DEBUG", message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log_with_context("INFO", message, **kwargs)
    
    def success(self, message: str, **kwargs):
        """Log success message"""
        self._log_with_context("SUCCESS", message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._warning_count += 1
        self._log_with_context("WARNING", message, **kwargs)
    
    def error(self, message: str, error: Exception = None, **kwargs):
        """Log error message with optional exception"""
        self._error_count += 1
        
        error_info = None
        if error:
            error_info = ErrorInfo(
                error_type=type(error).__name__,
                error_message=str(error),
                stack_trace=traceback.format_exc(),
                context=self.context,
                timestamp=datetime.now(),
                severity=LogLevel.ERROR
            )
            kwargs["error_info"] = error_info.dict()
        
        self._log_with_context("ERROR", message, **kwargs)
    
    def critical(self, message: str, error: Exception = None, **kwargs):
        """Log critical message"""
        self._error_count += 1
        
        error_info = None
        if error:
            error_info = ErrorInfo(
                error_type=type(error).__name__,
                error_message=str(error),
                stack_trace=traceback.format_exc(),
                context=self.context,
                timestamp=datetime.now(),
                severity=LogLevel.CRITICAL
            )
            kwargs["error_info"] = error_info.dict()
        
        self._log_with_context("CRITICAL", message, **kwargs)
    
    def get_stats(self) -> Dict[str, int]:
        """Get logging statistics"""
        return {
            "error_count": self._error_count,
            "warning_count": self._warning_count
        }


class PerformanceLogger:
    """Performance monitoring and logging"""
    
    def __init__(self, logger_instance: StructuredLogger):
        self.logger = logger_instance
        self.slow_query_threshold = getattr(settings, 'SLOW_QUERY_THRESHOLD', 1.0)
    
    @contextmanager
    def time_operation(self, operation_name: str, **context):
        """Time an operation and log if it's slow"""
        start_time = datetime.now()
        try:
            yield
        finally:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if duration > self.slow_query_threshold:
                self.logger.warning(
                    f"Slow operation detected: {operation_name}",
                    duration=duration,
                    operation=operation_name,
                    **context
                )
            else:
                self.logger.debug(
                    f"Operation completed: {operation_name}",
                    duration=duration,
                    operation=operation_name,
                    **context
                )
    
    def log_database_query(self, query: str, duration: float, **context):
        """Log database query performance"""
        if duration > self.slow_query_threshold:
            self.logger.warning(
                "Slow database query detected",
                query=query[:200] + "..." if len(query) > 200 else query,
                duration=duration,
                **context
            )
        else:
            self.logger.debug(
                "Database query executed",
                duration=duration,
                **context
            )
    
    def log_api_request(self, method: str, endpoint: str, status_code: int, 
                       duration: float, **context):
        """Log API request performance"""
        level = "info"
        if status_code >= 500:
            level = "error"
        elif status_code >= 400:
            level = "warning"
        elif duration > self.slow_query_threshold:
            level = "warning"
        
        getattr(self.logger, level)(
            f"API request: {method} {endpoint}",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration=duration,
            **context
        )


def log_exceptions(logger_instance: StructuredLogger = None):
    """Decorator to automatically log exceptions"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if logger_instance:
                    logger_instance.error(f"Exception in {func.__name__}", error=e)
                else:
                    logger.error(f"Exception in {func.__name__}: {e}")
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if logger_instance:
                    logger_instance.error(f"Exception in {func.__name__}", error=e)
                else:
                    logger.error(f"Exception in {func.__name__}: {e}")
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# Global logging instances
logging_config = LoggingConfig()
structured_logger = StructuredLogger()
performance_logger = PerformanceLogger(structured_logger)


def setup_logging():
    """Setup centralized logging for the application"""
    logging_config.setup_logging()
    return structured_logger


def get_logger(name: str = None) -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)


# Export commonly used functions
__all__ = [
    'LogLevel',
    'LogContext', 
    'ErrorInfo',
    'StructuredLogger',
    'PerformanceLogger',
    'setup_logging',
    'get_logger',
    'log_exceptions',
    'structured_logger',
    'performance_logger'
]