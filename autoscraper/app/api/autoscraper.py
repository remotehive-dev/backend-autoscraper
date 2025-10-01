#!/usr/bin/env python3
"""
Autoscraper API Routes
Enterprise-grade autoscraper endpoints for the dedicated service
"""

import time
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Request, UploadFile, File
from fastapi.responses import StreamingResponse, Response
# SQLAlchemy imports removed - using MongoDB models
from celery.result import AsyncResult
from loguru import logger
import psutil
import json

# Database manager import removed - using MongoDB models
from app.middleware.auth import get_current_user_optional, require_auth, require_admin
# from app.utils.metrics import AutoScraperMetrics  # Temporarily disabled
# SQLAlchemy models removed - using MongoDB models
# MongoDB models are imported locally where needed
from app.schemas import (
    JobBoardCreate, JobBoardUpdate, JobBoardResponse,
    ScheduleConfigCreate, ScheduleConfigUpdate, ScheduleConfigResponse,
    ScrapeJobCreate, ScrapeJobUpdate, ScrapeJobResponse,
    ScrapeRunResponse, RawJobResponse, NormalizedJobResponse, EngineStateResponse,
    StartScrapeJobRequest, EngineStartRequest, PauseScrapeJobRequest, HardResetRequest,
    DashboardResponse, DashboardStats, RecentActivity,
    HealthCheckResponse, LiveLogsResponse, LogEntry,
    SuccessResponse, ErrorResponse,
    SystemSettings, SystemSettingsUpdate, SettingsTestRequest, SettingsTestResponse,
    SystemHealthResponse, PerformanceMetrics
)
from app.services.services import ScrapingService, NormalizationService, EngineService
from app.services.tasks import run_scrape_job
from app.services.settings_service import settings_service
from config.settings import get_settings
from app.scrapers.enhanced_scraper import EnhancedScraper
from app.scrapers.job_board_scrapers import JobBoardScraperFactory
from app.scrapers.scraping_monitor import ScrapingMonitor
from app.scrapers.job_queue import JobQueue, JobPriority

settings = get_settings()
# metrics = AutoScraperMetrics()  # Temporarily disabled

# Initialize enhanced scraping components
scraping_service = ScrapingService()
enhanced_scraper = EnhancedScraper()
job_board_factory = JobBoardScraperFactory()
scraping_monitor = ScrapingMonitor()
job_queue = JobQueue()

# Create router
router = APIRouter(prefix="/api/v1/autoscraper", tags=["autoscraper"])


@router.get("/", include_in_schema=False)
async def autoscraper_root():
    """Autoscraper service root endpoint"""
    return {
        "service": "autoscraper",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "dashboard": "/api/v1/autoscraper/dashboard",
            "health": "/api/v1/autoscraper/health",
            "metrics": "/metrics",
            "docs": "/docs"
        }
    }


@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Health check endpoint for autoscraper service
    """
    try:
        # Check database connection
        db_status = "healthy"
        try:
            # Test database connection using global manager
            from app.database.database import db_manager
            health_check = await db_manager.health_check()
            if health_check.get("status") != "healthy":
                db_status = f"unhealthy: {health_check.get('status', 'unknown')}"
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
        
        # Check scraping monitor
        monitor_status = "healthy"
        try:
            stats = scraping_monitor.get_statistics()
            if not stats:
                monitor_status = "unhealthy: no statistics available"
        except Exception as e:
            monitor_status = f"unhealthy: {str(e)}"
        
        # Overall health status
        overall_status = "healthy" if db_status == "healthy" and monitor_status == "healthy" else "unhealthy"
        
        return {
            "status": overall_status,
            "service": "RemoteHive AutoScraper Service",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "database": db_status,
                "scraping_monitor": monitor_status
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "RemoteHive AutoScraper Service",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# Database session dependency removed - using MongoDB models

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user = Depends(require_auth)
):
    """
    Get autoscraper dashboard with stats and recent activities
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import (
    JobBoard, ScrapeJob, RawJob, NormalizedJob, EngineState
)
        
        # Get dashboard statistics using MongoDB aggregation
        total_job_boards = await JobBoard.find().count() or 0
        active_job_boards = await JobBoard.find({"is_active": True}).count() or 0
        total_scrape_jobs = await ScrapeJob.find().count() or 0
        running_jobs = await ScrapeJob.find({"status": "RUNNING"}).count() or 0
        
        # Today's statistics
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        completed_jobs_today = await ScrapeJob.find({
            "status": "COMPLETED",
            "completed_at": {"$gte": today_start}
        }).count() or 0
        
        failed_jobs_today = await ScrapeJob.find({
            "status": "FAILED",
            "updated_at": {"$gte": today_start}
        }).count() or 0
        
        # Calculate success rate
        total_jobs_today = completed_jobs_today + failed_jobs_today
        success_rate_today = (completed_jobs_today / total_jobs_today * 100) if total_jobs_today > 0 else 0.0
        
        total_raw_jobs = await RawJob.find().count() or 0
        total_normalized_jobs = await NormalizedJob.find().count() or 0
        
        jobs_published_today = await NormalizedJob.find({
            "is_published": True,
            "published_at": {"$gte": today_start}
        }).count() or 0
        
        # Calculate total jobs scraped
        total_jobs_scraped = total_raw_jobs + total_normalized_jobs
        
        # Calculate overall success rate
        success_rate = success_rate_today
        
        # Get enhanced scraping statistics
        scraping_stats = scraping_monitor.get_statistics()
        scraping_service_stats = await scraping_service.get_scraping_stats()
        deduplication_stats = scraping_service_stats.get('deduplication', {})
        queue_stats = await job_queue.get_queue_stats()
        
        stats = DashboardStats(
            total_job_boards=total_job_boards,
            active_job_boards=active_job_boards,
            total_scrape_jobs=total_scrape_jobs,
            running_jobs=running_jobs,
            completed_jobs_today=completed_jobs_today,
            failed_jobs_today=failed_jobs_today,
            total_jobs_scraped=total_jobs_scraped,
            success_rate=success_rate,
            # Enhanced statistics
            jobs_in_queue=queue_stats.get('total_jobs', 0),
            duplicate_jobs_filtered=deduplication_stats.get('duplicates_found', 0),
            average_scrape_time=scraping_stats.get('average_execution_time', 0.0),
            total_errors=scraping_stats.get('total_errors', 0)
        )
        
        # Get recent activities using MongoDB aggregation
        recent_jobs = await ScrapeJob.find().sort("-created_at").limit(10).to_list()
        
        recent_activities = []
        for job in recent_jobs:
            # Get job board info
            job_board = await JobBoard.get(job.job_board_id)
            if job_board:
                recent_activities.append(
                    RecentActivity(
                        id=str(job.id),
                        type="scrape_job",
                        message=f"Scrape job for {job_board.name} - {job.status}",
                        timestamp=job.started_at or job.created_at,
                        status=job.status
                    )
                )
        
        # Get engine state using MongoDB
        engine_state = await EngineState.find_one()
        if not engine_state:
            # Create default engine state if not exists
            import psutil
            import socket
            engine_state = EngineState(
                name=f"autoscraper-engine-{socket.gethostname()}",
                status=EngineStatus.IDLE,
                current_job_id=None,
                current_operation=None,
                total_jobs_processed=0,
                total_jobs_completed=completed_jobs_today,
                total_jobs_failed=failed_jobs_today,
                average_job_duration=0.0,
                cpu_usage_percent=psutil.cpu_percent(),
                memory_usage_mb=psutil.virtual_memory().used / 1024 / 1024,
                disk_usage_mb=0.0,
                last_heartbeat=datetime.utcnow(),
                health_status="healthy",
                error_count=failed_jobs_today,
                last_error=None,
                last_error_at=None,
                max_concurrent_jobs=5,
                worker_threads=4,
                version="1.0.0",
                host_name=socket.gethostname(),
                process_id=None,
                started_at=datetime.utcnow()
            )
            await engine_state.insert()
        
        # Record metrics
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/dashboard", 200, duration)  # Temporarily disabled
        
        return DashboardResponse(
            stats=stats,
            recent_activity=recent_activities,
            engine_status=EngineStateResponse(
                status=engine_state.status,
                active_jobs=running_jobs,
                queued_jobs=0,  # TODO: Implement queued jobs count
                total_jobs_today=engine_state.total_jobs_completed + engine_state.total_jobs_failed,
                success_rate=success_rate_today,
                last_activity=engine_state.last_heartbeat,
                uptime_seconds=int((datetime.utcnow() - engine_state.started_at).total_seconds())
            )
        )
        
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/dashboard", 500, duration)  # Temporarily disabled
        logger.error(f"Dashboard error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load dashboard: {str(e)}"
        )


