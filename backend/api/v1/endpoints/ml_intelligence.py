from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session  # Using MongoDB instead
from pydantic import BaseModel, Field
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.core.deps import get_database  # Using MongoDB instead
from backend.services.ml_intelligence import (
    MLIntelligenceEngine, 
    MLPrediction, 
    PatternInsight, 
    AdaptiveLearningMetrics,
    SelectorPattern
)
from backend.core.auth import get_current_user
from backend.models.mongodb_models import User

router = APIRouter()

# Global ML engine instance
ml_engine = MLIntelligenceEngine()

# Pydantic models for API
class PredictionRequest(BaseModel):
    html_content: str = Field(..., description="HTML content to analyze")
    url: str = Field(..., description="URL of the page")
    target_content_type: str = Field(default="general", description="Type of content to extract")

class PredictionResponse(BaseModel):
    predicted_selectors: List[str]
    confidence_scores: List[float]
    optimization_suggestions: List[str]
    expected_success_rate: float
    estimated_response_time: float
    risk_factors: List[str]

class PatternInsightResponse(BaseModel):
    pattern_type: str
    description: str
    confidence: float
    impact_score: float
    recommendation: str
    supporting_data: Dict[str, Any]

class LearningMetricsResponse(BaseModel):
    pattern_accuracy: float
    learning_rate: float
    adaptation_speed: float
    prediction_confidence: float
    optimization_impact: float
    model_stability: float

class DomainInsightsResponse(BaseModel):
    domain: str
    pattern_count: int
    average_success_rate: float
    average_confidence: float
    recommended_selectors: List[str]
    top_patterns: List[Dict[str, Any]]
    insights: List[str]

class AnomalyResponse(BaseModel):
    index: int
    data: Dict[str, Any]
    anomaly_score: float
    reason: str

class OptimizationReportResponse(BaseModel):
    period: str
    summary: Dict[str, Any]
    domain_performance: Dict[str, Any]
    recommendations: List[str]
    learning_trends: Dict[str, Any]

class SelectorAnalysisRequest(BaseModel):
    successful_selectors: List[str] = Field(default=[], description="List of successful selectors")
    failed_selectors: List[str] = Field(default=[], description="List of failed selectors")
    domain: str = Field(..., description="Domain to analyze")

