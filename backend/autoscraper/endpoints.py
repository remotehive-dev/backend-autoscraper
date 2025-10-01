from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from typing import List, Optional
from loguru import logger
import json

from backend.core.deps import get_current_user
from backend.models.mongodb_models import User
from backend.autoscraper.schemas import (
    JobBoardCreate, JobBoardUpdate, JobBoardResponse,
    ScrapeJobResponse, ScrapeRunResponse, EngineStateResponse,
    StartScrapeJobRequest, PauseScrapeJobRequest, HardResetRequest,
    DashboardResponse, HealthCheckResponse, LiveLogsResponse,
    SuccessResponse, SystemSettings, SystemSettingsUpdate, 
    SettingsTestRequest, SettingsTestResponse,
    SystemHealthResponse, PerformanceMetrics, ErrorResponse
)
from backend.autoscraper.service_adapter import get_autoscraper_adapter

router = APIRouter()

# Dashboard endpoint
@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get autoscraper dashboard with stats and recent activities
    """
    try:
        # Extract authorization header to forward to autoscraper service
        auth_header = request.headers.get("authorization")
        headers = {"Authorization": auth_header} if auth_header else {}
        
        adapter = get_autoscraper_adapter()
        async with adapter:
            dashboard_data = await adapter.get_dashboard(headers=headers)
            return DashboardResponse(**dashboard_data)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard data"
        )

# Start scrape job endpoint
@router.post("/jobs/start", response_model=ScrapeJobResponse)
async def start_scrape_job(
    request: StartScrapeJobRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Start a new scrape job for a specific job board
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            job_data = request.dict()
            job_data['requested_by_id'] = current_user.id
            result = await adapter.start_scrape_job(job_data)
            return ScrapeJobResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Error starting scrape job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start scrape job"
        )

# Pause scrape job endpoint (can handle multiple job IDs)
@router.post("/jobs/pause", response_model=SuccessResponse)
async def pause_scrape_job(
    request: PauseScrapeJobRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Pause one or more running scrape jobs
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            payload = request.dict()
            payload['requested_by_id'] = getattr(current_user, 'id', None)
            result = await adapter.pause_scrape_job(payload)
            return SuccessResponse(success=True, message="Pause request submitted", data=result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Error pausing scrape job(s): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause scrape job(s)"
        )

# Engine control alias endpoints
@router.post("/engine/start", response_model=SuccessResponse)
async def start_engine(
    request: Optional[StartScrapeJobRequest] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Alias for starting the scraping engine by dispatching scrape jobs.
    If no request body is provided, it will start all active job boards.
    This exists for UI compatibility (/engine/start) where the frontend sends an empty POST.
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            # Determine job_board_ids
            job_board_ids: List[str] = []
            priority = 0
            mode = "manual"

            if request and getattr(request, 'job_board_ids', None):
                job_board_ids = [str(jb_id) for jb_id in request.job_board_ids]
                priority = getattr(request, 'priority', 0)
                # request.mode may be Enum; convert to string
                mode = getattr(request.mode, 'value', str(request.mode)) if getattr(request, 'mode', None) else "manual"
            else:
                # No explicit job boards provided; start all active job boards
                job_boards = await adapter.list_job_boards(active_only=True)
                job_board_ids = [str(jb.get('id')) for jb in job_boards if jb.get('is_active')]
                if not job_board_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No active job boards available to start"
                    )

            job_data = {
                'job_board_ids': job_board_ids,
                'priority': priority,
                'mode': mode,
                'requested_by_id': current_user.id
            }
            result = await adapter.start_scrape_job(job_data)
            return SuccessResponse(success=True, message="Engine start request submitted", data=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting engine: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start engine"
        )

@router.post("/engine/pause", response_model=SuccessResponse)
async def pause_engine(
    request: Optional[PauseScrapeJobRequest] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Alias for pausing the scraping engine by pausing active jobs.
    If no request body is provided, pause all running jobs.
    This exists for UI compatibility (/engine/pause).
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            if request and getattr(request, 'job_ids', None):
                payload = request.dict()
                payload['requested_by_id'] = getattr(current_user, 'id', None)
            else:
                # No explicit job IDs provided; pause all running jobs
                running_jobs = await adapter.list_scrape_jobs(status="running")
                job_ids: List[str] = [str(job.get('id')) for job in running_jobs if job.get('id')]
                if not job_ids:
                    return SuccessResponse(success=True, message="No running jobs to pause", data={"paused": 0})
                payload = {
                    'job_ids': job_ids,
                    'reason': 'Pause-all via engine alias',
                    'requested_by_id': getattr(current_user, 'id', None)
                }
            result = await adapter.pause_scrape_job(payload)
            return SuccessResponse(success=True, message="Engine pause request submitted", data=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing engine: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause engine"
        )

@router.post("/engine/reset", response_model=SuccessResponse)
async def reset_engine(
    current_user: User = Depends(get_current_user)
):
    """
    Alias for resetting the scraping engine.
    This maps to a system hard reset with no data/config wipe by default.
    Frontend sends an empty POST to /engine/reset.
    """
    try:
        # Require admin permission for engine reset
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required for engine reset"
            )
        adapter = get_autoscraper_adapter()
        async with adapter:
            reset_payload = {
                'confirm': True,
                'reset_data': False,
                'reset_configs': False
            }
            result = await adapter.hard_reset(reset_payload)
            return SuccessResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting engine: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset engine"
        )

# Hard reset endpoint
@router.post("/system/hard-reset", response_model=SuccessResponse)
async def hard_reset(
    request: HardResetRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Perform a hard reset of the autoscraper system
    """
    try:
        # Require admin permission for hard reset
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required for hard reset"
            )
        
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.hard_reset(request.dict())
            return SuccessResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Hard reset failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hard reset failed: {str(e)}"
        )