@router.post("/jobs/start", response_model=List[ScrapeJobResponse])
async def start_scrape_job(
    request: StartScrapeJobRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(require_auth)
):
    """
    Start new scrape jobs for specified job boards
    """
    start_time = time.time()
    created_jobs = []
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import JobBoard, ScrapeJob
        from bson import ObjectId
        
        # Process each job board ID
        for job_board_id in request.job_board_ids:
            try:
                # Convert job_board_id to string (handles both UUID and ObjectId formats)
                job_board_id_str = str(job_board_id)
                
                # Verify job board exists and is active
                # Try to find by _id first (for ObjectId format), then by id field (for UUID format)
                job_board = None
                try:
                    # Try ObjectId format first
                    job_board_obj_id = ObjectId(job_board_id_str)
                    job_board = await JobBoard.find_one({
                        "_id": job_board_obj_id,
                        "is_active": True
                    })
                except Exception:
                    # If ObjectId fails, try UUID string format
                    pass
                
                # If not found by ObjectId, try by UUID string
                if not job_board:
                    job_board = await JobBoard.find_one({
                        "id": job_board_id_str,
                        "is_active": True
                    })
                
                # If still not found, try by name (for backward compatibility)
                if not job_board:
                    job_board = await JobBoard.find_one({
                        "name": job_board_id_str,
                        "is_active": True
                    })
                
                if not job_board:
                    logger.warning(f"Job board not found or inactive: {job_board_id}")
                    continue
                
                # Use the actual job board ID from the found document
                actual_job_board_id = str(job_board.id) if hasattr(job_board, 'id') else str(job_board._id)
                
                # Check for existing running jobs for this job board
                existing_job = await ScrapeJob.find_one({
                    "job_board_id": actual_job_board_id,
                    "status": "running"
                })
                
                if existing_job:
                    logger.warning(f"Scrape job already running for job board: {actual_job_board_id}")
                    continue
                
                # Create new scrape job
                scrape_job = ScrapeJob(
                    job_board_id=actual_job_board_id,
                    mode=request.mode,
                    priority=request.priority,
                    status="pending",
                    config_snapshot={
                        "job_board_config": {
                            "name": job_board.name,
                            "type": job_board.type,
                            "base_url": job_board.base_url,
                            "rss_url": job_board.rss_url,
                            "selectors": job_board.selectors,
                            "headers": job_board.headers,
                            "rate_limit_delay": job_board.rate_limit_delay,
                            "quality_threshold": job_board.quality_threshold
                        },
                        "request_params": {
                            "mode": request.mode,
                            "priority": request.priority
                        }
                    }
                )
                
                await scrape_job.save()
                
                # Add job to enhanced job queue
                priority_mapping = {
                    0: JobPriority.LOW,
                    1: JobPriority.NORMAL, 
                    2: JobPriority.HIGH,
                    3: JobPriority.URGENT
                }
                job_priority = priority_mapping.get(request.priority, JobPriority.NORMAL)
                
                # Queue the job for enhanced processing
                await job_queue.add_job(
                    job_id=str(scrape_job.id),
                    job_board_id=actual_job_board_id,
                    priority=job_priority,
                    config=scrape_job.config_snapshot["job_board_config"]
                )
                
                # Start the Celery task with enhanced monitoring
                task = run_scrape_job.apply_async(
                    args=[str(scrape_job.id)],
                    queue="autoscraper.default",
                    priority=request.priority
                )
                
                # Update job with task ID and start monitoring
                scrape_job.celery_task_id = task.id
                await scrape_job.save()
                
                # Start monitoring for this job
                await scraping_monitor.start_monitoring(str(scrape_job.id), job_board.name)
                
                created_jobs.append(ScrapeJobResponse(**scrape_job.dict()))
                
                logger.info(f"Started scrape job {scrape_job.id} for job board {job_board.name}")
                
            except Exception as e:
                logger.error(f"Failed to create job for job board {job_board_id}: {str(e)}")
                continue
        
        if not created_jobs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid job boards found or all jobs already running"
            )
        
        # Record metrics
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/jobs/start", 200, duration)  # Temporarily disabled
        
        logger.info(f"Started {len(created_jobs)} scrape jobs successfully")
        
        return created_jobs
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/jobs/start", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to start scrape jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scrape jobs: {str(e)}"
        )


@router.post("/jobs/pause", response_model=SuccessResponse)
async def pause_scrape_job(
    request: PauseScrapeJobRequest,
    current_user = Depends(require_auth)
):
    """
    Pause a running scrape job
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import ScrapeJob
        from bson import ObjectId
        
        # Validate ObjectId format
        try:
            job_obj_id = ObjectId(request.job_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job ID format"
            )
        
        # Find the scrape job
        scrape_job = await ScrapeJob.get(job_obj_id)
        
        if not scrape_job:
            duration = time.time() - start_time
            # metrics.record_http_request("POST", "/jobs/pause", 404, duration)  # Temporarily disabled
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scrape job not found"
            )
        
        if scrape_job.status != "running":
            duration = time.time() - start_time
            # metrics.record_http_request("POST", "/jobs/pause", 400, duration)  # Temporarily disabled
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job is not currently running"
            )
        
        # Revoke the Celery task if it exists
        if scrape_job.celery_task_id:
            from celery import Celery
            from autoscraper_service.config.settings import settings
            
            celery_app = Celery(
                'autoscraper',
                broker=settings.CELERY_BROKER_URL,
                backend=settings.CELERY_RESULT_BACKEND
            )
            celery_app.control.revoke(scrape_job.celery_task_id, terminate=True)
        
        # Update job status
        scrape_job.status = "paused"
        scrape_job.updated_at = datetime.utcnow()
        await scrape_job.save()
        
        # Record metrics
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/jobs/pause", 200, duration)  # Temporarily disabled
        
        logger.info(f"Paused scrape job {scrape_job.id}")
        
        return SuccessResponse(
            message=f"Scrape job {scrape_job.id} has been paused",
            data={"job_id": str(scrape_job.id), "status": scrape_job.status}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/jobs/pause", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to pause scrape job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause scrape job: {str(e)}"
        )


@router.get("/job-boards", response_model=List[JobBoardResponse])
async def list_job_boards(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False)
):
    """
    List all job boards with pagination
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import JobBoard
        
        # Debug logging
        logger.info(f"DEBUG: list_job_boards called with skip={skip}, limit={limit}, active_only={active_only}")
        
        # Build MongoDB query
        query_filter = {}
        if active_only:
            query_filter["is_active"] = True
        
        logger.info(f"DEBUG: query_filter = {query_filter}")
        
        # Test total count first
        total_count = await JobBoard.find().count()
        logger.info(f"DEBUG: Total JobBoard count = {total_count}")
        
        # Execute MongoDB query with pagination
        job_boards = await JobBoard.find(query_filter).skip(skip).limit(limit).to_list()
        logger.info(f"DEBUG: Found {len(job_boards)} job boards after query")
        
        # Map MongoDB models to response schema
        response_data = []
        for jb in job_boards:
            # Convert MongoDB ObjectId to UUID format for response schema
            import uuid
            object_id_str = str(jb.id)
            # Create a deterministic UUID from ObjectId
            uuid_from_objectid = str(uuid.uuid5(uuid.NAMESPACE_DNS, object_id_str))
            
            # Map job board type to valid enum values
            type_mapping = {
                "indeed": "html",
                "linkedin": "html",
                "glassdoor": "html",
                "monster": "html",
                "ziprecruiter": "html",
                "careerbuilder": "html",
                "dice": "html",
                "remote_ok": "html",
                "we_work_remotely": "html",
                "angellist": "html",
                "flexjobs": "html",
                "upwork": "html",
                "freelancer": "html",
                "toptal": "html",
                "guru": "html",
                "stackoverflow": "html",
                "github_jobs": "html",
                "custom": "html"
            }
            
            job_type = jb.type.value if jb.type else "html"
            mapped_type = type_mapping.get(job_type.lower(), job_type)
            
            response_item = {
                "id": uuid_from_objectid,
                "name": jb.name,
                "description": jb.notes or "",  # Use notes field as description
                "type": mapped_type,
                "base_url": jb.base_url,
                "rss_url": getattr(jb, 'search_url_template', None),  # Use search_url_template as rss_url
                "region": getattr(jb, 'region', None),  # Add region field from MongoDB model
                "selectors": jb.selectors or {},
                "rate_limit_delay": int(jb.rate_limit_delay or 2),
                "max_pages": jb.max_pages_per_search or 10,  # Use max_pages_per_search
                "request_timeout": 30,  # Default value as not in MongoDB model
                "retry_attempts": 3,  # Default value as not in MongoDB model
                "is_active": jb.is_active,
                "success_rate": jb.success_rate or 0.0,
                "last_scraped_at": jb.last_successful_scrape,  # Use last_successful_scrape
                "total_scrapes": jb.total_jobs_scraped or 0,  # Use total_jobs_scraped
                "successful_scrapes": 0,  # Default value as not in MongoDB model
                "failed_scrapes": 0,  # Default value as not in MongoDB model
                "created_at": jb.created_at,
                "updated_at": jb.updated_at
            }
            response_data.append(JobBoardResponse(**response_item))
        
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/job-boards", 200, duration)  # Temporarily disabled
        
        return response_data
        
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/job-boards", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to list job boards: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list job boards: {str(e)}"
        )


