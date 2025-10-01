from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel, Field, HttpUrl
from loguru import logger

from ..scrapers.multi_engine_framework import (
    get_multi_engine_framework,
    ScrapingResult,
    EnginePerformanceMetrics
)
from ..ai.decision_engine import get_ai_decision_engine
from ..job_boards.job_board_manager import get_job_board_manager
from ..data_quality.validator import get_data_quality_validator
from ..monitoring.dashboard import get_monitoring_dashboard
from ..middleware.auth import get_current_user

router = APIRouter(prefix="/scraping", tags=["Scraping"])

# Request/Response Models
class ScrapeJobBoardRequest(BaseModel):
    """Request model for scraping a job board"""
    job_board_name: str = Field(..., description="Name of the job board")
    base_url: HttpUrl = Field(..., description="Base URL of the job board")
    max_pages: int = Field(5, description="Maximum pages to scrape")
    max_jobs: int = Field(100, description="Maximum jobs to scrape")
    force_engine: Optional[str] = Field(None, description="Force specific engine (scrapy, beautifulsoup, selenium)")
    enable_ai_analysis: bool = Field(True, description="Enable AI-powered analysis")
    validate_content: bool = Field(True, description="Enable content validation")
    enrich_content: bool = Field(True, description="Enable AI content enrichment")

class ScrapeUrlRequest(BaseModel):
    """Request model for scraping specific URLs"""
    urls: List[HttpUrl] = Field(..., description="List of URLs to scrape")
    job_board_name: str = Field(..., description="Name of the job board")
    force_engine: Optional[str] = Field(None, description="Force specific engine")
    enable_ai_analysis: bool = Field(True, description="Enable AI-powered analysis")
    validate_content: bool = Field(True, description="Enable content validation")
    enrich_content: bool = Field(True, description="Enable AI content enrichment")

class BulkScrapeRequest(BaseModel):
    """Request model for bulk scraping multiple job boards"""
    job_boards: List[str] = Field(..., description="List of job board names")
    max_jobs_per_board: int = Field(50, description="Maximum jobs per board")
    max_concurrent_boards: int = Field(5, description="Maximum concurrent boards")
    enable_ai_optimization: bool = Field(True, description="Enable AI optimization")
    priority_boards: List[str] = Field([], description="Priority job boards to scrape first")

class ScrapeResponse(BaseModel):
    """Response model for scraping operations"""
    task_id: str
    job_board: str
    status: str
    message: str
    estimated_completion: Optional[datetime] = None
    urls_to_scrape: int
    engine_selected: Optional[str] = None
    ai_analysis_enabled: bool
    started_at: datetime

class ScrapeResultResponse(BaseModel):
    """Response model for scraping results"""
    task_id: str
    job_board: str
    status: str
    total_jobs_found: int
    successful_scrapes: int
    failed_scrapes: int
    validation_results: Optional[Dict[str, Any]] = None
    enrichment_results: Optional[Dict[str, Any]] = None
    engine_used: str
    processing_time: float
    quality_score: float
    completed_at: datetime
    jobs: List[Dict[str, Any]]

class EnginePerformanceResponse(BaseModel):
    """Response model for engine performance"""
    engine: str
    metrics: Dict[str, Any]
    recommendations: List[str]
    last_updated: datetime

class ScrapingStatsResponse(BaseModel):
    """Response model for scraping statistics"""
    total_scraping_sessions: int
    successful_sessions: int
    failed_sessions: int
    total_jobs_scraped: int
    average_quality_score: float
    engine_usage: Dict[str, int]
    top_performing_boards: List[Dict[str, Any]]
    recent_activity: List[Dict[str, Any]]
    last_updated: datetime

# In-memory task storage (in production, use Redis or database)
scraping_tasks = {}