# Health check endpoint
@router.get("/health", response_model=HealthCheckResponse)
async def health_check(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Get autoscraper system health status
    """
    try:
        logger.info("Starting health check")
        adapter = get_autoscraper_adapter()
        logger.info(f"Got adapter: {type(adapter)}")
        
        # Extract authorization header
        auth_header = request.headers.get("authorization")
        headers = {"Authorization": auth_header} if auth_header else None
        
        async with adapter:
            logger.info("Entered async context manager")
            result = await adapter.health_check(headers=headers)
            logger.info(f"Health check result: {result}")
            return HealthCheckResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        logger.error("HTTPException in health check")
        raise
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )

# Regular logs endpoint for initial log fetching
@router.get("/logs", response_model=LiveLogsResponse)
async def get_logs(
    job_id: Optional[str] = Query(None, description="Filter logs by job ID"),
    level: Optional[str] = Query(None, description="Filter logs by level"),
    limit: int = Query(100, description="Maximum number of logs to return"),
    skip: int = Query(0, ge=0, description="Number of logs to skip"),
    current_user: User = Depends(get_current_user)
):
    """
    Get logs from the autoscraper system with pagination
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.get_logs(
                job_id=job_id,
                level=level,
                limit=limit,
                skip=skip
            )
            return LiveLogsResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to fetch logs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch logs: {str(e)}"
        )