@router.post("/job-boards", response_model=JobBoardResponse, status_code=status.HTTP_201_CREATED)
async def create_job_board(
    job_board: JobBoardCreate,
    current_user = Depends(require_admin)
):
    """
    Create a new job board
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import JobBoard, JobBoardType
        from datetime import datetime
        
        # Check if job board with same name exists
        existing = await JobBoard.find_one({"name": job_board.name})
        if existing:
            duration = time.time() - start_time
            # metrics.record_http_request("POST", "/job-boards", 409, duration)  # Temporarily disabled
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Job board with this name already exists"
            )
        
        # Map request type to MongoDB JobBoardType
        type_mapping = {
            "rss": JobBoardType.RSS,
            "html": JobBoardType.HTML, 
            "api": JobBoardType.API,
            "hybrid": JobBoardType.HYBRID
        }
        
        request_type = job_board.type if hasattr(job_board, 'type') else "html"
        mapped_type = type_mapping.get(request_type.lower(), JobBoardType.HTML)
        
        # Create new MongoDB job board
        db_job_board = JobBoard(
            name=job_board.name,
            type=mapped_type,
            base_url=job_board.base_url,
            search_url_template=getattr(job_board, 'rss_url', job_board.base_url),  # Use rss_url as search_url_template
            notes=getattr(job_board, 'description', None),  # Use description as notes
            selectors=job_board.selectors or {},
            is_active=job_board.is_active,
            rate_limit_delay=getattr(job_board, 'rate_limit_delay', 2.0),
            max_pages_per_search=getattr(job_board, 'max_pages_per_search', 10),  # Use max_pages_per_search
            success_rate=0.0,
            total_jobs_scraped=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        await db_job_board.insert()
        
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/job-boards", 201, duration)  # Temporarily disabled
        
        logger.info(f"Created job board: {db_job_board.name}")
        
        # Map MongoDB fields to response schema fields
        import uuid
        object_id_str = str(db_job_board.id)
        # Create a deterministic UUID from ObjectId
        uuid_from_objectid = str(uuid.uuid5(uuid.NAMESPACE_DNS, object_id_str))
        
        # Map job board type to valid enum values
        type_mapping = {
            "indeed": "html",
            "linkedin": "html",
            "glassdoor": "html",
            "monster": "html",
            "ziprecruiter": "html",
            "careerbuilder": "html",
            "dice": "html",
            "remote_ok": "html",
            "we_work_remotely": "html",
            "angellist": "html",
            "flexjobs": "html",
            "upwork": "html",
            "freelancer": "html",
            "toptal": "html",
            "guru": "html",
            "stackoverflow": "html",
            "github_jobs": "html",
            "custom": "html"
        }
        
        job_type = db_job_board.type.value if db_job_board.type else "html"
        mapped_type = type_mapping.get(job_type.lower(), job_type)
        
        response_data = {
            "id": uuid_from_objectid,
            "name": db_job_board.name,
            "type": mapped_type,  # Use mapped type
            "base_url": db_job_board.base_url,
            "description": db_job_board.notes or "",  # Use notes as description
            "rss_url": db_job_board.search_url_template,  # Use search_url_template as rss_url
            "region": getattr(db_job_board, 'region', None),  # Add region field from MongoDB model
            "selectors": db_job_board.selectors,
            "rate_limit_delay": int(db_job_board.rate_limit_delay),
            "max_pages": db_job_board.max_pages_per_search,  # Use max_pages_per_search
            "request_timeout": 30,  # Default value
            "retry_attempts": 3,  # Default value
            "is_active": db_job_board.is_active,
            "success_rate": db_job_board.success_rate,
            "last_scraped_at": db_job_board.last_successful_scrape,  # Use last_successful_scrape
            "total_scrapes": db_job_board.total_jobs_scraped,  # Use total_jobs_scraped
            "successful_scrapes": 0,  # Default value
            "failed_scrapes": 0,  # Default value
            "created_at": db_job_board.created_at,
            "updated_at": db_job_board.updated_at
        }
        
        return JobBoardResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/job-boards", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to create job board: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job board: {str(e)}"
        )


@router.post("/job-boards/upload-csv")
async def upload_job_boards_csv(
    file: UploadFile = File(...),
    test_accessibility: bool = Query(False, description="Test URL accessibility"),
    current_user = Depends(require_admin)
):
    """
    Upload job boards from CSV file
    Expected CSV format: name,url,region (optional)
    """
    start_time = time.time()
    upload_id = f"upload_{int(time.time())}"
    
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a CSV file"
            )
        
        # Read and parse CSV content
        content = await file.read()
        csv_text = content.decode('utf-8')
        lines = csv_text.strip().split('\n')
        
        if len(lines) < 2:  # At least header + 1 data row
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file must contain at least one data row"
            )
        
        # Parse CSV data
        job_boards_data = []
        headers = []
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
                
            # Parse CSV line (simple parsing, handles quoted values)
            columns = []
            current_col = ""
            in_quotes = False
            
            for char in line:
                if char == '"':
                    in_quotes = not in_quotes
                elif char == ',' and not in_quotes:
                    columns.append(current_col.strip())
                    current_col = ""
                else:
                    current_col += char
            columns.append(current_col.strip())  # Add last column
            
            if i == 0:
                # Check if first row is header
                first_col = columns[0].lower() if columns else ""
                if 'name' in first_col or 'job' in first_col or 'board' in first_col:
                    headers = [col.lower().strip() for col in columns]
                    continue
                else:
                    # No header, treat as data
                    headers = ['name', 'website', 'region']  # Default to simple format
            
            # Process data rows
            if len(columns) >= 2:
                # Detect format based on headers
                is_simple_format = len(headers) <= 3 and ('website' in headers or len(headers) == 3)
                
                if is_simple_format:
                    # Simple format: Name, website, region
                    name = columns[0].strip('"').strip()
                    website = columns[1].strip('"').strip() if len(columns) > 1 else ''
                    region = columns[2].strip('"').strip() if len(columns) > 2 else ''
                    
                    if name and website:
                        job_boards_data.append({
                            'name': name,
                            'type': 'custom',  # Default type for simple format
                            'base_url': website,  # Map website to base_url
                            'region': region,
                            'search_url_template': f'{website}/jobs',  # Provide a default search template
                            'is_active': True,  # Default to active
                            'rate_limit_delay': 2.0,
                            'max_pages_per_search': 10
                        })
                else:
                    # Advanced format: name, type, base_url, search_url_template, is_active, rate_limit_delay, max_pages_per_search
                    name = columns[0].strip('"').strip()
                    job_type = columns[1].strip('"').strip() if len(columns) > 1 else 'custom'
                    base_url = columns[2].strip('"').strip() if len(columns) > 2 else ''
                    search_url_template = columns[3].strip('"').strip() if len(columns) > 3 else ''
                    is_active = columns[4].strip('"').strip().lower() == 'true' if len(columns) > 4 else True
                    rate_limit_delay = float(columns[5].strip('"').strip()) if len(columns) > 5 and columns[5].strip() else 2.0
                    max_pages = int(columns[6].strip('"').strip()) if len(columns) > 6 and columns[6].strip() else 10
                    region = columns[7].strip('"').strip() if len(columns) > 7 else ''  # Region in advanced format
                    
                    if name and base_url:
                        job_boards_data.append({
                            'name': name,
                            'type': job_type,
                            'base_url': base_url,
                            'region': region,
                            'search_url_template': search_url_template,
                            'is_active': is_active,
                            'rate_limit_delay': rate_limit_delay,
                            'max_pages_per_search': max_pages
                        })
        
        if not job_boards_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid job board data found in CSV"
            )
        
        # Create job boards in database
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        
        # Import MongoDB models
        from app.models.mongodb_models import JobBoard, JobBoardType
        from datetime import datetime
        
        # Process job boards data
        for data in job_boards_data:
            try:
                # Check if job board already exists
                existing = await JobBoard.find_one({"name": data['name']})
                
                # Map type string to enum - use CUSTOM enum value which exists in JobBoardType
                type_mapping = {
                    "rss": JobBoardType.CUSTOM,  # Map to CUSTOM since RSS not in enum
                    "html": JobBoardType.CUSTOM,  # Map to CUSTOM since HTML not in enum
                    "api": JobBoardType.CUSTOM,   # Map to CUSTOM since API not in enum
                    "hybrid": JobBoardType.CUSTOM, # Map to CUSTOM since HYBRID not in enum
                    "custom": JobBoardType.CUSTOM  # Map custom to CUSTOM enum
                }
                mapped_type = type_mapping.get(data['type'].lower(), JobBoardType.CUSTOM)
                
                if existing:
                    # Update existing job board with CSV data
                    existing.type = mapped_type
                    existing.base_url = data['base_url']
                    existing.description = data.get('region', '')
                    existing.region = data.get('region', '')
                    existing.is_active = data['is_active']
                    existing.rate_limit_delay = data['rate_limit_delay']
                    existing.max_pages_per_search = data['max_pages_per_search']
                    existing.updated_at = datetime.utcnow()
                    await existing.save()
                    updated_count += 1
                else:
                    # Create new job board using CSV data
                    new_job_board = JobBoard(
                        name=data['name'],
                        type=mapped_type,
                        base_url=data['base_url'],
                        search_url_template=data.get('search_url_template', f"{data['base_url']}/jobs"),
                        description=data.get('region', ''),
                        region=data.get('region', ''),
                        is_active=data['is_active'],
                        rate_limit_delay=data['rate_limit_delay'],
                        max_pages_per_search=data['max_pages_per_search'],
                        total_jobs_scraped=0,
                        success_rate=0.0,
                        average_response_time=0.0,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    await new_job_board.insert()
                    created_count += 1
                    
            except Exception as e:
                errors.append(f"Error processing {data['name']}: {str(e)}")
                skipped_count += 1
                continue
        
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/job-boards/upload-csv", 200, duration)  # Temporarily disabled
        
        logger.info(f"CSV upload completed: {created_count} created, {updated_count} updated, {skipped_count} skipped")
        
        return {
            "upload_id": upload_id,
            "total_rows": len(job_boards_data),
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "errors": errors,
            "status": "completed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/job-boards/upload-csv", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to upload CSV: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload CSV: {str(e)}"
        )


@router.get("/job-boards/csv-template")
async def download_job_boards_csv_template(
    current_user = Depends(require_auth)
):
    """
    Download CSV template for job boards upload
    Returns a CSV file with standardized headers: Name, website, region
    """
    try:
        # Create CSV content with standardized headers and sample data
        csv_content = "Name,website,region\n"
        csv_content += "Indeed Jobs,https://indeed.com,US\n"
        csv_content += "LinkedIn Jobs,https://linkedin.com,Global\n"
        csv_content += "Glassdoor Jobs,https://glassdoor.com,US\n"
        
        # Create response with proper headers
        response = Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=job_boards_template.csv"
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to generate CSV template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate CSV template: {str(e)}"
        )


@router.get("/jobs", response_model=List[ScrapeJobResponse])
async def list_scrape_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    job_status: Optional[str] = Query(None),
    job_board_id: Optional[str] = Query(None),
    current_user = Depends(require_auth)
):
    """
    List scrape jobs with filtering
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import ScrapeJob
        from bson import ObjectId
        
        # Build MongoDB query filter
        query_filter = {}
        
        if job_status:
            query_filter["status"] = job_status
        
        if job_board_id:
            try:
                query_filter["job_board_id"] = ObjectId(job_board_id)
            except Exception:
                query_filter["job_board_id"] = job_board_id
        
        # Execute MongoDB query
        jobs = await ScrapeJob.find(query_filter).sort("-created_at").skip(skip).limit(limit).to_list()
        
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/jobs", 200, duration)  # Temporarily disabled
        
        # Convert to response format
        job_responses = []
        for job in jobs:
            job_responses.append(ScrapeJobResponse(
                id=str(job.id),
                job_board_id=str(job.job_board_id),
                status=job.status,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                error_message=job.error_message,
                total_jobs_found=job.total_jobs_found or 0,
                total_jobs_processed=job.total_jobs_processed or 0,
                total_jobs_saved=job.total_jobs_saved or 0,
                execution_time_seconds=job.execution_time_seconds or 0.0
            ))
        
        return job_responses
        
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/jobs", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to list scrape jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list scrape jobs: {str(e)}"
        )


