from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
# from sqlalchemy.orm import Session  # Using MongoDB instead
from typing import List, Dict, Any, Optional
import csv
import io
import uuid
from datetime import datetime
import pandas as pd
from pydantic import BaseModel, ValidationError

from backend.database.database import get_db_session as get_db
from backend.core.rbac import require_permission
from backend.services.csv_import_service import CSVImportService
from backend.services.job_board_config_service import JobBoardConfigService
from backend.database.services import ScraperConfigService
from backend.services.job_validation_service import JobDataValidator
from backend.schemas.job_post import JobPostCreate
# User model import removed - using dict for current_user

router = APIRouter()

class CSVUploadResponse(BaseModel):
    upload_id: str
    filename: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    status: str
    errors: List[Dict[str, Any]]
    created_at: datetime

class CSVImportStatus(BaseModel):
    upload_id: str
    status: str
    progress: float
    total_rows: int
    processed_rows: int
    successful_imports: int
    failed_imports: int
    errors: List[Dict[str, Any]]
    started_at: datetime
    completed_at: Optional[datetime]

class CSVFieldMapping(BaseModel):
    csv_field: str
    job_field: str
    required: bool = False
    transform: Optional[str] = None

class CSVImportConfig(BaseModel):
    field_mappings: List[CSVFieldMapping]
    skip_duplicates: bool = True
    validate_urls: bool = True
    auto_categorize: bool = False
    ml_parsing_enabled: bool = False

