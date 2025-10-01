"""Performance tracking module for the autoscraper engine.

This module provides comprehensive performance monitoring capabilities
for web scraping operations, including:

- Session-based performance tracking
- System resource monitoring
- Metric collection and aggregation
- Error tracking and reporting
- Performance analytics and insights
"""

from backend.performance.tracker import (
    PerformanceTracker,
    PerformanceContext,
    ScrapingSession,
    PerformanceMetric,
    MetricType,
    performance_tracker,
    track_performance
)

__all__ = [
    'PerformanceTracker',
    'PerformanceContext', 
    'ScrapingSession',
    'PerformanceMetric',
    'MetricType',
    'performance_tracker',
    'track_performance'
]

__version__ = '1.0.0'