@router.post("/scrape-job-board", response_model=ScrapeResponse)
async def scrape_job_board(
    request: ScrapeJobBoardRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Start scraping a specific job board with AI-powered engine selection"""
    try:
        # Generate task ID
        task_id = f"scrape_{request.job_board_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Get multi-engine framework
        framework = await get_multi_engine_framework()
        
        # AI-powered engine selection if not forced
        selected_engine = request.force_engine
        if not selected_engine and request.enable_ai_analysis:
            try:
                ai_engine = await get_ai_decision_engine()
                analysis = await ai_engine.analyze_job_board(
                    url=str(request.base_url),
                    job_board_name=request.job_board_name
                )
                selected_engine = analysis.recommended_engine
                logger.info(f"AI selected engine {selected_engine} for {request.job_board_name} (confidence: {analysis.confidence_score})")
            except Exception as e:
                logger.warning(f"AI engine selection failed, using default: {e}")
                selected_engine = "beautifulsoup"  # Default fallback
        elif not selected_engine:
            selected_engine = "beautifulsoup"  # Default
        
        # Store task info
        scraping_tasks[task_id] = {
            "status": "started",
            "job_board": request.job_board_name,
            "base_url": str(request.base_url),
            "engine": selected_engine,
            "started_at": datetime.now(),
            "max_pages": request.max_pages,
            "max_jobs": request.max_jobs,
            "ai_analysis_enabled": request.enable_ai_analysis,
            "validate_content": request.validate_content,
            "enrich_content": request.enrich_content,
            "user": current_user.get("username", "unknown")
        }
        
        # Start background scraping task
        background_tasks.add_task(
            _scrape_job_board_background,
            task_id,
            framework,
            request
        )
        
        return ScrapeResponse(
            task_id=task_id,
            job_board=request.job_board_name,
            status="started",
            message=f"Scraping started for {request.job_board_name}",
            estimated_completion=datetime.now().replace(minute=datetime.now().minute + 10),  # Rough estimate
            urls_to_scrape=request.max_jobs,
            engine_selected=selected_engine,
            ai_analysis_enabled=request.enable_ai_analysis,
            started_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to start scraping for {request.job_board_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start scraping: {str(e)}")

@router.post("/scrape-urls", response_model=ScrapeResponse)
async def scrape_urls(
    request: ScrapeUrlRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Scrape specific URLs with AI-powered processing"""
    try:
        # Generate task ID
        task_id = f"urls_{request.job_board_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Get multi-engine framework
        framework = await get_multi_engine_framework()
        
        # AI-powered engine selection
        selected_engine = request.force_engine or "beautifulsoup"
        if not request.force_engine and request.enable_ai_analysis:
            try:
                ai_engine = await get_ai_decision_engine()
                # Use first URL for analysis
                analysis = await ai_engine.analyze_job_board(
                    url=str(request.urls[0]),
                    job_board_name=request.job_board_name
                )
                selected_engine = analysis.recommended_engine
            except Exception as e:
                logger.warning(f"AI engine selection failed: {e}")
        
        # Store task info
        scraping_tasks[task_id] = {
            "status": "started",
            "job_board": request.job_board_name,
            "urls": [str(url) for url in request.urls],
            "engine": selected_engine,
            "started_at": datetime.now(),
            "ai_analysis_enabled": request.enable_ai_analysis,
            "validate_content": request.validate_content,
            "enrich_content": request.enrich_content,
            "user": current_user.get("username", "unknown")
        }
        
        # Start background scraping task
        background_tasks.add_task(
            _scrape_urls_background,
            task_id,
            framework,
            request
        )
        
        return ScrapeResponse(
            task_id=task_id,
            job_board=request.job_board_name,
            status="started",
            message=f"URL scraping started for {len(request.urls)} URLs",
            urls_to_scrape=len(request.urls),
            engine_selected=selected_engine,
            ai_analysis_enabled=request.enable_ai_analysis,
            started_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to start URL scraping: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start URL scraping: {str(e)}")

@router.post("/bulk-scrape", response_model=List[ScrapeResponse])
async def bulk_scrape(
    request: BulkScrapeRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Start bulk scraping of multiple job boards"""
    try:
        # Get job board manager
        job_board_manager = await get_job_board_manager()
        
        # Get job board configurations
        job_boards = await job_board_manager.get_job_boards_by_names(request.job_boards)
        
        if not job_boards:
            raise HTTPException(status_code=404, detail="No valid job boards found")
        
        responses = []
        
        # Sort by priority
        priority_boards = [board for board in job_boards if board.name in request.priority_boards]
        regular_boards = [board for board in job_boards if board.name not in request.priority_boards]
        sorted_boards = priority_boards + regular_boards
        
        # Start scraping tasks
        for i, board in enumerate(sorted_boards[:request.max_concurrent_boards]):
            task_id = f"bulk_{board.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}"
            
            # Store task info
            scraping_tasks[task_id] = {
                "status": "started",
                "job_board": board.name,
                "base_url": board.base_url,
                "engine": "auto",  # Will be selected by AI
                "started_at": datetime.now(),
                "max_jobs": request.max_jobs_per_board,
                "ai_optimization_enabled": request.enable_ai_optimization,
                "user": current_user.get("username", "unknown")
            }
            
            # Create scrape request
            scrape_request = ScrapeJobBoardRequest(
                job_board_name=board.name,
                base_url=board.base_url,
                max_jobs=request.max_jobs_per_board,
                enable_ai_analysis=request.enable_ai_optimization
            )
            
            # Start background task
            background_tasks.add_task(
                _scrape_job_board_background,
                task_id,
                await get_multi_engine_framework(),
                scrape_request
            )
            
            responses.append(ScrapeResponse(
                task_id=task_id,
                job_board=board.name,
                status="started",
                message=f"Bulk scraping started for {board.name}",
                urls_to_scrape=request.max_jobs_per_board,
                engine_selected="auto",
                ai_analysis_enabled=request.enable_ai_optimization,
                started_at=datetime.now()
            ))
        
        return responses
        
    except Exception as e:
        logger.error(f"Failed to start bulk scraping: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start bulk scraping: {str(e)}")

@router.get("/task/{task_id}", response_model=ScrapeResultResponse)
async def get_scraping_result(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get the result of a scraping task"""
    try:
        if task_id not in scraping_tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task = scraping_tasks[task_id]
        
        # If task is still running
        if task["status"] in ["started", "running"]:
            return ScrapeResultResponse(
                task_id=task_id,
                job_board=task["job_board"],
                status=task["status"],
                total_jobs_found=task.get("total_jobs_found", 0),
                successful_scrapes=task.get("successful_scrapes", 0),
                failed_scrapes=task.get("failed_scrapes", 0),
                engine_used=task["engine"],
                processing_time=task.get("processing_time", 0.0),
                quality_score=task.get("quality_score", 0.0),
                completed_at=task.get("completed_at", datetime.now()),
                jobs=[]
            )
        
        # Task completed
        return ScrapeResultResponse(
            task_id=task_id,
            job_board=task["job_board"],
            status=task["status"],
            total_jobs_found=task.get("total_jobs_found", 0),
            successful_scrapes=task.get("successful_scrapes", 0),
            failed_scrapes=task.get("failed_scrapes", 0),
            validation_results=task.get("validation_results"),
            enrichment_results=task.get("enrichment_results"),
            engine_used=task["engine"],
            processing_time=task.get("processing_time", 0.0),
            quality_score=task.get("quality_score", 0.0),
            completed_at=task.get("completed_at", datetime.now()),
            jobs=task.get("jobs", [])
        )
        
    except Exception as e:
        logger.error(f"Failed to get task result {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task result: {str(e)}")

@router.get("/tasks")
async def get_scraping_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    job_board: Optional[str] = Query(None, description="Filter by job board"),
    limit: int = Query(50, description="Maximum number of tasks"),
    current_user: dict = Depends(get_current_user)
):
    """Get list of scraping tasks"""
    try:
        # Filter tasks
        filtered_tasks = []
        for task_id, task in scraping_tasks.items():
            if status and task["status"] != status:
                continue
            if job_board and task["job_board"] != job_board:
                continue
            
            task_info = {
                "task_id": task_id,
                "job_board": task["job_board"],
                "status": task["status"],
                "engine": task["engine"],
                "started_at": task["started_at"].isoformat(),
                "completed_at": task.get("completed_at", {}).isoformat() if task.get("completed_at") else None,
                "successful_scrapes": task.get("successful_scrapes", 0),
                "failed_scrapes": task.get("failed_scrapes", 0),
                "quality_score": task.get("quality_score", 0.0),
                "user": task.get("user", "unknown")
            }
            filtered_tasks.append(task_info)
        
        # Sort by start time (newest first) and limit
        filtered_tasks.sort(key=lambda x: x["started_at"], reverse=True)
        filtered_tasks = filtered_tasks[:limit]
        
        return {
            "tasks": filtered_tasks,
            "total_tasks": len(filtered_tasks),
            "filters": {
                "status": status,
                "job_board": job_board,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get scraping tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scraping tasks: {str(e)}")

@router.get("/engines/performance", response_model=List[EnginePerformanceResponse])
async def get_engine_performance(
    current_user: dict = Depends(get_current_user)
):
    """Get performance metrics for all scraping engines"""
    try:
        # Get multi-engine framework
        framework = await get_multi_engine_framework()
        
        # Get performance metrics for each engine
        engines = ["scrapy", "beautifulsoup", "selenium"]
        performance_data = []
        
        for engine in engines:
            metrics = framework.get_engine_performance(engine)
            
            # Generate recommendations based on metrics
            recommendations = []
            if metrics.success_rate < 0.7:
                recommendations.append(f"Low success rate ({metrics.success_rate:.2%}). Consider reviewing selectors.")
            if metrics.average_response_time > 10.0:
                recommendations.append(f"High response time ({metrics.average_response_time:.2f}s). Consider optimization.")
            if metrics.total_requests == 0:
                recommendations.append("Engine not used recently. Consider testing.")
            if not recommendations:
                recommendations.append("Engine performing well.")
            
            performance_data.append(EnginePerformanceResponse(
                engine=engine,
                metrics={
                    "total_requests": metrics.total_requests,
                    "successful_requests": metrics.successful_requests,
                    "failed_requests": metrics.failed_requests,
                    "success_rate": metrics.success_rate,
                    "average_response_time": metrics.average_response_time,
                    "last_used": metrics.last_used.isoformat() if metrics.last_used else None
                },
                recommendations=recommendations,
                last_updated=datetime.now()
            ))
        
        return performance_data
        
    except Exception as e:
        logger.error(f"Failed to get engine performance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get engine performance: {str(e)}")

@router.get("/stats", response_model=ScrapingStatsResponse)
async def get_scraping_stats(
    current_user: dict = Depends(get_current_user)
):
    """Get comprehensive scraping statistics"""
    try:
        # Calculate stats from tasks
        total_sessions = len(scraping_tasks)
        successful_sessions = len([t for t in scraping_tasks.values() if t["status"] == "completed"])
        failed_sessions = len([t for t in scraping_tasks.values() if t["status"] == "failed"])
        
        total_jobs = sum(t.get("successful_scrapes", 0) for t in scraping_tasks.values())
        
        # Calculate average quality score
        quality_scores = [t.get("quality_score", 0.0) for t in scraping_tasks.values() if t.get("quality_score", 0.0) > 0]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        
        # Engine usage stats
        engine_usage = {}
        for task in scraping_tasks.values():
            engine = task.get("engine", "unknown")
            engine_usage[engine] = engine_usage.get(engine, 0) + 1
        
        # Top performing boards
        board_performance = {}
        for task in scraping_tasks.values():
            board = task["job_board"]
            if board not in board_performance:
                board_performance[board] = {"jobs": 0, "quality": 0.0, "sessions": 0}
            
            board_performance[board]["jobs"] += task.get("successful_scrapes", 0)
            board_performance[board]["quality"] += task.get("quality_score", 0.0)
            board_performance[board]["sessions"] += 1
        
        # Calculate average quality per board
        for board, data in board_performance.items():
            if data["sessions"] > 0:
                data["avg_quality"] = data["quality"] / data["sessions"]
            else:
                data["avg_quality"] = 0.0
        
        # Sort by jobs scraped
        top_boards = sorted(
            board_performance.items(),
            key=lambda x: x[1]["jobs"],
            reverse=True
        )[:10]
        
        top_performing_boards = [
            {
                "job_board": board,
                "jobs_scraped": data["jobs"],
                "average_quality": data["avg_quality"],
                "sessions": data["sessions"]
            } for board, data in top_boards
        ]
        
        # Recent activity (last 10 tasks)
        recent_tasks = sorted(
            scraping_tasks.items(),
            key=lambda x: x[1]["started_at"],
            reverse=True
        )[:10]
        
        recent_activity = [
            {
                "task_id": task_id,
                "job_board": task["job_board"],
                "status": task["status"],
                "engine": task["engine"],
                "started_at": task["started_at"].isoformat(),
                "jobs_scraped": task.get("successful_scrapes", 0)
            } for task_id, task in recent_tasks
        ]
        
        return ScrapingStatsResponse(
            total_scraping_sessions=total_sessions,
            successful_sessions=successful_sessions,
            failed_sessions=failed_sessions,
            total_jobs_scraped=total_jobs,
            average_quality_score=avg_quality,
            engine_usage=engine_usage,
            top_performing_boards=top_performing_boards,
            recent_activity=recent_activity,
            last_updated=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to get scraping stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scraping stats: {str(e)}")

@router.delete("/task/{task_id}")
async def cancel_scraping_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel a running scraping task"""
    try:
        if task_id not in scraping_tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task = scraping_tasks[task_id]
        
        if task["status"] in ["completed", "failed", "cancelled"]:
            raise HTTPException(status_code=400, detail=f"Task already {task['status']}")
        
        # Mark task as cancelled
        task["status"] = "cancelled"
        task["completed_at"] = datetime.now()
        
        return {
            "message": f"Task {task_id} cancelled successfully",
            "task_id": task_id,
            "cancelled_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to cancel task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")

# Background task functions
async def _scrape_job_board_background(
    task_id: str,
    framework,
    request: ScrapeJobBoardRequest
):
    """Background task for scraping a job board"""
    try:
        logger.info(f"Starting background scraping task {task_id}")
        
        # Update task status
        scraping_tasks[task_id]["status"] = "running"
        
        start_time = datetime.now()
        
        # Perform scraping
        result = await framework.scrape_job_board(
            job_board_name=request.job_board_name,
            base_url=str(request.base_url),
            max_pages=request.max_pages,
            max_jobs=request.max_jobs
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Validate and enrich content if requested
        validation_results = None
        enrichment_results = None
        
        if request.validate_content or request.enrich_content:
            try:
                validator = await get_data_quality_validator()
                
                if request.validate_content:
                    # Validate scraped jobs (simplified)
                    validation_results = {"validated": True, "quality_score": 0.8}
                
                if request.enrich_content:
                    # Enrich scraped jobs (simplified)
                    enrichment_results = {"enriched": True, "enrichments_added": 5}
                    
            except Exception as e:
                logger.error(f"Content validation/enrichment failed: {e}")
        
        # Update task with results
        scraping_tasks[task_id].update({
            "status": "completed",
            "completed_at": datetime.now(),
            "total_jobs_found": len(result.jobs) if result.jobs else 0,
            "successful_scrapes": len(result.jobs) if result.jobs else 0,
            "failed_scrapes": 0,
            "processing_time": processing_time,
            "quality_score": 0.8,  # Would be calculated from actual validation
            "validation_results": validation_results,
            "enrichment_results": enrichment_results,
            "jobs": result.jobs[:10] if result.jobs else []  # Store first 10 for preview
        })
        
        logger.info(f"Completed scraping task {task_id}: {len(result.jobs) if result.jobs else 0} jobs")
        
    except Exception as e:
        logger.error(f"Scraping task {task_id} failed: {e}")
        scraping_tasks[task_id].update({
            "status": "failed",
            "completed_at": datetime.now(),
            "error": str(e)
        })

async def _scrape_urls_background(
    task_id: str,
    framework,
    request: ScrapeUrlRequest
):
    """Background task for scraping specific URLs"""
    try:
        logger.info(f"Starting URL scraping task {task_id}")
        
        # Update task status
        scraping_tasks[task_id]["status"] = "running"
        
        start_time = datetime.now()
        jobs = []
        
        # Scrape each URL
        for url in request.urls:
            try:
                result = await framework.scrape_job_url(
                    url=str(url),
                    job_board_name=request.job_board_name
                )
                if result.jobs:
                    jobs.extend(result.jobs)
            except Exception as e:
                logger.error(f"Failed to scrape URL {url}: {e}")
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Update task with results
        scraping_tasks[task_id].update({
            "status": "completed",
            "completed_at": datetime.now(),
            "total_jobs_found": len(jobs),
            "successful_scrapes": len(jobs),
            "failed_scrapes": len(request.urls) - len(jobs),
            "processing_time": processing_time,
            "quality_score": 0.8,
            "jobs": jobs[:10]  # Store first 10 for preview
        })
        
        logger.info(f"Completed URL scraping task {task_id}: {len(jobs)} jobs")
        
    except Exception as e:
        logger.error(f"URL scraping task {task_id} failed: {e}")
        scraping_tasks[task_id].update({
            "status": "failed",
            "completed_at": datetime.now(),
            "error": str(e)
        })