@router.post("/predict-selectors", response_model=PredictionResponse)
async def predict_optimal_selectors(
    request: PredictionRequest,
    current_user: User = Depends(get_current_user)
):
    """Predict optimal selectors for given HTML content using ML"""
    try:
        prediction = ml_engine.predict_optimal_selectors(
            html_content=request.html_content,
            url=request.url,
            target_content_type=request.target_content_type
        )
        
        return PredictionResponse(
            predicted_selectors=prediction.predicted_selectors,
            confidence_scores=prediction.confidence_scores,
            optimization_suggestions=prediction.optimization_suggestions,
            expected_success_rate=prediction.expected_success_rate,
            estimated_response_time=prediction.estimated_response_time,
            risk_factors=prediction.risk_factors
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@router.post("/analyze-patterns", response_model=List[PatternInsightResponse])
async def analyze_selector_patterns(
    request: SelectorAnalysisRequest,
    current_user: User = Depends(get_current_user)
):
    """Analyze selector patterns to identify success factors"""
    try:
        insights = ml_engine.analyze_selector_patterns(
            successful_selectors=request.successful_selectors,
            failed_selectors=request.failed_selectors,
            domain=request.domain
        )
        
        return [
            PatternInsightResponse(
                pattern_type=insight.pattern_type,
                description=insight.description,
                confidence=insight.confidence,
                impact_score=insight.impact_score,
                recommendation=insight.recommendation,
                supporting_data=insight.supporting_data
            )
            for insight in insights
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pattern analysis failed: {str(e)}")

@router.post("/learn-from-session/{session_id}", response_model=LearningMetricsResponse)
async def learn_from_scraping_session(
    session_id: int,
    db: AsyncIOMotorDatabase = Depends(get_database),  # Using MongoDB instead
    current_user: User = Depends(get_current_user)
):
    """Learn from scraping session results to improve future predictions"""
    try:
        metrics = ml_engine.learn_from_scraping_results(session_id, db)
        
        return LearningMetricsResponse(
            pattern_accuracy=metrics.pattern_accuracy,
            learning_rate=metrics.learning_rate,
            adaptation_speed=metrics.adaptation_speed,
            prediction_confidence=metrics.prediction_confidence,
            optimization_impact=metrics.optimization_impact,
            model_stability=metrics.model_stability
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Learning failed: {str(e)}")

@router.get("/domain-insights/{domain}", response_model=DomainInsightsResponse)
async def get_domain_insights(
    domain: str,
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive insights for a specific domain"""
    try:
        insights = ml_engine.get_domain_insights(domain)
        
        return DomainInsightsResponse(
            domain=insights['domain'],
            pattern_count=insights['pattern_count'],
            average_success_rate=insights['average_success_rate'],
            average_confidence=insights.get('average_confidence', 0.0),
            recommended_selectors=insights['recommended_selectors'],
            top_patterns=insights.get('top_patterns', []),
            insights=insights['insights']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Domain insights failed: {str(e)}")

@router.post("/detect-anomalies", response_model=List[AnomalyResponse])
async def detect_anomalies(
    session_data: List[Dict[str, Any]],
    current_user: User = Depends(get_current_user)
):
    """Detect anomalies in scraping session data"""
    try:
        anomalies = ml_engine.detect_anomalies(session_data)
        
        return [
            AnomalyResponse(
                index=anomaly['index'],
                data=anomaly['data'],
                anomaly_score=anomaly['anomaly_score'],
                reason=anomaly['reason']
            )
            for anomaly in anomalies
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {str(e)}")

@router.get("/optimization-report", response_model=OptimizationReportResponse)
async def generate_optimization_report(
    time_period_days: int = Query(default=30, ge=1, le=365, description="Time period in days"),
    current_user: User = Depends(get_current_user)
):
    """Generate comprehensive optimization report"""
    try:
        report = ml_engine.generate_optimization_report(time_period_days)
        
        return OptimizationReportResponse(
            period=report['period'],
            summary=report['summary'],
            domain_performance=report['domain_performance'],
            recommendations=report['recommendations'],
            learning_trends=report['learning_trends']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@router.get("/training-status")
async def get_training_status(
    current_user: User = Depends(get_current_user)
):
    """Get ML model training status and statistics"""
    try:
        return {
            "is_trained": ml_engine.is_trained,
            "last_training_time": ml_engine.last_training_time.isoformat() if ml_engine.last_training_time else None,
            "training_data_size": ml_engine.training_data_size,
            "total_learned_patterns": sum(len(patterns) for patterns in ml_engine.learned_patterns.values()),
            "domains_with_patterns": len(ml_engine.learned_patterns),
            "performance_history_size": len(ml_engine.performance_history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status retrieval failed: {str(e)}")

@router.post("/retrain-models")
async def retrain_models(
    force: bool = Query(default=False, description="Force retraining even with limited data"),
    db: AsyncIOMotorDatabase = Depends(get_database),  # Using MongoDB instead
    current_user: User = Depends(get_current_user)
):
    """Manually trigger model retraining"""
    try:
        # Get recent session data for training
        from backend.models.scraping_session import ScrapingSession, ScrapingResult
        
        recent_sessions = db.query(ScrapingSession).order_by(
            ScrapingSession.created_at.desc()
        ).limit(100).all()
        
        learning_data = []
        for session in recent_sessions:
            results = db.query(ScrapingResult).filter(
                ScrapingResult.session_id == session.id
            ).all()
            
            for result in results:
                if result.extracted_data and result.selectors_used:
                    features = ml_engine.extract_features_from_html(
                        result.html_snapshot or "", 
                        result.url
                    )
                    
                    learning_data.append({
                        'features': features,
                        'selectors': result.selectors_used,
                        'success': result.status == 'completed',
                        'response_time': result.response_time or 0,
                        'domain': ml_engine._extract_domain(result.url)
                    })
        
        if not learning_data and not force:
            raise HTTPException(
                status_code=400, 
                detail="Insufficient training data available. Use force=true to override."
            )
        
        # Update patterns and retrain
        ml_engine._update_learned_patterns(learning_data)
        if len(learning_data) >= 10 or force:
            ml_engine._retrain_models(learning_data)
        
        return {
            "message": "Models retrained successfully",
            "training_data_points": len(learning_data),
            "is_trained": ml_engine.is_trained,
            "last_training_time": ml_engine.last_training_time.isoformat() if ml_engine.last_training_time else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retraining failed: {str(e)}")

@router.get("/learned-patterns")
async def get_learned_patterns(
    domain: Optional[str] = Query(default=None, description="Filter by domain"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of patterns to return"),
    current_user: User = Depends(get_current_user)
):
    """Get learned selector patterns"""
    try:
        if domain:
            patterns = ml_engine.learned_patterns.get(domain, [])
            domain_patterns = {domain: patterns[:limit]}
        else:
            domain_patterns = {}
            total_count = 0
            for d, patterns in ml_engine.learned_patterns.items():
                if total_count >= limit:
                    break
                remaining = limit - total_count
                domain_patterns[d] = patterns[:remaining]
                total_count += len(domain_patterns[d])
        
        # Convert to serializable format
        serializable_patterns = {}
        for d, patterns in domain_patterns.items():
            serializable_patterns[d] = [
                {
                    "selector": p.selector,
                    "confidence": p.confidence,
                    "success_rate": p.success_rate,
                    "domain_pattern": p.domain_pattern,
                    "content_type": p.content_type,
                    "usage_count": p.usage_count,
                    "last_used": p.last_used.isoformat(),
                    "performance_score": p.performance_score
                }
                for p in patterns
            ]
        
        return {
            "patterns": serializable_patterns,
            "total_domains": len(serializable_patterns),
            "total_patterns": sum(len(patterns) for patterns in serializable_patterns.values())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pattern retrieval failed: {str(e)}")

@router.delete("/clear-patterns")
async def clear_learned_patterns(
    domain: Optional[str] = Query(default=None, description="Clear patterns for specific domain only"),
    confirm: bool = Query(default=False, description="Confirmation required"),
    current_user: User = Depends(get_current_user)
):
    """Clear learned patterns (use with caution)"""
    if not confirm:
        raise HTTPException(
            status_code=400, 
            detail="Confirmation required. Set confirm=true to proceed."
        )
    
    try:
        if domain:
            if domain in ml_engine.learned_patterns:
                pattern_count = len(ml_engine.learned_patterns[domain])
                del ml_engine.learned_patterns[domain]
                return {
                    "message": f"Cleared {pattern_count} patterns for domain {domain}",
                    "domain": domain
                }
            else:
                raise HTTPException(status_code=404, detail=f"No patterns found for domain {domain}")
        else:
            total_patterns = sum(len(patterns) for patterns in ml_engine.learned_patterns.values())
            total_domains = len(ml_engine.learned_patterns)
            ml_engine.learned_patterns.clear()
            ml_engine.performance_history.clear()
            ml_engine.is_trained = False
            ml_engine.last_training_time = None
            ml_engine.training_data_size = 0
            
            return {
                "message": f"Cleared all learned patterns and reset ML models",
                "patterns_cleared": total_patterns,
                "domains_cleared": total_domains
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pattern clearing failed: {str(e)}")

@router.get("/performance-history")
async def get_performance_history(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to retrieve"),
    current_user: User = Depends(get_current_user)
):
    """Get ML performance history"""
    try:
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_history = [
            {
                "timestamp": h['timestamp'].isoformat(),
                "session_id": h['session_id'],
                "data_points": h['data_points'],
                "metrics": {
                    "pattern_accuracy": h['metrics'].pattern_accuracy,
                    "learning_rate": h['metrics'].learning_rate,
                    "adaptation_speed": h['metrics'].adaptation_speed,
                    "prediction_confidence": h['metrics'].prediction_confidence,
                    "optimization_impact": h['metrics'].optimization_impact,
                    "model_stability": h['metrics'].model_stability
                }
            }
            for h in ml_engine.performance_history
            if h['timestamp'] >= cutoff_date
        ]
        
        return {
            "history": recent_history,
            "period_days": days,
            "total_entries": len(recent_history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"History retrieval failed: {str(e)}")