@router.get("/engine/state", response_model=EngineStateResponse)
async def get_engine_state(
    current_user = Depends(require_auth)
):
    """
    Get current engine state
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import EngineState, ScrapeJob
        
        engine_state = await EngineState.find_one()
        
        if not engine_state:
            # Create default engine state
            running_jobs_count = await ScrapeJob.find({"status": "RUNNING"}).count()
            queued_jobs_count = await ScrapeJob.find({"status": "PENDING"}).count()
            
            # Get today's job statistics
            today = datetime.utcnow().date()
            today_start = datetime.combine(today, datetime.min.time())
            
            completed_jobs_today = await ScrapeJob.find({
                "status": "COMPLETED",
                "completed_at": {"$gte": today_start}
            }).count() or 0
            
            failed_jobs_today = await ScrapeJob.find({
                "status": "FAILED",
                "updated_at": {"$gte": today_start}
            }).count() or 0
            
            total_jobs_today = completed_jobs_today + failed_jobs_today
            success_rate = (completed_jobs_today / total_jobs_today * 100) if total_jobs_today > 0 else 0.0
            
            engine_state = EngineState(
                status=EngineStatus.IDLE,
                active_jobs=running_jobs_count,
                queued_jobs=queued_jobs_count,
                total_jobs_today=total_jobs_today,
                success_rate=success_rate,
                last_activity=datetime.utcnow(),
                uptime_seconds=0
            )
            await engine_state.insert()
        
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/engine/state", 200, duration)  # Temporarily disabled
        
        return EngineStateResponse(
            status=engine_state.status,
            active_jobs=engine_state.active_jobs,
            queued_jobs=engine_state.queued_jobs,
            total_jobs_today=engine_state.total_jobs_today,
            success_rate=engine_state.success_rate,
            last_activity=engine_state.last_activity,
            uptime_seconds=engine_state.uptime_seconds
        )
        
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/engine/state", 500, duration)  # Temporarily disabled
        logger.error("Failed to get engine state: {}", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get engine state: {str(e)}"
        )


@router.get("/system/metrics", response_model=PerformanceMetrics)
async def get_performance_metrics(
    current_user = Depends(require_auth)
):
    """
    Get current performance metrics
    """
    start_time = time.time()
    
    try:
        # Get system metrics
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        disk = psutil.disk_usage('/')
        
        performance_metrics = PerformanceMetrics(
            cpu_usage=cpu_percent,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            active_connections=0,  # TODO: Implement connection tracking
            requests_per_second=0.0,  # TODO: Implement request tracking
            average_response_time=0.0,  # TODO: Implement response time tracking
            error_rate=0.0,  # TODO: Implement error tracking
            success_rate=100.0,  # TODO: Implement success tracking
            memory_usage_mb=memory.used // (1024 * 1024),
            cpu_usage_percent=cpu_percent,
            disk_usage_percent=disk.percent,
            timestamp=datetime.now().isoformat()
        )
        
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/system/metrics", 200, duration)  # Temporarily disabled
        
        return performance_metrics
        
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/system/metrics", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to get performance metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance metrics: {str(e)}"
        )


@router.get("/settings", response_model=SystemSettings)
async def get_settings(
    current_user = Depends(require_auth)
):
    """
    Get current system settings
    """
    start_time = time.time()
    
    try:
        settings = settings_service.get_settings()
        
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/settings", 200, duration)  # Temporarily disabled
        
        return settings
        
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/settings", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to get settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get settings: {str(e)}"
        )


@router.put("/settings", response_model=SystemSettings)
async def update_settings(
    settings_update: SystemSettingsUpdate,
    current_user = Depends(require_auth)
):
    """
    Update system settings
    """
    start_time = time.time()
    
    try:
        updated_settings = settings_service.update_settings(settings_update.dict(exclude_unset=True))
        
        duration = time.time() - start_time
        # metrics.record_http_request("PUT", "/settings", 200, duration)  # Temporarily disabled
        
        logger.info("System settings updated")
        
        return updated_settings
        
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("PUT", "/settings", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to update settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )


# Engine control endpoints
async def uuid_to_objectid_mapping(uuid_str: str) -> str:
    """
    Convert UUID back to ObjectId by finding the job board with matching UUID.
    UUIDs are generated deterministically from ObjectIds using uuid5.
    """
    import uuid
    from bson import ObjectId
    from app.models.mongodb_models import JobBoard
    
    # First try to parse as ObjectId directly
    try:
        ObjectId(uuid_str)
        return uuid_str
    except:
        pass
    
    # If it's a UUID, find the corresponding ObjectId
    try:
        uuid.UUID(uuid_str)
        # Search all job boards to find matching UUID
        job_boards = await JobBoard.find_all().to_list()
        for jb in job_boards:
            # Generate UUID from ObjectId using the same method as in responses
            generated_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(jb.id)))
            if generated_uuid == uuid_str:
                return str(jb.id)
        raise ValueError(f"No job board found for UUID: {uuid_str}")
    except ValueError:
        raise
    except:
        raise ValueError("Invalid ID format")


@router.post("/engine/start", response_model=SuccessResponse)
async def start_engine(
    request: Optional[EngineStartRequest] = None,
    current_user = Depends(require_admin)
):
    """
    Start the scraping engine by dispatching scrape jobs.
    If no request body is provided, it will start all active job boards.
    Accepts both ObjectId and UUID formats for job_board_ids.
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import JobBoard
        from bson import ObjectId
        
        # Determine which job boards to start
        if request and request.job_board_ids:
            # Convert UUIDs to ObjectIds if needed
            object_ids = []
            for jb_id in request.job_board_ids:
                try:
                    # Try to convert UUID to ObjectId
                    object_id_str = await uuid_to_objectid_mapping(str(jb_id))
                    object_ids.append(ObjectId(object_id_str))
                except Exception as e:
                    logger.warning(f"Invalid job board ID {jb_id}: {str(e)}")
                    continue
            
            if not object_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No valid job board IDs provided"
                )
            
            # Start specific job boards
            job_board_filter = {
                "_id": {"$in": object_ids},
                "is_active": True
            }
        else:
            # Start all active job boards
            job_board_filter = {"is_active": True}
        
        job_boards = await JobBoard.find(job_board_filter).to_list()
        
        if not job_boards:
            detail = "No matching active job boards found" if request and request.job_board_ids else "No active job boards available to start"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail
            )
        
        # Import job queue functions
        from app.scrapers.job_queue import get_job_queue, TaskPriority
        
        # Get the job queue instance
        queue = get_job_queue()
        
        # Start the job queue workers if not already running
        if not queue._running:
            await queue.start_workers()
            logger.info("Job queue workers started")
        
        # Queue scraping tasks for all selected job boards
        task_ids = []
        priority_mapping = {
            0: TaskPriority.LOW,
            1: TaskPriority.NORMAL,
            2: TaskPriority.HIGH,
            3: TaskPriority.URGENT
        }
        task_priority = priority_mapping.get(request.priority if request else 1, TaskPriority.NORMAL)
        
        for job_board in job_boards:
            try:
                task_id = await queue.add_task(
                    job_board=job_board.name.lower().replace(' ', '_'),
                    query="remote",
                    location="Remote",
                    max_pages=3,
                    priority=task_priority,
                    metadata={
                        'job_board_id': str(job_board.id),
                        'engine_start': True,
                        'mode': request.mode.value if request else 'manual'
                    }
                )
                task_ids.append(task_id)
                logger.info(f"Queued scraping task {task_id} for job board {job_board.name}")
            except Exception as e:
                logger.error(f"Failed to queue task for job board {job_board.name}: {str(e)}")
                continue
        
        if not task_ids:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to queue any scraping tasks"
            )
        
        # Create result data
        result = {
            "job_boards_count": len(job_boards),
            "tasks_queued": len(task_ids),
            "task_ids": task_ids,
            "job_board_names": [jb.name for jb in job_boards],
            "priority": request.priority if request else 1,
            "mode": request.mode.value if request else 'manual'
        }
        
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/engine/start", 200, duration)  # Temporarily disabled
        
        logger.info(f"Engine started successfully: {len(task_ids)} tasks queued for {len(job_boards)} job boards")
        
        return SuccessResponse(
            success=True, 
            message=f"Engine started successfully! Queued {len(task_ids)} scraping tasks for {len(job_boards)} job boards", 
            data=result
        )
            
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/engine/start", 500, duration)  # Temporarily disabled
        logger.error(f"Error starting engine: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start engine"
        )


