from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel, Field
from loguru import logger

from ..ai.decision_engine import get_ai_decision_engine, AIAnalysisResult
from ..ai.openrouter_client import get_openrouter_client
from ..job_boards.job_board_manager import get_job_board_manager, JobBoardConfig
from ..data_quality.validator import get_data_quality_validator, ValidationResult, EnrichmentResult
from ..monitoring.dashboard import get_monitoring_dashboard
from ..models.mongodb_models import JobPosting
from ..middleware.auth import get_current_user

router = APIRouter(prefix="/ai", tags=["AI"])

# Request/Response Models
class JobBoardAnalysisRequest(BaseModel):
    """Request model for job board analysis"""
    url: str = Field(..., description="Job board URL to analyze")
    job_board_name: str = Field(..., description="Name of the job board")
    force_reanalysis: bool = Field(False, description="Force re-analysis even if cached")

class JobBoardAnalysisResponse(BaseModel):
    """Response model for job board analysis"""
    job_board: str
    url: str
    analysis_result: Dict[str, Any]
    recommended_engine: str
    confidence_score: float
    selectors: Dict[str, str]
    analyzed_at: datetime
    processing_time: float

class ContentValidationRequest(BaseModel):
    """Request model for content validation"""
    job_posting_id: str = Field(..., description="Job posting ID to validate")
    include_enrichment: bool = Field(True, description="Include AI enrichment")

class ContentValidationResponse(BaseModel):
    """Response model for content validation"""
    job_id: str
    validation_result: Dict[str, Any]
    enrichment_result: Optional[Dict[str, Any]] = None
    processing_time: float

class BatchValidationRequest(BaseModel):
    """Request model for batch validation"""
    job_posting_ids: List[str] = Field(..., description="List of job posting IDs")
    include_enrichment: bool = Field(True, description="Include AI enrichment")
    max_concurrent: int = Field(10, description="Maximum concurrent validations")

class BatchValidationResponse(BaseModel):
    """Response model for batch validation"""
    total_jobs: int
    successful_validations: int
    failed_validations: int
    results: List[Dict[str, Any]]
    processing_time: float

class AIMetricsResponse(BaseModel):
    """Response model for AI metrics"""
    total_analyses: int
    successful_analyses: int
    failed_analyses: int
    average_processing_time: float
    engine_usage: Dict[str, int]
    quality_scores: Dict[str, float]
    last_updated: datetime

class EngineOptimizationRequest(BaseModel):
    """Request model for engine optimization"""
    job_board: str = Field(..., description="Job board to optimize")
    sample_urls: List[str] = Field(..., description="Sample URLs for testing")
    optimization_criteria: List[str] = Field(["speed", "accuracy", "reliability"], description="Optimization criteria")