# Live logs streaming endpoint
@router.get("/logs/live")
async def live_logs_stream(
    job_id: Optional[str] = Query(None, description="Filter logs by job ID"),
    level: Optional[str] = Query(None, description="Filter logs by level"),
    limit: int = Query(100, description="Maximum number of logs to return"),
    current_user: User = Depends(get_current_user)
):
    """
    Stream live logs from the autoscraper system
    """
    async def generate_logs():
        try:
            adapter = get_autoscraper_adapter()
            async with adapter:
                result = await adapter.get_live_logs(
                    job_id=job_id,
                    level=level,
                    limit=limit
                )
                yield f"data: {json.dumps(result)}\n\n"
            
        except Exception as e:
            error_response = ErrorResponse(
                error=f"Failed to stream logs: {str(e)}"
            )
            yield f"data: {error_response.json()}\n\n"
    
    return StreamingResponse(
        generate_logs(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

# Job Boards CRUD endpoints
@router.get("/job-boards", response_model=List[JobBoardResponse])
async def list_job_boards(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    current_user: User = Depends(get_current_user)
):
    """
    List all job boards with pagination
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.get_job_boards(
                skip=skip,
                limit=limit,
                active_only=active_only
            )
            return [JobBoardResponse(**jb) for jb in result]
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Error getting job boards: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job boards"
        )

@router.post("/job-boards", response_model=JobBoardResponse)
async def create_job_board(
    job_board: JobBoardCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new job board configuration
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            job_board_data = job_board.dict()
            result = await adapter.create_job_board(job_board_data)
            return JobBoardResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Error creating job board: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job board"
        )

@router.get("/job-boards/{job_board_id}", response_model=JobBoardResponse)
async def get_job_board(
    job_board_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific job board by ID
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.get_job_board(job_board_id)
            return JobBoardResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to get job board {job_board_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job board"
        )

@router.put("/job-boards/{job_board_id}", response_model=JobBoardResponse)
async def update_job_board(
    job_board_id: str,
    job_board_update: JobBoardUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a job board configuration
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            update_data = job_board_update.dict(exclude_unset=True)
            result = await adapter.update_job_board(job_board_id, update_data)
            return JobBoardResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Error updating job board: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update job board"
        )

@router.delete("/job-boards/{job_board_id}", response_model=SuccessResponse)
async def delete_job_board(
    job_board_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a job board configuration
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.delete_job_board(job_board_id)
            return SuccessResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to delete job board: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete job board"
        )

@router.patch("/job-boards/{job_board_id}/status", response_model=JobBoardResponse)
async def toggle_job_board_status(
    job_board_id: str,
    status_update: dict,
    current_user: User = Depends(get_current_user)
):
    """
    Toggle job board active status
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            # Extract is_active from the request body
            is_active = status_update.get('is_active', False)
            update_data = {'is_active': is_active}
            result = await adapter.update_job_board(job_board_id, update_data)
            return JobBoardResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to toggle job board status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle job board status"
        )

# Scrape Jobs endpoints
@router.get("/jobs", response_model=List[ScrapeJobResponse])
async def list_scrape_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    job_board_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user)
):
    """
    List scrape jobs with filtering and pagination
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.list_scrape_jobs(
                skip=skip,
                limit=limit,
                status=status,
                job_board_id=job_board_id
            )
            return [ScrapeJobResponse(**job) for job in result]
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to list scrape jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list scrape jobs"
        )

@router.get("/jobs/{job_id}", response_model=ScrapeJobResponse)
async def get_scrape_job(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific scrape job by ID
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.get_scrape_job(job_id)
            return ScrapeJobResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to get scrape job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get scrape job"
        )

# Engine state endpoint
@router.get("/engine/state", response_model=EngineStateResponse)
async def get_engine_state(
    current_user: User = Depends(get_current_user)
):
    """
    Get current engine state
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.get_engine_state()
            return EngineStateResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to get engine state: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get engine state"
        )

# Trigger heartbeat endpoint
@router.post("/engine/heartbeat", response_model=SuccessResponse)
async def trigger_heartbeat(
    current_user: User = Depends(get_current_user)
):
    """
    Manually trigger a system heartbeat
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.trigger_heartbeat()
            return SuccessResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to trigger heartbeat: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger heartbeat"
        )

# Settings endpoints
@router.get("/settings", response_model=SystemSettings)
async def get_settings(
    current_user: User = Depends(get_current_user)
):
    """
    Get current autoscraper system settings
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.get_settings()
            return SystemSettings(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to get settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get settings: {str(e)}"
        )