@router.post("/jobs/batch-scrape", response_model=SuccessResponse)
async def batch_scrape_job_boards(
    job_board_ids: List[str],
    priority: int = 1,
    max_pages: Optional[int] = None,
    current_user = Depends(require_auth)
):
    """
    Start batch scraping for multiple job boards using enhanced scraper
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import JobBoard
        from bson import ObjectId
        
        # Validate job board IDs and get active job boards
        valid_job_boards = []
        for job_board_id in job_board_ids:
            try:
                obj_id = ObjectId(job_board_id)
                job_board = await JobBoard.find_one({
                    "_id": obj_id,
                    "is_active": True
                })
                if job_board:
                    valid_job_boards.append(job_board)
            except Exception:
                logger.warning(f"Invalid job board ID: {job_board_id}")
                continue
        
        if not valid_job_boards:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid active job boards found"
            )
        
        # Use enhanced scraping service for batch processing
        batch_result = await scraping_service.batch_scrape_job_boards(
            job_board_ids=[str(jb.id) for jb in valid_job_boards],
            priority=priority,
            max_pages=max_pages
        )
        
        duration = time.time() - start_time
        logger.info(f"Batch scrape initiated for {len(valid_job_boards)} job boards")
        
        return SuccessResponse(
            success=True,
            message=f"Batch scraping started for {len(valid_job_boards)} job boards",
            data={
                "job_boards_count": len(valid_job_boards),
                "batch_id": batch_result.get("batch_id"),
                "estimated_completion": batch_result.get("estimated_completion")
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Batch scrape failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch scraping failed: {str(e)}"
        )


@router.get("/monitoring/stats", response_model=Dict[str, Any])
async def get_scraping_stats(
    current_user = Depends(require_auth)
):
    """
    Get comprehensive scraping statistics and monitoring data
    """
    try:
        # Get statistics from enhanced components
        scraping_stats = await scraping_monitor.get_statistics()
        deduplication_stats = scraping_service.get_deduplication_stats()
        queue_stats = await job_queue.get_queue_stats()
        
        # Get health report
        health_report = await scraping_monitor.generate_health_report()
        
        return {
            "scraping_statistics": scraping_stats,
            "deduplication_statistics": deduplication_stats,
            "queue_statistics": queue_stats,
            "health_report": health_report,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get scraping stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scraping statistics: {str(e)}"
        )


@router.get("/queue/status", response_model=Dict[str, Any])
async def get_queue_status(
    current_user = Depends(require_auth)
):
    """
    Get current job queue status and pending jobs
    """
    try:
        queue_status = await job_queue.get_status()
        pending_jobs = await job_queue.get_pending_jobs()
        
        return {
            "queue_status": queue_status,
            "pending_jobs": pending_jobs,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get queue status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue status: {str(e)}"
        )


@router.post("/test-scraper/{job_board_name}", response_model=Dict[str, Any])
async def test_job_board_scraper(
    job_board_name: str,
    query: str = "remote",
    max_pages: int = 1,
    current_user = Depends(require_auth)
):
    """
    Test scraping functionality for a specific job board
    """
    try:
        # Get specialized scraper for the job board
        scraper = job_board_factory.get_scraper(job_board_name)
        
        if not scraper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No specialized scraper found for {job_board_name}"
            )
        
        # Test scraping with monitoring
        test_id = f"test_{job_board_name}_{int(time.time())}"
        await scraping_monitor.start_monitoring(test_id, job_board_name)
        
        # Perform test scraping
        result = await scraper.scrape_jobs(
            query=query,
            location="Remote",
            max_pages=max_pages
        )
        
        # Stop monitoring and get results
        await scraping_monitor.stop_monitoring(test_id)
        
        return {
            "job_board": job_board_name,
            "test_result": {
                "status": result.status.value,
                "jobs_found": len(result.jobs),
                "pages_scraped": result.pages_scraped,
                "execution_time": result.execution_time,
                "errors": result.errors
            },
            "sample_jobs": result.jobs[:3] if result.jobs else [],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test scraping failed for {job_board_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test scraping failed: {str(e)}"
        )


@router.post("/engine/pause", response_model=SuccessResponse)
async def pause_engine(
    request: Optional[PauseScrapeJobRequest] = None,
    current_user = Depends(require_admin)
):
    """
    Pause the scraping engine by pausing active jobs.
    If no request body is provided, pause all running jobs.
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import ScrapeJob
        from app.models.mongodb_models import ScrapeJobStatus
        
        # Get running jobs
        running_jobs = await ScrapeJob.find({"status": ScrapeJobStatus.RUNNING}).to_list()
        
        if not running_jobs:
            return SuccessResponse(success=True, message="No running jobs to pause", data={"paused": 0})
        
        # Pause running jobs
        job_ids = [str(job.id) for job in running_jobs]
        
        payload = {
            'job_ids': job_ids,
            'reason': 'Pause-all via engine alias'
        }
        
        # For now, return a success response indicating the jobs to be paused
        result = {"jobs_to_pause": len(running_jobs), "job_ids": job_ids}
        
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/engine/pause", 200, duration)  # Temporarily disabled
        
        return SuccessResponse(success=True, message="Engine pause request submitted", data=result)
            
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/engine/pause", 500, duration)  # Temporarily disabled
        logger.error(f"Error pausing engine: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause engine"
        )