@router.post("/upload", response_model=CSVUploadResponse)
async def upload_csv_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    config: Optional[str] = None,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """
    Upload and validate a CSV file for job import.
    
    Args:
        file: CSV file containing job data
        config: Optional JSON string with import configuration
        db: Database session
        current_user: Authenticated admin user
    
    Returns:
        CSVUploadResponse with validation results and upload ID
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    if file.size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File size exceeds 10MB limit")
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Generate upload ID
        upload_id = str(uuid.uuid4())
        
        # Initialize CSV import service
        csv_service = CSVImportService(db)
        
        # Parse and validate CSV
        validation_result = await csv_service.validate_csv(
            csv_content=csv_content,
            filename=file.filename,
            upload_id=upload_id,
            user_id=current_user.get('id'),
            config=config
        )
        
        # Start background import process if validation passed
        if validation_result['valid_rows'] > 0:
            background_tasks.add_task(
                csv_service.process_csv_import,
                upload_id=upload_id,
                csv_content=csv_content,
                config=config
            )
        
        return CSVUploadResponse(
            upload_id=upload_id,
            filename=file.filename,
            total_rows=validation_result['total_rows'],
            valid_rows=validation_result['valid_rows'],
            invalid_rows=validation_result['invalid_rows'],
            status="processing" if validation_result['valid_rows'] > 0 else "validation_failed",
            errors=validation_result['errors'],
            created_at=datetime.utcnow()
        )
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing CSV file: {str(e)}")

@router.get("/status/{upload_id}", response_model=CSVImportStatus)
async def get_import_status(
    upload_id: str,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """
    Get the status of a CSV import operation.
    
    Args:
        upload_id: Unique identifier for the upload
        db: Database session
        current_user: Authenticated admin user
    
    Returns:
        CSVImportStatus with current progress and results
    """
    csv_service = CSVImportService(db)
    status = await csv_service.get_import_status(upload_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Import not found")
    
    return status

@router.get("/history")
async def get_import_history(
    limit: int = 50,
    offset: int = 0,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """
    Get history of CSV import operations.
    
    Args:
        limit: Maximum number of records to return
        offset: Number of records to skip
        db: Database session
        current_user: Authenticated admin user
    
    Returns:
        List of import history records
    """
    csv_service = CSVImportService(db)
    history = await csv_service.get_import_history(
        user_id=current_user.get('id'),
        limit=limit,
        offset=offset
    )
    
    return {
        "imports": history,
        "total": len(history),
        "limit": limit,
        "offset": offset
    }

@router.delete("/cancel/{upload_id}")
async def cancel_import(
    upload_id: str,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """
    Cancel an ongoing CSV import operation.
    
    Args:
        upload_id: Unique identifier for the upload
        db: Database session
        current_user: Authenticated admin user
    
    Returns:
        Success message
    """
    csv_service = CSVImportService(db)
    success = await csv_service.cancel_import(upload_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Import not found or cannot be cancelled")
    
    return {"message": "Import cancelled successfully"}

@router.get("/template")
async def download_csv_template(
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """
    Download a CSV template with required fields for job import.
    
    Args:
        current_user: Authenticated admin user
    
    Returns:
        CSV template file
    """
    template_data = {
        "title": ["Test Engineer", "Test Analyst"],
        "company": ["Test Company A", "Test Company B"],
        "location": ["Test City, ST", "Test Location, ST"],
        "job_type": ["Full-time", "Contract"],
        "experience_level": ["Mid-level", "Senior"],
        "salary_min": ["80000", "120000"],
        "salary_max": ["120000", "180000"],
        "description": ["Job description here", "Another job description"],
        "requirements": ["Requirements here", "Other requirements"],
        "benefits": ["Benefits here", "Other benefits"],
        "application_url": ["https://example.com/apply1", "https://example.com/apply2"],
        "remote_friendly": ["true", "false"],
        "tags": ["python,django", "data,analytics"]
    }
    
    df = pd.DataFrame(template_data)
    
    # Create CSV content
    output = io.StringIO()
    df.to_csv(output, index=False)
    csv_content = output.getvalue()
    
    return JSONResponse(
        content={"csv_content": csv_content},
        headers={
            "Content-Disposition": "attachment; filename=job_import_template.csv"
        }
    )

@router.post("/validate")
async def validate_csv_data(
    file: UploadFile = File(...),
    config: Optional[str] = None,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """
    Validate CSV data without importing.
    
    Args:
        file: CSV file to validate
        config: Optional JSON string with validation configuration
        db: Database session
        current_user: Authenticated admin user
    
    Returns:
        Validation results with detailed error information
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        csv_service = CSVImportService(db)
        validation_result = await csv_service.validate_csv(
            csv_content=csv_content,
            filename=file.filename,
            upload_id=str(uuid.uuid4()),
            user_id=str(current_user.get('id')),
            config=config,
            validate_only=True
        )
        
        return validation_result
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating CSV file: {str(e)}")

# ============================================================================
# JOB BOARD CONFIGURATION CSV ENDPOINTS
# ============================================================================

class JobBoardCSVUploadResponse(BaseModel):
    upload_id: str
    filename: str
    total_rows: int
    processed: int
    created: int
    updated: int
    skipped: int
    errors: List[str]
    warnings: List[str]
    status: str
    created_at: datetime