@router.post("/analyze-job-board", response_model=JobBoardAnalysisResponse)
async def analyze_job_board(
    request: JobBoardAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze a job board using AI to determine optimal scraping strategy"""
    try:
        start_time = datetime.now()
        
        # Get AI decision engine
        ai_engine = await get_ai_decision_engine()
        
        # Perform AI analysis
        analysis_result = await ai_engine.analyze_job_board(
            url=request.url,
            job_board_name=request.job_board_name,
            force_reanalysis=request.force_reanalysis
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return JobBoardAnalysisResponse(
            job_board=request.job_board_name,
            url=request.url,
            analysis_result={
                "page_structure": analysis_result.page_structure,
                "anti_bot_measures": analysis_result.anti_bot_measures,
                "content_patterns": analysis_result.content_patterns,
                "performance_indicators": analysis_result.performance_indicators
            },
            recommended_engine=analysis_result.recommended_engine,
            confidence_score=analysis_result.confidence_score,
            selectors=analysis_result.selectors,
            analyzed_at=datetime.now(),
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Job board analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.post("/validate-content", response_model=ContentValidationResponse)
async def validate_content(
    request: ContentValidationRequest,
    current_user: dict = Depends(get_current_user)
):
    """Validate and enrich job posting content using AI"""
    try:
        start_time = datetime.now()
        
        # Get data quality validator
        validator = await get_data_quality_validator()
        
        # Get job posting from database (simplified - you'd implement this)
        # For now, we'll create a mock job posting
        job_posting = JobPosting(
            id=request.job_posting_id,
            title="Sample Job",
            company="Sample Company",
            location="Sample Location",
            description="Sample Description",
            url="https://example.com/job",
            job_board="sample_board",
            scraped_at=datetime.now()
        )
        
        # Validate content
        validation_result = await validator.validate_job_posting(job_posting)
        
        enrichment_result = None
        if request.include_enrichment:
            enrichment_result = await validator.enrich_job_posting(job_posting)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return ContentValidationResponse(
            job_id=request.job_posting_id,
            validation_result={
                "is_valid": validation_result.is_valid,
                "quality_score": validation_result.quality_score,
                "issues": [{
                    "rule": issue.rule,
                    "severity": issue.severity,
                    "field": issue.field,
                    "message": issue.message,
                    "suggestion": issue.suggestion
                } for issue in validation_result.issues],
                "validated_at": validation_result.validated_at.isoformat(),
                "processing_time": validation_result.processing_time
            },
            enrichment_result={
                "enrichments": enrichment_result.enrichments,
                "confidence_scores": enrichment_result.confidence_scores,
                "enriched_at": enrichment_result.enriched_at.isoformat(),
                "processing_time": enrichment_result.processing_time
            } if enrichment_result else None,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Content validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

@router.post("/batch-validate", response_model=BatchValidationResponse)
async def batch_validate(
    request: BatchValidationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Validate multiple job postings in batch"""
    try:
        start_time = datetime.now()
        
        # Get data quality validator
        validator = await get_data_quality_validator()
        
        # Create mock job postings (you'd fetch from database)
        job_postings = []
        for job_id in request.job_posting_ids:
            job_posting = JobPosting(
                id=job_id,
                title=f"Sample Job {job_id}",
                company="Sample Company",
                location="Sample Location",
                description="Sample Description",
                url=f"https://example.com/job/{job_id}",
                job_board="sample_board",
                scraped_at=datetime.now()
            )
            job_postings.append(job_posting)
        
        # Batch validate
        validation_results = await validator.batch_validate(
            job_postings, 
            max_concurrent=request.max_concurrent
        )
        
        enrichment_results = []
        if request.include_enrichment:
            enrichment_results = await validator.batch_enrich(
                job_postings,
                max_concurrent=min(5, request.max_concurrent)
            )
        
        # Combine results
        results = []
        for i, validation_result in enumerate(validation_results):
            result_data = {
                "job_id": validation_result.job_id,
                "validation": {
                    "is_valid": validation_result.is_valid,
                    "quality_score": validation_result.quality_score,
                    "issues_count": len(validation_result.issues),
                    "processing_time": validation_result.processing_time
                }
            }
            
            if i < len(enrichment_results):
                enrichment_result = enrichment_results[i]
                result_data["enrichment"] = {
                    "enrichments_count": len(enrichment_result.enrichments),
                    "average_confidence": sum(enrichment_result.confidence_scores.values()) / len(enrichment_result.confidence_scores) if enrichment_result.confidence_scores else 0.0,
                    "processing_time": enrichment_result.processing_time
                }
            
            results.append(result_data)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return BatchValidationResponse(
            total_jobs=len(request.job_posting_ids),
            successful_validations=len(validation_results),
            failed_validations=len(request.job_posting_ids) - len(validation_results),
            results=results,
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Batch validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch validation failed: {str(e)}")

@router.get("/metrics", response_model=AIMetricsResponse)
async def get_ai_metrics(
    current_user: dict = Depends(get_current_user)
):
    """Get AI system metrics and performance statistics"""
    try:
        # Get monitoring dashboard
        dashboard = await get_monitoring_dashboard()
        
        # Get dashboard stats
        stats = await dashboard.get_dashboard_stats()
        
        return AIMetricsResponse(
            total_analyses=stats.total_scraping_attempts,
            successful_analyses=stats.successful_scrapes,
            failed_analyses=stats.failed_scrapes,
            average_processing_time=stats.average_response_time,
            engine_usage={
                "scrapy": stats.engine_metrics.get("scrapy", {}).get("total_requests", 0),
                "beautifulsoup": stats.engine_metrics.get("beautifulsoup", {}).get("total_requests", 0),
                "selenium": stats.engine_metrics.get("selenium", {}).get("total_requests", 0)
            },
            quality_scores={
                "average": stats.average_quality_score,
                "by_board": stats.quality_by_board
            },
            last_updated=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to get AI metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")

@router.post("/optimize-engine")
async def optimize_engine(
    request: EngineOptimizationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Optimize scraping engine for a specific job board"""
    try:
        # Get AI decision engine
        ai_engine = await get_ai_decision_engine()
        
        # Add optimization task to background
        background_tasks.add_task(
            _optimize_engine_background,
            ai_engine,
            request.job_board,
            request.sample_urls,
            request.optimization_criteria
        )
        
        return {
            "message": f"Engine optimization started for {request.job_board}",
            "job_board": request.job_board,
            "sample_urls_count": len(request.sample_urls),
            "criteria": request.optimization_criteria,
            "status": "started"
        }
        
    except Exception as e:
        logger.error(f"Engine optimization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")

@router.get("/job-boards")
async def get_supported_job_boards(
    category: Optional[str] = Query(None, description="Filter by category"),
    region: Optional[str] = Query(None, description="Filter by region"),
    current_user: dict = Depends(get_current_user)
):
    """Get list of supported job boards with AI analysis status"""
    try:
        # Get job board manager
        job_board_manager = await get_job_board_manager()
        
        # Get all job boards
        job_boards = await job_board_manager.get_all_job_boards()
        
        # Filter by category and region if specified
        filtered_boards = []
        for board in job_boards:
            if category and board.category != category:
                continue
            if region and board.region != region:
                continue
            filtered_boards.append(board)
        
        # Format response
        response_data = []
        for board in filtered_boards:
            response_data.append({
                "name": board.name,
                "url": board.base_url,
                "category": board.category,
                "region": board.region,
                "supported_engines": board.supported_engines,
                "ai_analyzed": board.ai_analyzed,
                "last_analysis": board.last_analysis.isoformat() if board.last_analysis else None,
                "success_rate": board.success_rate,
                "average_response_time": board.average_response_time,
                "status": "active" if board.is_active else "inactive"
            })
        
        return {
            "total_boards": len(response_data),
            "filtered_boards": len(response_data),
            "job_boards": response_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get job boards: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job boards: {str(e)}")

@router.post("/test-openrouter")
async def test_openrouter_connection(
    current_user: dict = Depends(get_current_user)
):
    """Test OpenRouter API connection and model availability"""
    try:
        # Get OpenRouter client
        client = await get_openrouter_client()
        
        # Test connection with a simple prompt
        test_prompt = "Analyze this job posting structure: <div class='job-title'>Software Engineer</div>"
        
        response = await client.analyze_job_board_structure(
            html_content=test_prompt,
            url="https://test.example.com"
        )
        
        return {
            "status": "success",
            "message": "OpenRouter connection successful",
            "model": client.config.model,
            "response_preview": response.get("analysis", {}).get("summary", "No summary available")[:200],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"OpenRouter test failed: {e}")
        raise HTTPException(status_code=500, detail=f"OpenRouter test failed: {str(e)}")

# Background task functions
async def _optimize_engine_background(
    ai_engine,
    job_board: str,
    sample_urls: List[str],
    criteria: List[str]
):
    """Background task for engine optimization"""
    try:
        logger.info(f"Starting engine optimization for {job_board}")
        
        # Perform optimization analysis
        for url in sample_urls:
            try:
                # Analyze each URL
                analysis = await ai_engine.analyze_job_board(
                    url=url,
                    job_board_name=job_board
                )
                
                # Log results
                logger.info(f"Analyzed {url}: engine={analysis.recommended_engine}, confidence={analysis.confidence_score}")
                
            except Exception as e:
                logger.error(f"Failed to analyze {url}: {e}")
        
        logger.info(f"Engine optimization completed for {job_board}")
        
    except Exception as e:
        logger.error(f"Engine optimization background task failed: {e}")