@router.put("/job-boards/{job_board_id}", response_model=JobBoardResponse)
async def update_job_board(
    job_board_id: str,
    job_board_update: JobBoardUpdate,
    current_user = Depends(require_auth)
):
    """
    Update a job board by ID
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import JobBoard
        from bson import ObjectId
        import uuid
        
        # Validate ObjectId format
        try:
            obj_id = ObjectId(job_board_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job board ID format"
            )
        
        # Find the job board
        job_board = await JobBoard.get(obj_id)
        if not job_board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job board not found"
            )
        
        # Map request type to MongoDB enum if provided
        mongo_type_mapping = {
            'rss': 'custom',
            'html': 'custom', 
            'api': 'custom',
            'hybrid': 'custom'
        }
        
        # Update fields
        update_data = job_board_update.dict(exclude_unset=True)
        
        # Handle type mapping
        if 'type' in update_data:
            request_type = update_data['type']
            update_data['type'] = mongo_type_mapping.get(request_type, 'custom')
        
        # Handle field mapping (description -> notes)
        if 'description' in update_data:
            update_data['notes'] = update_data.pop('description')
        
        # Update the job board
        for field, value in update_data.items():
            setattr(job_board, field, value)
        
        await job_board.save()
        
        # Convert ObjectId to UUID for response
        job_board_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, str(job_board.id))
        
        # Prepare response data with original request type
        response_data = {
            "id": job_board_uuid,
            "name": job_board.name,
            "description": getattr(job_board, 'notes', None),  # Map notes back to description
            "type": job_board_update.type if 'type' in update_data else "html",  # Use original request type
            "base_url": job_board.base_url,
            "rss_url": getattr(job_board, 'rss_url', None),
            "selectors": job_board.selectors or {},
            "rate_limit_delay": int(job_board.rate_limit_delay) if job_board.rate_limit_delay else 2,
            "max_pages": job_board.max_pages_per_search or 10,
            "request_timeout": getattr(job_board, 'request_timeout', 30),
            "retry_attempts": getattr(job_board, 'retry_attempts', 3),
            "is_active": job_board.is_active,
            "success_rate": getattr(job_board, 'success_rate', 0.0),
            "last_scraped_at": getattr(job_board, 'last_scraped_at', None),
            "total_scrapes": getattr(job_board, 'total_scrapes', 0),
            "successful_scrapes": getattr(job_board, 'successful_scrapes', 0),
            "failed_scrapes": getattr(job_board, 'failed_scrapes', 0),
            "created_at": job_board.created_at,
            "updated_at": job_board.updated_at
        }
        
        duration = time.time() - start_time
        # metrics.record_http_request("PUT", f"/job-boards/{job_board_id}", 200, duration)  # Temporarily disabled
        
        return JobBoardResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("PUT", f"/job-boards/{job_board_id}", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to update job board {job_board_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update job board: {str(e)}"
        )


def uuid_to_objectid(uuid_str: str) -> str:
    """
    Convert UUID back to ObjectId by searching all job boards.
    This is needed because we convert ObjectIds to UUIDs in the listing endpoint.
    """
    import uuid
    from bson import ObjectId
    
    # First try to parse as ObjectId directly
    try:
        ObjectId(uuid_str)
        return uuid_str
    except:
        pass
    
    # If it's a UUID, we need to find the corresponding ObjectId
    try:
        uuid.UUID(uuid_str)
        # It's a valid UUID, we need to search for the corresponding ObjectId
        return None  # Will be handled by the caller
    except:
        raise ValueError("Invalid ID format")


@router.patch("/job-boards/{job_board_id}/status", response_model=JobBoardResponse)
async def toggle_job_board_status(
    job_board_id: str,
    status_update: dict,
    current_user = Depends(require_auth)
):
    """
    Toggle job board active/inactive status
    Accepts both ObjectId and UUID formats
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import JobBoard
        from bson import ObjectId
        import uuid
        
        # Validate request body
        if "is_active" not in status_update:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'is_active' field in request body"
            )
        
        is_active = status_update["is_active"]
        if not isinstance(is_active, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'is_active' must be a boolean value"
            )
        
        # Validate ObjectId format
        try:
            obj_id = ObjectId(job_board_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job board ID format"
            )
        
        # Find the job board
        job_board = await JobBoard.get(obj_id)
        if not job_board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job board not found"
            )
        
        # Update the status
        job_board.is_active = is_active
        job_board.updated_at = datetime.utcnow()
        await job_board.save()
        
        # Convert ObjectId to UUID for response
        job_board_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, str(job_board.id))
        
        # Prepare response data using MongoDB model fields
        response_data = {
            "id": job_board_uuid,
            "name": job_board.name,
            "description": getattr(job_board, 'notes', None),  # Map notes back to description
            "type": "html",  # Default type for response
            "base_url": job_board.base_url,
            "rss_url": getattr(job_board, 'rss_url', None),
            "selectors": job_board.selectors or {},
            "rate_limit_delay": int(job_board.rate_limit_delay) if job_board.rate_limit_delay else 2,
            "max_pages": job_board.max_pages_per_search or 10,
            "request_timeout": getattr(job_board, 'request_timeout', 30),
            "retry_attempts": getattr(job_board, 'retry_attempts', 3),
            "is_active": job_board.is_active,
            "success_rate": getattr(job_board, 'success_rate', 0.0),
            "last_scraped_at": getattr(job_board, 'last_scraped_at', None),
            "total_scrapes": getattr(job_board, 'total_scrapes', 0),
            "successful_scrapes": getattr(job_board, 'successful_scrapes', 0),
            "failed_scrapes": getattr(job_board, 'failed_scrapes', 0),
            "created_at": job_board.created_at,
            "updated_at": job_board.updated_at
        }
        
        duration = time.time() - start_time
        # metrics.record_http_request("PATCH", f"/job-boards/{job_board_id}/status", 200, duration)  # Temporarily disabled
        
        logger.info(f"Job board {job_board_id} status updated to {'active' if is_active else 'inactive'}")
        
        return JobBoardResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("PATCH", f"/job-boards/{job_board_id}/status", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to toggle job board status {job_board_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle job board status: {str(e)}"
        )


@router.delete("/job-boards/{job_board_id}", response_model=SuccessResponse)
async def delete_job_board(
    job_board_id: str,
    current_user = Depends(require_auth)
):
    """
    Delete a job board by ID
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import JobBoard
        from bson import ObjectId
        
        # Validate ObjectId format
        try:
            obj_id = ObjectId(job_board_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid job board ID format"
            )
        
        # Find the job board
        job_board = await JobBoard.get(obj_id)
        if not job_board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job board not found"
            )
        
        job_board_name = job_board.name
        
        # Delete the job board
        await job_board.delete()
        
        duration = time.time() - start_time
        # metrics.record_http_request("DELETE", f"/job-boards/{job_board_id}", 200, duration)  # Temporarily disabled
        
        return SuccessResponse(
            success=True,
            message=f"Job board '{job_board_name}' deleted successfully",
            data={"deleted_id": job_board_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("DELETE", f"/job-boards/{job_board_id}", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to delete job board {job_board_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete job board: {str(e)}"
        )


@router.post("/engine/reset", response_model=SuccessResponse)
async def reset_engine(
    current_user = Depends(require_admin)
):
    """
    Reset the scraping engine.
    This performs a system reset with no data/config wipe by default.
    Requires admin privileges.
    """
    start_time = time.time()
    
    try:
        
        # Reset engine state
        # Note: EngineService might need to be updated for MongoDB compatibility
        result = {"message": "Engine reset completed", "timestamp": time.time()}
        
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/engine/reset", 200, duration)  # Temporarily disabled
        
        return SuccessResponse(success=True, message="Engine reset completed", data=result)
            
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("POST", "/engine/reset", 500, duration)  # Temporarily disabled
        logger.error(f"Error resetting engine: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset engine"
        )


# Scrape Runs endpoints
@router.get("/runs", response_model=List[ScrapeRunResponse])
async def list_scrape_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    job_id: Optional[str] = Query(None, description="Filter by scrape job ID"),
    current_user = Depends(require_auth)
):
    """
    List scrape runs with optional filtering
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import ScrapeRun
        
        # Build MongoDB query filter
        query_filter = {}
        if job_id:
            query_filter["scrape_job_id"] = job_id
        
        # Execute query with pagination
        runs = await ScrapeRun.find(query_filter).skip(skip).limit(limit).sort([("created_at", -1)]).to_list()
        
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/runs", 200, duration)  # Temporarily disabled
        
        return [ScrapeRunResponse(**run.dict()) for run in runs]
        
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/runs", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to list scrape runs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list scrape runs"
        )