@router.put("/settings", response_model=SystemSettings)
async def update_settings(
    settings_update: SystemSettingsUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update autoscraper system settings
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            settings_data = settings_update.dict(exclude_unset=True)
            result = await adapter.update_system_settings(settings_data)
            logger.info(f"Settings updated by user {current_user.id}")
            return SystemSettings(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to update settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )

@router.post("/settings/reset", response_model=SystemSettings)
async def reset_settings(
    current_user: User = Depends(get_current_user)
):
    """
    Reset autoscraper system settings to defaults
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.reset_settings()
            logger.info(f"Settings reset to defaults by user {current_user.id}")
            return SystemSettings(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to reset settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset settings: {str(e)}"
        )

@router.post("/settings/test", response_model=SettingsTestResponse)
async def test_settings(
    test_request: SettingsTestRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Test specific settings configuration
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            payload = {
                "test_type": test_request.test_type,
                "settings": test_request.settings,
            }
            result = await adapter.test_settings(payload)
            return SettingsTestResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to test settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test settings: {str(e)}"
        )

# System health and metrics endpoints
@router.get("/system/health", response_model=SystemHealthResponse)
async def get_system_health(
    current_user: User = Depends(get_current_user)
):
    """
    Get current system health status
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.get_system_health()
            return SystemHealthResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to get system health: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system health: {str(e)}"
        )

@router.get("/system/metrics", response_model=PerformanceMetrics)
async def get_performance_metrics(
    current_user: User = Depends(get_current_user)
):
    """
    Get current performance metrics
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.get_performance_metrics()
            return PerformanceMetrics(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance metrics: {str(e)}"
        )

# Scrape Runs endpoints
@router.get("/runs", response_model=List[ScrapeRunResponse])
async def list_scrape_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    job_id: Optional[str] = Query(None, description="Filter by scrape job ID"),
    current_user: User = Depends(get_current_user)
):
    """
    List scrape runs with optional filtering
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.list_scrape_runs(skip=skip, limit=limit, job_id=job_id)
            return [ScrapeRunResponse(**run) for run in result]
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to list scrape runs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list scrape runs"
        )

@router.get("/runs/{run_id}", response_model=ScrapeRunResponse)
async def get_scrape_run(
    run_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific scrape run by ID
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            result = await adapter.get_scrape_run(run_id)
            return ScrapeRunResponse(**result)
        
    except HTTPException:
        # Re-raise HTTP exceptions from the adapter
        raise
    except Exception as e:
        logger.error(f"Failed to get scrape run {run_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get scrape run"
        )
@router.post("/jobs/{job_id}/start", response_model=SuccessResponse)
async def start_scrape_job_alias(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Alias to (re)start a specific scrape job by creating a new run for its job board.
    Maps to adapter.start_scrape_job with the job's job_board_id.
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            # Fetch the job to get its job_board_id
            job = await adapter.get_scrape_job(job_id)
            job_board_id = str(job.get('job_board_id')) if job else None
            if not job_board_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unable to determine job_board_id for the given job"
                )
            start_payload = {
                'job_board_ids': [job_board_id],
                'priority': 0,
                'mode': 'manual',
                'requested_by_id': getattr(current_user, 'id', None)
            }
            result = await adapter.start_scrape_job(start_payload)
            return SuccessResponse(success=True, message="Job start request submitted", data=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting job {job_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start job"
        )
@router.post("/jobs/{job_id}/pause", response_model=SuccessResponse)
async def pause_scrape_job_alias(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Alias to pause a specific scrape job by ID.
    Maps to adapter.pause_scrape_job with a single job_id.
    """
    try:
        adapter = get_autoscraper_adapter()
        async with adapter:
            payload = {
                'job_ids': [job_id],
                'reason': 'Paused via UI',
                'requested_by_id': getattr(current_user, 'id', None)
            }
            result = await adapter.pause_scrape_job(payload)
            return SuccessResponse(success=True, message="Job pause request submitted", data=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing job {job_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pause job"
        )