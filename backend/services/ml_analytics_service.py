from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import json
import statistics
import logging
from collections import defaultdict, Counter

try:
    from backend.database.database import get_db_session
    # TODO: MongoDB Migration - Update imports to use MongoDB models
    # from backend.database.models import AnalyticsMetrics, ScraperConfig, ScraperLog
    from backend.models.mongodb_models import AnalyticsMetrics, ScraperConfig, ScraperLog
except ImportError:
    # Fallback for testing
    get_db_session = None
    AnalyticsMetrics = None
    ScraperConfig = None
    ScraperLog = None

class MetricType(Enum):
    """Types of ML analytics metrics"""
    PARSING_ACCURACY = "parsing_accuracy"
    CONFIDENCE_SCORE = "confidence_score"
    FIELD_EXTRACTION_SUCCESS = "field_extraction_success"
    VALIDATION_SCORE = "validation_score"
    PROCESSING_TIME = "processing_time"
    ERROR_RATE = "error_rate"
    QUALITY_SCORE = "quality_score"
    GEMINI_API_USAGE = "gemini_api_usage"
    COST_METRICS = "cost_metrics"

class TimeRange(Enum):
    """Time ranges for analytics"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

@dataclass
class MLMetric:
    """Individual ML parsing metric"""
    metric_type: MetricType
    value: Union[float, int, str]
    config_id: int
    source: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

@dataclass
class MLAnalyticsSummary:
    """Summary of ML analytics for a time period"""
    config_id: int
    source: str
    time_range: TimeRange
    start_date: datetime
    end_date: datetime
    total_jobs_processed: int
    average_confidence_score: float
    average_quality_score: float
    success_rate: float
    error_rate: float
    average_processing_time: float
    field_extraction_rates: Dict[str, float]
    validation_scores: Dict[str, float]
    cost_metrics: Dict[str, float]
    trends: Dict[str, List[float]]

@dataclass
class PerformanceInsight:
    """Performance insight and recommendation"""
    insight_type: str
    severity: str  # low, medium, high
    title: str
    description: str
    recommendation: str
    affected_configs: List[int]
    metric_values: Dict[str, float]
    confidence: float

class MLAnalyticsService:
    """Service for ML parsing analytics and insights"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._metric_cache = defaultdict(list)
        self._cache_ttl = timedelta(minutes=15)
        self._last_cache_update = datetime.now()
    
    async def record_ml_metric(self, metric: MLMetric) -> Dict[str, Any]:
        """Record a single ML parsing metric"""
        try:
            # Store in database
            if get_db_session and AnalyticsMetrics:
                with get_db_session() as db:
                    analytics_record = AnalyticsMetrics(
                        scraper_config_id=metric.config_id,
                        metric_type=metric.metric_type.value,
                        metric_value=float(metric.value) if isinstance(metric.value, (int, float)) else 0.0,
                        metadata=json.dumps({
                            'source': metric.source,
                            'session_id': metric.session_id,
                            'original_value': metric.value,
                            **(metric.metadata or {})
                        }),
                        created_at=metric.timestamp
                    )
                    db.add(analytics_record)
                    db.commit()
            
            # Update cache
            cache_key = f"{metric.config_id}_{metric.metric_type.value}"
            self._metric_cache[cache_key].append(metric)
            
            # Keep cache size manageable
            if len(self._metric_cache[cache_key]) > 1000:
                self._metric_cache[cache_key] = self._metric_cache[cache_key][-500:]
            
            return {'success': True, 'metric_id': f"{metric.config_id}_{metric.timestamp.isoformat()}"}
            
        except Exception as e:
            self.logger.error(f"Error recording ML metric: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def record_parsing_session(self, config_id: int, source: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record metrics for a complete parsing session"""
        try:
            session_id = session_data.get('session_id', f"{config_id}_{datetime.now().isoformat()}")
            timestamp = datetime.now()
            
            metrics_to_record = []
            
            # Record confidence scores
            if 'confidence_scores' in session_data:
                for score in session_data['confidence_scores']:
                    metrics_to_record.append(MLMetric(
                        metric_type=MetricType.CONFIDENCE_SCORE,
                        value=score,
                        config_id=config_id,
                        source=source,
                        timestamp=timestamp,
                        session_id=session_id
                    ))
            
            # Record field extraction success rates
            if 'field_extraction_results' in session_data:
                for field_name, success_rate in session_data['field_extraction_results'].items():
                    metrics_to_record.append(MLMetric(
                        metric_type=MetricType.FIELD_EXTRACTION_SUCCESS,
                        value=success_rate,
                        config_id=config_id,
                        source=source,
                        timestamp=timestamp,
                        session_id=session_id,
                        metadata={'field_name': field_name}
                    ))
            
            # Record validation scores
            if 'validation_scores' in session_data:
                for field_name, score in session_data['validation_scores'].items():
                    metrics_to_record.append(MLMetric(
                        metric_type=MetricType.VALIDATION_SCORE,
                        value=score,
                        config_id=config_id,
                        source=source,
                        timestamp=timestamp,
                        session_id=session_id,
                        metadata={'field_name': field_name}
                    ))
            
            # Record processing time
            if 'processing_time' in session_data:
                metrics_to_record.append(MLMetric(
                    metric_type=MetricType.PROCESSING_TIME,
                    value=session_data['processing_time'],
                    config_id=config_id,
                    source=source,
                    timestamp=timestamp,
                    session_id=session_id
                ))
            
            # Record quality score
            if 'quality_score' in session_data:
                metrics_to_record.append(MLMetric(
                    metric_type=MetricType.QUALITY_SCORE,
                    value=session_data['quality_score'],
                    config_id=config_id,
                    source=source,
                    timestamp=timestamp,
                    session_id=session_id
                ))
            
            # Record API usage
            if 'api_usage' in session_data:
                metrics_to_record.append(MLMetric(
                    metric_type=MetricType.GEMINI_API_USAGE,
                    value=session_data['api_usage'].get('requests', 0),
                    config_id=config_id,
                    source=source,
                    timestamp=timestamp,
                    session_id=session_id,
                    metadata=session_data['api_usage']
                ))
            
            # Record all metrics
            results = []
            for metric in metrics_to_record:
                result = await self.record_ml_metric(metric)
                results.append(result)
            
            successful_records = sum(1 for r in results if r.get('success', False))
            
            return {
                'success': True,
                'session_id': session_id,
                'metrics_recorded': successful_records,
                'total_metrics': len(metrics_to_record)
            }
            
        except Exception as e:
            self.logger.error(f"Error recording parsing session: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def get_analytics_summary(self, config_id: int, time_range: TimeRange, 
                                  start_date: Optional[datetime] = None) -> Optional[MLAnalyticsSummary]:
        """Get analytics summary for a configuration and time range"""
        try:
            # Calculate date range
            end_date = datetime.now()
            if start_date is None:
                if time_range == TimeRange.HOUR:
                    start_date = end_date - timedelta(hours=1)
                elif time_range == TimeRange.DAY:
                    start_date = end_date - timedelta(days=1)
                elif time_range == TimeRange.WEEK:
                    start_date = end_date - timedelta(weeks=1)
                elif time_range == TimeRange.MONTH:
                    start_date = end_date - timedelta(days=30)
                elif time_range == TimeRange.QUARTER:
                    start_date = end_date - timedelta(days=90)
                else:  # YEAR
                    start_date = end_date - timedelta(days=365)
            
            # Get metrics from database
            metrics_data = await self._get_metrics_for_period(config_id, start_date, end_date)
            
            if not metrics_data:
                return None
            
            # Calculate summary statistics
            confidence_scores = [m['value'] for m in metrics_data if m['type'] == MetricType.CONFIDENCE_SCORE.value]
            quality_scores = [m['value'] for m in metrics_data if m['type'] == MetricType.QUALITY_SCORE.value]
            processing_times = [m['value'] for m in metrics_data if m['type'] == MetricType.PROCESSING_TIME.value]
            
            # Calculate field extraction rates
            field_extraction_data = [m for m in metrics_data if m['type'] == MetricType.FIELD_EXTRACTION_SUCCESS.value]
            field_extraction_rates = {}
            for field_data in field_extraction_data:
                field_name = field_data.get('metadata', {}).get('field_name', 'unknown')
                if field_name not in field_extraction_rates:
                    field_extraction_rates[field_name] = []
                field_extraction_rates[field_name].append(field_data['value'])
            
            # Average the rates
            for field_name in field_extraction_rates:
                field_extraction_rates[field_name] = statistics.mean(field_extraction_rates[field_name])
            
            # Calculate validation scores by field
            validation_data = [m for m in metrics_data if m['type'] == MetricType.VALIDATION_SCORE.value]
            validation_scores = {}
            for val_data in validation_data:
                field_name = val_data.get('metadata', {}).get('field_name', 'overall')
                if field_name not in validation_scores:
                    validation_scores[field_name] = []
                validation_scores[field_name].append(val_data['value'])
            
            # Average the validation scores
            for field_name in validation_scores:
                validation_scores[field_name] = statistics.mean(validation_scores[field_name])
            
            # Calculate trends (daily averages)
            trends = await self._calculate_trends(config_id, start_date, end_date)
            
            # Get source from config
            source = "unknown"
            if get_db_session and ScraperConfig:
                with get_db_session() as db:
                    config = db.query(ScraperConfig).filter(ScraperConfig.id == config_id).first()
                    if config:
                        source = config.source or "unknown"
            
            return MLAnalyticsSummary(
                config_id=config_id,
                source=source,
                time_range=time_range,
                start_date=start_date,
                end_date=end_date,
                total_jobs_processed=len(set(m.get('session_id') for m in metrics_data if m.get('session_id'))),
                average_confidence_score=statistics.mean(confidence_scores) if confidence_scores else 0.0,
                average_quality_score=statistics.mean(quality_scores) if quality_scores else 0.0,
                success_rate=len([s for s in confidence_scores if s > 0.7]) / len(confidence_scores) if confidence_scores else 0.0,
                error_rate=len([s for s in confidence_scores if s < 0.3]) / len(confidence_scores) if confidence_scores else 0.0,
                average_processing_time=statistics.mean(processing_times) if processing_times else 0.0,
                field_extraction_rates=field_extraction_rates,
                validation_scores=validation_scores,
                cost_metrics=await self._calculate_cost_metrics(config_id, start_date, end_date),
                trends=trends
            )
            
        except Exception as e:
            self.logger.error(f"Error getting analytics summary: {str(e)}")
            return None
    
    async def get_performance_insights(self, config_ids: Optional[List[int]] = None) -> List[PerformanceInsight]:
        """Generate performance insights and recommendations"""
        try:
            insights = []
            
            # Get recent analytics for all configs or specified configs
            if config_ids is None:
                config_ids = await self._get_all_ml_enabled_configs()
            
            for config_id in config_ids:
                summary = await self.get_analytics_summary(config_id, TimeRange.WEEK)
                if not summary:
                    continue
                
                # Low confidence score insight
                if summary.average_confidence_score < 0.6:
                    insights.append(PerformanceInsight(
                        insight_type="low_confidence",
                        severity="high",
                        title="Low ML Confidence Scores",
                        description=f"Configuration {config_id} has an average confidence score of {summary.average_confidence_score:.2f}, which is below the recommended threshold of 0.6.",
                        recommendation="Review and improve field mapping configurations, or consider updating the ML model training data.",
                        affected_configs=[config_id],
                        metric_values={'confidence_score': summary.average_confidence_score},
                        confidence=0.9
                    ))
                
                # High error rate insight
                if summary.error_rate > 0.2:
                    insights.append(PerformanceInsight(
                        insight_type="high_error_rate",
                        severity="high",
                        title="High Error Rate",
                        description=f"Configuration {config_id} has an error rate of {summary.error_rate:.1%}, which indicates frequent parsing failures.",
                        recommendation="Check field mapping selectors and validation rules. Consider updating extraction methods.",
                        affected_configs=[config_id],
                        metric_values={'error_rate': summary.error_rate},
                        confidence=0.95
                    ))
                
                # Slow processing insight
                if summary.average_processing_time > 5.0:  # 5 seconds
                    insights.append(PerformanceInsight(
                        insight_type="slow_processing",
                        severity="medium",
                        title="Slow Processing Time",
                        description=f"Configuration {config_id} has an average processing time of {summary.average_processing_time:.2f} seconds, which may impact scraping performance.",
                        recommendation="Optimize field extraction selectors and consider reducing the number of validation rules.",
                        affected_configs=[config_id],
                        metric_values={'processing_time': summary.average_processing_time},
                        confidence=0.8
                    ))
                
                # Poor field extraction insight
                poor_fields = [field for field, rate in summary.field_extraction_rates.items() if rate < 0.5]
                if poor_fields:
                    insights.append(PerformanceInsight(
                        insight_type="poor_field_extraction",
                        severity="medium",
                        title="Poor Field Extraction",
                        description=f"Configuration {config_id} has low extraction rates for fields: {', '.join(poor_fields)}",
                        recommendation="Review and update CSS selectors or extraction methods for these fields.",
                        affected_configs=[config_id],
                        metric_values={f"extraction_rate_{field}": rate for field, rate in summary.field_extraction_rates.items() if field in poor_fields},
                        confidence=0.85
                    ))
                
                # Declining performance insight (based on trends)
                if 'confidence_score' in summary.trends and len(summary.trends['confidence_score']) >= 3:
                    recent_trend = summary.trends['confidence_score'][-3:]
                    if all(recent_trend[i] > recent_trend[i+1] for i in range(len(recent_trend)-1)):
                        insights.append(PerformanceInsight(
                            insight_type="declining_performance",
                            severity="medium",
                            title="Declining Performance Trend",
                            description=f"Configuration {config_id} shows a declining confidence score trend over the past few days.",
                            recommendation="Monitor for website changes that might affect parsing. Consider updating field mappings.",
                            affected_configs=[config_id],
                            metric_values={'trend_slope': (recent_trend[-1] - recent_trend[0]) / len(recent_trend)},
                            confidence=0.7
                        ))
            
            # Sort insights by severity and confidence
            severity_order = {'high': 3, 'medium': 2, 'low': 1}
            insights.sort(key=lambda x: (severity_order.get(x.severity, 0), x.confidence), reverse=True)
            
            return insights
            
        except Exception as e:
            self.logger.error(f"Error generating performance insights: {str(e)}")
            return []
    
    async def get_cost_analysis(self, config_id: Optional[int] = None, time_range: TimeRange = TimeRange.MONTH) -> Dict[str, Any]:
        """Get cost analysis for ML parsing operations"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30 if time_range == TimeRange.MONTH else 7)
            
            # Get API usage metrics
            if config_id:
                config_ids = [config_id]
            else:
                config_ids = await self._get_all_ml_enabled_configs()
            
            total_requests = 0
            total_tokens = 0
            total_cost = 0.0
            config_costs = {}
            
            for cid in config_ids:
                metrics = await self._get_metrics_for_period(cid, start_date, end_date)
                api_metrics = [m for m in metrics if m['type'] == MetricType.GEMINI_API_USAGE.value]
                
                config_requests = sum(m['value'] for m in api_metrics)
                config_tokens = sum(m.get('metadata', {}).get('tokens_used', 0) for m in api_metrics)
                
                # Estimate cost (approximate Gemini API pricing)
                config_cost = (config_tokens / 1000) * 0.002  # $0.002 per 1K tokens (approximate)
                
                total_requests += config_requests
                total_tokens += config_tokens
                total_cost += config_cost
                
                config_costs[cid] = {
                    'requests': config_requests,
                    'tokens': config_tokens,
                    'estimated_cost': config_cost
                }
            
            # Calculate efficiency metrics
            avg_tokens_per_request = total_tokens / total_requests if total_requests > 0 else 0
            cost_per_job = total_cost / total_requests if total_requests > 0 else 0
            
            return {
                'time_range': time_range.value,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'total_requests': total_requests,
                'total_tokens': total_tokens,
                'total_estimated_cost': total_cost,
                'average_tokens_per_request': avg_tokens_per_request,
                'cost_per_job': cost_per_job,
                'config_breakdown': config_costs,
                'optimization_suggestions': await self._get_cost_optimization_suggestions(config_costs)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cost analysis: {str(e)}")
            return {'error': str(e)}
    
    async def _get_metrics_for_period(self, config_id: int, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get metrics for a specific period from database"""
        try:
            if not get_db_session or not AnalyticsMetrics:
                return []
            
            with get_db_session() as db:
                metrics = db.query(AnalyticsMetrics).filter(
                    AnalyticsMetrics.scraper_config_id == config_id,
                    AnalyticsMetrics.created_at >= start_date,
                    AnalyticsMetrics.created_at <= end_date
                ).all()
                
                result = []
                for metric in metrics:
                    metadata = json.loads(metric.metadata) if metric.metadata else {}
                    result.append({
                        'type': metric.metric_type,
                        'value': metric.metric_value,
                        'timestamp': metric.created_at,
                        'metadata': metadata,
                        'session_id': metadata.get('session_id')
                    })
                
                return result
                
        except Exception as e:
            self.logger.error(f"Error getting metrics for period: {str(e)}")
            return []
    
    async def _calculate_trends(self, config_id: int, start_date: datetime, end_date: datetime) -> Dict[str, List[float]]:
        """Calculate daily trends for key metrics"""
        try:
            trends = {
                'confidence_score': [],
                'quality_score': [],
                'processing_time': [],
                'success_rate': []
            }
            
            # Calculate daily averages
            current_date = start_date
            while current_date < end_date:
                next_date = current_date + timedelta(days=1)
                daily_metrics = await self._get_metrics_for_period(config_id, current_date, next_date)
                
                # Calculate daily averages
                confidence_scores = [m['value'] for m in daily_metrics if m['type'] == MetricType.CONFIDENCE_SCORE.value]
                quality_scores = [m['value'] for m in daily_metrics if m['type'] == MetricType.QUALITY_SCORE.value]
                processing_times = [m['value'] for m in daily_metrics if m['type'] == MetricType.PROCESSING_TIME.value]
                
                trends['confidence_score'].append(statistics.mean(confidence_scores) if confidence_scores else 0)
                trends['quality_score'].append(statistics.mean(quality_scores) if quality_scores else 0)
                trends['processing_time'].append(statistics.mean(processing_times) if processing_times else 0)
                trends['success_rate'].append(len([s for s in confidence_scores if s > 0.7]) / len(confidence_scores) if confidence_scores else 0)
                
                current_date = next_date
            
            return trends
            
        except Exception as e:
            self.logger.error(f"Error calculating trends: {str(e)}")
            return {}
    
    async def _calculate_cost_metrics(self, config_id: int, start_date: datetime, end_date: datetime) -> Dict[str, float]:
        """Calculate cost-related metrics"""
        try:
            metrics = await self._get_metrics_for_period(config_id, start_date, end_date)
            api_metrics = [m for m in metrics if m['type'] == MetricType.GEMINI_API_USAGE.value]
            
            total_requests = sum(m['value'] for m in api_metrics)
            total_tokens = sum(m.get('metadata', {}).get('tokens_used', 0) for m in api_metrics)
            estimated_cost = (total_tokens / 1000) * 0.002  # Approximate pricing
            
            return {
                'total_requests': total_requests,
                'total_tokens': total_tokens,
                'estimated_cost': estimated_cost,
                'cost_per_request': estimated_cost / total_requests if total_requests > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating cost metrics: {str(e)}")
            return {}
    
    async def _get_all_ml_enabled_configs(self) -> List[int]:
        """Get all scraper configurations with ML parsing enabled"""
        try:
            if not get_db_session or not ScraperConfig:
                return []
            
            with get_db_session() as db:
                configs = db.query(ScraperConfig).filter(
                    ScraperConfig.ml_parsing_enabled == True
                ).all()
                
                return [config.id for config in configs]
                
        except Exception as e:
            self.logger.error(f"Error getting ML enabled configs: {str(e)}")
            return []
    
    async def _get_cost_optimization_suggestions(self, config_costs: Dict[int, Dict[str, Any]]) -> List[str]:
        """Generate cost optimization suggestions"""
        suggestions = []
        
        try:
            # Find high-cost configurations
            high_cost_configs = [cid for cid, data in config_costs.items() if data['estimated_cost'] > 1.0]
            if high_cost_configs:
                suggestions.append(f"Consider optimizing configurations {high_cost_configs} which have high API costs")
            
            # Find inefficient token usage
            inefficient_configs = [cid for cid, data in config_costs.items() 
                                 if data['requests'] > 0 and (data['tokens'] / data['requests']) > 1000]
            if inefficient_configs:
                suggestions.append(f"Configurations {inefficient_configs} use excessive tokens per request - consider simplifying prompts")
            
            # General suggestions
            if not suggestions:
                suggestions.append("API usage is within normal ranges. Continue monitoring for optimization opportunities.")
            
        except Exception as e:
            self.logger.error(f"Error generating cost optimization suggestions: {str(e)}")
            suggestions.append("Unable to generate optimization suggestions due to analysis error.")
        
        return suggestions

# Global instance
ml_analytics_service = MLAnalyticsService()