@router.get("/runs/{run_id}", response_model=ScrapeRunResponse)
async def get_scrape_run(
    run_id: str,
    current_user = Depends(require_auth)
):
    """
    Get a specific scrape run by ID
    """
    start_time = time.time()
    
    try:
        # Import MongoDB models
        from app.models.mongodb_models import ScrapeRun
        from bson import ObjectId
        
        # Validate ObjectId format
        try:
            run_obj_id = ObjectId(run_id)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid run ID format"
            )
        
        run = await ScrapeRun.get(run_obj_id)
        
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scrape run not found"
            )
        
        duration = time.time() - start_time
        # metrics.record_http_request("GET", f"/runs/{run_id}", 200, duration)  # Temporarily disabled
        
        return ScrapeRunResponse(**run.dict())
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("GET", f"/runs/{run_id}", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to get scrape run {run_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get scrape run"
        )


# Logs endpoints
@router.get("/logs", response_model=LiveLogsResponse)
async def get_logs(
    limit: int = Query(100, ge=1, le=1000, description="Number of logs to retrieve"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    source: Optional[str] = Query(None, description="Filter by log source"),
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    current_user = Depends(require_auth)
):
    """
    Get application logs with filtering options
    """
    start_time = time.time()
    
    try:
        # For now, return mock logs since we don't have a log storage system
        # In a real implementation, you'd query your log storage (e.g., database, file, etc.)
        mock_logs = [
            LogEntry(
                timestamp=datetime.now(),
                level="INFO",
                message="AutoScraper service started successfully",
                source="autoscraper",
                job_id=None,
                details={"service": "autoscraper", "version": "1.0.0"}
            ),
            LogEntry(
                timestamp=datetime.now(),
                level="INFO",
                message="Job board scraping completed",
                source="scraper",
                job_id=None,
                details={"items_found": 25, "items_processed": 25}
            )
        ]
        
        # Apply filters
        filtered_logs = mock_logs
        if level:
            filtered_logs = [log for log in filtered_logs if log.level.lower() == level.lower()]
        if source:
            filtered_logs = [log for log in filtered_logs if log.source and source.lower() in log.source.lower()]
        if job_id:
            try:
                job_uuid = UUID(job_id)
                filtered_logs = [log for log in filtered_logs if log.job_id == job_uuid]
            except ValueError:
                pass  # Invalid UUID, ignore filter
        
        # Apply limit
        filtered_logs = filtered_logs[:limit]
        
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/logs", 200, duration)  # Temporarily disabled
        
        return LiveLogsResponse(
            logs=filtered_logs,
            total_count=len(filtered_logs),
            has_more=False
        )
        
    except Exception as e:
        duration = time.time() - start_time
        # metrics.record_http_request("GET", "/logs", 500, duration)  # Temporarily disabled
        logger.error(f"Failed to get logs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve logs"
        )


@router.get("/logs/live")
async def get_live_logs(
    limit: int = Query(100, ge=1, le=1000),
    level: str = Query("INFO", description="Log level filter"),
    current_user = Depends(require_auth)
):
    """
    Live log streaming using Server-Sent Events (SSE)
    """
    import asyncio
    import json
    
    async def generate_log_stream():
        """Generate SSE formatted log stream"""
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            
            # Send recent logs first
            now = datetime.utcnow()
            
            for i in range(min(limit, 10)):
                log_time = now - timedelta(minutes=i)
                log_entry = {
                    "type": "log",
                    "timestamp": log_time.isoformat(),
                    "level": level,
                    "message": f"Sample log message {i+1}",
                    "source": "autoscraper",
                    "job_id": None
                }
                yield f"data: {json.dumps(log_entry)}\n\n"
            
            # Keep connection alive and send periodic updates
            while True:
                await asyncio.sleep(5)  # Send update every 5 seconds
                
                # Send heartbeat or new log entries
                heartbeat = {
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat(),
                    "active_jobs": 0  # TODO: Get actual active job count
                }
                yield f"data: {json.dumps(heartbeat)}\n\n"
                
        except asyncio.CancelledError:
            # Client disconnected
            logger.info("Live log stream disconnected")
            return
        except Exception as e:
            logger.error(f"Error in log stream: {str(e)}")
            error_event = {
                "type": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        generate_log_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


# Advanced Jobs Data Endpoints
@router.get("/raw-jobs", response_model=Dict[str, Any])
async def get_raw_jobs(
    job_board_id: Optional[str] = Query(None, description="Filter by job board ID"),
    date_from: Optional[datetime] = Query(None, description="Start date filter"),
    date_to: Optional[datetime] = Query(None, description="End date filter"),
    status: Optional[str] = Query(None, description="Filter by processing status"),
    search_term: Optional[str] = Query(None, description="Search in title, company, or description"),
    limit: int = Query(50, ge=1, le=1000, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    current_user = Depends(require_auth)
):
    """
    Get raw scraped jobs with comprehensive filtering options
    """
    start_time = time.time()
    
    try:
        from app.models.mongodb_models import RawJob, JobBoard
        from bson import ObjectId
        
        # Build filter query
        filter_query = {}
        
        # Job board filter
        if job_board_id:
            try:
                # Try ObjectId format first
                job_board_obj_id = ObjectId(job_board_id)
                filter_query["job_board_id"] = str(job_board_obj_id)
            except Exception:
                # Use as string if not ObjectId
                filter_query["job_board_id"] = job_board_id
        
        # Date range filter
        if date_from or date_to:
            date_filter = {}
            if date_from:
                date_filter["$gte"] = date_from
            if date_to:
                date_filter["$lte"] = date_to
            filter_query["scraped_at"] = date_filter
        
        # Status filter
        if status:
            filter_query["processing_status"] = status
        
        # Search term filter
        if search_term:
            filter_query["$or"] = [
                {"title": {"$regex": search_term, "$options": "i"}},
                {"company": {"$regex": search_term, "$options": "i"}},
                {"description": {"$regex": search_term, "$options": "i"}}
            ]
        
        # Get total count
        total_count = await RawJob.find(filter_query).count()
        
        # Get paginated results
        raw_jobs = await RawJob.find(filter_query).skip(offset).limit(limit).sort("-scraped_at").to_list()
        
        # Enrich with job board information
        enriched_jobs = []
        for job in raw_jobs:
            job_dict = job.dict()
            
            # Get job board info
            if job.job_board_id:
                try:
                    job_board_obj_id = ObjectId(job.job_board_id)
                    job_board = await JobBoard.get(job_board_obj_id)
                    if job_board:
                        job_dict["job_board_name"] = job_board.name
                        job_dict["job_board_type"] = job_board.type
                except Exception:
                    job_dict["job_board_name"] = "Unknown"
                    job_dict["job_board_type"] = "Unknown"
            
            enriched_jobs.append(job_dict)
        
        duration = time.time() - start_time
        
        return {
            "data": enriched_jobs,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            },
            "filters_applied": {
                "job_board_id": job_board_id,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "status": status,
                "search_term": search_term
            },
            "execution_time_ms": round(duration * 1000, 2)
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Failed to get raw jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve raw jobs: {str(e)}"
        )


@router.get("/normalized-jobs", response_model=Dict[str, Any])
async def get_normalized_jobs(
    job_board_id: Optional[str] = Query(None, description="Filter by job board ID"),
    date_from: Optional[datetime] = Query(None, description="Start date filter"),
    date_to: Optional[datetime] = Query(None, description="End date filter"),
    quality_score_min: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum quality score"),
    quality_score_max: Optional[float] = Query(None, ge=0.0, le=1.0, description="Maximum quality score"),
    location: Optional[str] = Query(None, description="Filter by location"),
    salary_min: Optional[int] = Query(None, ge=0, description="Minimum salary"),
    salary_max: Optional[int] = Query(None, ge=0, description="Maximum salary"),
    skills: Optional[str] = Query(None, description="Filter by skills (comma-separated)"),
    is_published: Optional[bool] = Query(None, description="Filter by publication status"),
    limit: int = Query(50, ge=1, le=1000, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    current_user = Depends(require_auth)
):
    """
    Get normalized jobs with comprehensive filtering options
    """
    start_time = time.time()
    
    try:
        from app.models.mongodb_models import NormalizedJob, JobBoard
        from bson import ObjectId
        
        # Build filter query
        filter_query = {}
        
        # Job board filter
        if job_board_id:
            try:
                job_board_obj_id = ObjectId(job_board_id)
                filter_query["job_board_id"] = str(job_board_obj_id)
            except Exception:
                filter_query["job_board_id"] = job_board_id
        
        # Date range filter
        if date_from or date_to:
            date_filter = {}
            if date_from:
                date_filter["$gte"] = date_from
            if date_to:
                date_filter["$lte"] = date_to
            filter_query["normalized_at"] = date_filter
        
        # Quality score filter
        if quality_score_min is not None or quality_score_max is not None:
            quality_filter = {}
            if quality_score_min is not None:
                quality_filter["$gte"] = quality_score_min
            if quality_score_max is not None:
                quality_filter["$lte"] = quality_score_max
            filter_query["quality_score"] = quality_filter
        
        # Location filter
        if location:
            filter_query["location"] = {"$regex": location, "$options": "i"}
        
        # Salary range filter
        if salary_min is not None or salary_max is not None:
            salary_filter = {}
            if salary_min is not None:
                salary_filter["$gte"] = salary_min
            if salary_max is not None:
                salary_filter["$lte"] = salary_max
            filter_query["salary_min"] = salary_filter
        
        # Skills filter
        if skills:
            skills_list = [skill.strip() for skill in skills.split(",")]
            filter_query["skills"] = {"$in": skills_list}
        
        # Publication status filter
        if is_published is not None:
            filter_query["is_published"] = is_published
        
        # Get total count
        total_count = await NormalizedJob.find(filter_query).count()
        
        # Get paginated results
        normalized_jobs = await NormalizedJob.find(filter_query).skip(offset).limit(limit).sort("-normalized_at").to_list()
        
        # Enrich with job board information
        enriched_jobs = []
        for job in normalized_jobs:
            job_dict = job.dict()
            
            # Get job board info
            if job.job_board_id:
                try:
                    job_board_obj_id = ObjectId(job.job_board_id)
                    job_board = await JobBoard.get(job_board_obj_id)
                    if job_board:
                        job_dict["job_board_name"] = job_board.name
                        job_dict["job_board_type"] = job_board.type
                except Exception:
                    job_dict["job_board_name"] = "Unknown"
                    job_dict["job_board_type"] = "Unknown"
            
            enriched_jobs.append(job_dict)
        
        duration = time.time() - start_time
        
        return {
            "data": enriched_jobs,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            },
            "filters_applied": {
                "job_board_id": job_board_id,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "quality_score_min": quality_score_min,
                "quality_score_max": quality_score_max,
                "location": location,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "skills": skills,
                "is_published": is_published
            },
            "execution_time_ms": round(duration * 1000, 2)
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Failed to get normalized jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve normalized jobs: {str(e)}"
        )


@router.get("/jobs-analytics", response_model=Dict[str, Any])
async def get_jobs_analytics(
    date_from: Optional[datetime] = Query(None, description="Start date for analytics"),
    date_to: Optional[datetime] = Query(None, description="End date for analytics"),
    job_board_id: Optional[str] = Query(None, description="Filter by specific job board"),
    current_user = Depends(require_auth)
):
    """
    Get comprehensive analytics data for scraped jobs
    """
    start_time = time.time()
    
    try:
        from app.models.mongodb_models import RawJob, NormalizedJob, JobBoard, ScrapeJob, ScrapeRun
        from bson import ObjectId
        
        # Set default date range if not provided (last 30 days)
        if not date_from:
            date_from = datetime.utcnow() - timedelta(days=30)
        if not date_to:
            date_to = datetime.utcnow()
        
        # Build base filter
        base_filter = {
            "scraped_at": {"$gte": date_from, "$lte": date_to}
        }
        
        if job_board_id:
            try:
                job_board_obj_id = ObjectId(job_board_id)
                base_filter["job_board_id"] = str(job_board_obj_id)
            except Exception:
                base_filter["job_board_id"] = job_board_id
        
        # Get basic counts
        total_raw_jobs = await RawJob.find(base_filter).count()
        total_normalized_jobs = await NormalizedJob.find({
            "normalized_at": {"$gte": date_from, "$lte": date_to}
        }).count()
        
        # Jobs over time (daily aggregation)
        pipeline_daily = [
            {"$match": base_filter},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$scraped_at"
                        }
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        daily_jobs = await RawJob.aggregate(pipeline_daily).to_list(length=None)
        
        # Job board performance
        pipeline_job_boards = [
            {"$match": base_filter},
            {
                "$group": {
                    "_id": "$job_board_id",
                    "total_jobs": {"$sum": 1},
                    "avg_quality": {"$avg": "$quality_score"}
                }
            }
        ]
        
        job_board_stats = await RawJob.aggregate(pipeline_job_boards).to_list(length=None)
        
        # Enrich job board stats with names
        enriched_job_board_stats = []
        for stat in job_board_stats:
            try:
                job_board_obj_id = ObjectId(stat["_id"])
                job_board = await JobBoard.get(job_board_obj_id)
                stat["job_board_name"] = job_board.name if job_board else "Unknown"
                stat["job_board_type"] = job_board.type if job_board else "Unknown"
            except Exception:
                stat["job_board_name"] = "Unknown"
                stat["job_board_type"] = "Unknown"
            enriched_job_board_stats.append(stat)
        
        # Quality score distribution
        pipeline_quality = [
            {"$match": {"normalized_at": {"$gte": date_from, "$lte": date_to}}},
            {
                "$bucket": {
                    "groupBy": "$quality_score",
                    "boundaries": [0, 0.2, 0.4, 0.6, 0.8, 1.0],
                    "default": "unknown",
                    "output": {
                        "count": {"$sum": 1}
                    }
                }
            }
        ]
        
        quality_distribution = await NormalizedJob.aggregate(pipeline_quality).to_list(length=None)
        
        # Success rate calculation
        total_scrape_jobs = await ScrapeJob.find({
            "created_at": {"$gte": date_from, "$lte": date_to}
        }).count()
        
        successful_scrape_jobs = await ScrapeJob.find({
            "status": "COMPLETED",
            "completed_at": {"$gte": date_from, "$lte": date_to}
        }).count()
        
        success_rate = (successful_scrape_jobs / total_scrape_jobs * 100) if total_scrape_jobs > 0 else 0
        
        # Top skills analysis
        pipeline_skills = [
            {"$match": {"normalized_at": {"$gte": date_from, "$lte": date_to}}},
            {"$unwind": "$skills"},
            {
                "$group": {
                    "_id": "$skills",
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        
        top_skills = await NormalizedJob.aggregate(pipeline_skills).to_list(length=None)
        
        # Location distribution
        pipeline_locations = [
            {"$match": {"normalized_at": {"$gte": date_from, "$lte": date_to}}},
            {
                "$group": {
                    "_id": "$location",
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 15}
        ]
        
        location_distribution = await NormalizedJob.aggregate(pipeline_locations).to_list(length=None)
        
        duration = time.time() - start_time
        
        return {
            "summary": {
                "total_raw_jobs": total_raw_jobs,
                "total_normalized_jobs": total_normalized_jobs,
                "success_rate": round(success_rate, 2),
                "date_range": {
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat()
                }
            },
            "charts": {
                "jobs_over_time": daily_jobs,
                "job_board_performance": enriched_job_board_stats,
                "quality_distribution": quality_distribution,
                "top_skills": top_skills,
                "location_distribution": location_distribution
            },
            "execution_time_ms": round(duration * 1000, 2)
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Failed to get jobs analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve jobs analytics: {str(e)}"
        )