@router.post("/job-boards/upload", response_model=JobBoardCSVUploadResponse)
async def upload_job_board_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    test_accessibility: bool = True,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """
    Upload and process a CSV file containing job board configurations.
    
    Args:
        file: CSV file containing job board data (name, url, search_url, etc.)
        test_accessibility: Whether to test website accessibility during import
        db: Database session
        current_user: Authenticated admin user
    
    Returns:
        JobBoardCSVUploadResponse with processing results and upload ID
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    if file.size > 5 * 1024 * 1024:  # 5MB limit for job board configs
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
    
    try:
        # Read CSV content
        content = await file.read()
        
        # Generate upload ID
        upload_id = str(uuid.uuid4())
        
        # Initialize job board config service
        job_board_service = JobBoardConfigService(db)
        
        # Validate CSV format
        is_valid, validation_message, df = await job_board_service.validate_csv_format(content)
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=validation_message)
        
        # Start background processing
        background_tasks.add_task(
            job_board_service.process_csv_import,
            upload_id=upload_id,
            df=df,
            test_accessibility=test_accessibility
        )
        
        return JobBoardCSVUploadResponse(
            upload_id=upload_id,
            filename=file.filename,
            total_rows=len(df),
            processed=0,
            created=0,
            updated=0,
            skipped=0,
            errors=[],
            warnings=[],
            status="processing",
            created_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing job board CSV: {str(e)}")

@router.get("/job-boards/status/{upload_id}")
async def get_job_board_import_status(
    upload_id: str,
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """
    Get the status of a job board CSV import operation.
    
    Args:
        upload_id: Unique identifier for the upload
        db: Database session
        current_user: Authenticated admin user
    
    Returns:
        Import status with progress and results
    """
    job_board_service = JobBoardConfigService(db)
    status = await job_board_service.get_import_status(upload_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Job board import not found")
    
    return status

@router.get("/job-boards/template")
async def download_job_board_csv_template(
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """
    Download a CSV template for job board configurations.
    
    Args:
        current_user: Authenticated admin user
    
    Returns:
        CSV template file with sample job board data
    """
    try:
        # Create a temporary database session for the service
        db = next(get_db())
        job_board_service = JobBoardConfigService(db)
        
        # Generate template
        csv_content = job_board_service.generate_csv_template()
        
        return JSONResponse(
            content={"csv_content": csv_content},
            headers={
                "Content-Disposition": "attachment; filename=job_board_config_template.csv"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating template: {str(e)}")

@router.post("/job-boards/validate")
async def validate_job_board_csv(
    file: UploadFile = File(...),
    # db: Session = Depends(get_db),  # Using MongoDB instead
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """
    Validate job board CSV data without importing.
    
    Args:
        file: CSV file to validate
        db: Database session
        current_user: Authenticated admin user
    
    Returns:
        Validation results with detailed error information
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        content = await file.read()
        
        job_board_service = JobBoardConfigService(db)
        is_valid, validation_message, df = await job_board_service.validate_csv_format(content)
        
        result = {
            "filename": file.filename,
            "is_valid": is_valid,
            "message": validation_message,
            "total_rows": len(df) if df is not None else 0,
            "validation_details": {
                "required_columns": job_board_service.REQUIRED_COLUMNS,
                "optional_columns": list(job_board_service.OPTIONAL_COLUMNS.keys()),
                "found_columns": list(df.columns) if df is not None else []
            }
        }
        
        return result
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please use UTF-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating job board CSV: {str(e)}")


@router.post("/job-boards/run", response_model=dict)
async def run_job_board_scrapers(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """Run all active job board configurations from CSV imports"""
    try:
        return {
            "success": True,
            "message": "Job board scraping functionality temporarily disabled during N8N removal",
            "status": "disabled",
            "initiated_by": current_user.get('email', 'unknown'),
            "initiated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate scraping: {str(e)}")


@router.get("/job-boards/status", response_model=dict)
async def get_job_board_status(
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """Get status of all job board configurations from CSV imports"""
    try:
        return {
            "success": True,
            "data": {"message": "Status functionality temporarily disabled during N8N removal"},
            "retrieved_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/job-boards/run-single/{config_id}", response_model=dict)
async def run_single_job_board_scraper(
    config_id: int,
    background_tasks: BackgroundTasks,
    use_ml_parsing: bool = True,
    confidence_threshold: float = 0.7,
    current_user: dict = Depends(require_permission("admin", "csv_upload"))
):
    """Run a single job board scraper configuration"""
    try:
        return {
            "success": True,
            "message": f"Single scraper functionality temporarily disabled during N8N removal",
            "config_id": config_id,
            "status": "disabled",
            "ml_parsing_enabled": use_ml_parsing,
            "confidence_threshold": confidence_threshold,
            "initiated_by": current_user.get('email', 'unknown'),
            "initiated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate scraper: {str(e)}")