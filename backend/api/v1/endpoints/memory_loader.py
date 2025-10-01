from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import asyncio
from datetime import datetime
import tempfile
import os
import uuid

from backend.services.memory_loader import MemoryLoader, ProcessingProgress
# from backend.database.models import MemoryUpload  # TODO: Migrate MemoryUpload to MongoDB models
# from backend.models.mongodb_models import MemoryUpload  # TODO: Create MemoryUpload MongoDB model
from backend.core.enums import MemoryUploadStatus
from backend.core.auth import get_current_user
from backend.database import get_db_session
# from sqlalchemy.orm import Session  # Using MongoDB instead

router = APIRouter()

# Initialize memory loader
memory_loader = MemoryLoader()

# Pydantic models
class MemoryUploadResponse(BaseModel):
    id: str
    filename: str
    status: str
    total_records: Optional[int]
    processed_records: Optional[int]
    upload_date: str
    processing_started_at: Optional[str]
    processing_completed_at: Optional[str]
    error_log: Optional[str]
    file_size: Optional[int]
    progress_percentage: Optional[float] = 0.0

@router.get("/", response_model=Dict[str, List[MemoryUploadResponse]])
async def get_memories(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db_session)  # db: Any - Using MongoDB instead
):
    """Get all memory uploads as memories for the frontend"""
    try:
        uploads = db.query(MemoryUpload).filter(
            MemoryUpload.user_id == str(current_user.get('id'))
        ).order_by(MemoryUpload.created_at.desc()).limit(50).all()
        
        memories = [
            MemoryUploadResponse(
                id=upload.id,
                filename=upload.filename,
                status=upload.upload_status,
                total_records=upload.total_rows,
                processed_records=upload.processed_rows,
                upload_date=upload.created_at.isoformat(),
                processing_started_at=upload.created_at.isoformat() if upload.created_at else None,
                processing_completed_at=upload.completed_at.isoformat() if upload.completed_at else None,
                error_log=upload.validation_errors,
                file_size=upload.file_size_bytes,
                progress_percentage=upload.progress_percentage or 0.0
            )
            for upload in uploads
        ]
        
        return {"memories": memories}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class MemoryContextResponse(BaseModel):
    website_patterns: Dict[str, Any]
    extraction_rules: Dict[str, List[Any]]
    success_indicators: List[str]
    failure_patterns: List[str]
    custom_selectors: Dict[str, str]
    metadata: Dict[str, Any]
    total_records: int
    processed_records: int

class ProcessingProgressResponse(BaseModel):
    total_rows: int
    processed_rows: int
    successful_rows: int
    failed_rows: int
    current_step: str
    progress_percentage: float
    errors: List[str]
    warnings: List[str]

class ValidationResponse(BaseModel):
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    preview_data: Optional[List[Dict[str, Any]]]

@router.post("/upload", response_model=MemoryUploadResponse)
async def upload_memory_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db_session)  # db: Any - Using MongoDB instead
):
    """Upload memory CSV file for processing"""
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
        # Check file size (limit to 50MB)
        file_content = await file.read()
        if len(file_content) > 50 * 1024 * 1024:  # 50MB
            raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        # Create memory upload record
        memory_upload = MemoryUpload(
            id=str(uuid.uuid4()),
            filename=file.filename,
            original_filename=file.filename,
            file_size_bytes=len(file_content),
            total_rows=0,  # Will be updated after processing
            upload_status="PENDING",
            memory_type="csv",  # Default type
            user_id=str(current_user.get('id')),
            progress_percentage=0.0  # Initialize to 0.0 to prevent None values
        )
        
        db.add(memory_upload)
        db.commit()
        db.refresh(memory_upload)
        
        # Start background processing
        background_tasks.add_task(
            process_memory_file_background,
            memory_upload.id,
            temp_file_path
        )
        
        return MemoryUploadResponse(
            id=memory_upload.id,
            filename=memory_upload.filename,
            status=memory_upload.upload_status,
            total_records=memory_upload.total_rows,
            processed_records=memory_upload.processed_rows,
            upload_date=memory_upload.created_at.isoformat(),
            processing_started_at=memory_upload.created_at.isoformat() if memory_upload.created_at else None,
            processing_completed_at=memory_upload.completed_at.isoformat() if memory_upload.completed_at else None,
            error_log=memory_upload.validation_errors,
            file_size=memory_upload.file_size_bytes,
            progress_percentage=memory_upload.progress_percentage or 0.0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

async def process_memory_file_background(upload_id: str, file_path: str):
    """Background task to process memory file"""
    try:
        # Process the memory file
        await memory_loader.process_memory_upload(upload_id, file_path)
        
    except Exception as e:
        print(f"Background processing failed for upload {upload_id}: {str(e)}")
    finally:
        # Clean up temporary file
        try:
            os.unlink(file_path)
        except:
            pass

@router.get("/uploads", response_model=List[MemoryUploadResponse])
async def list_memory_uploads(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db_session)  # db: Any - Using MongoDB instead
):
    """List memory uploads with optional filtering"""
    try:
        user_id_str = str(current_user.get('id'))
        query = db.query(MemoryUpload).filter(MemoryUpload.user_id == user_id_str)
        
        if status:
            query = query.filter(MemoryUpload.upload_status == status)
        
        uploads = query.offset(offset).limit(limit).all()
        
        return [
            MemoryUploadResponse(
                id=upload.id,
                filename=upload.filename,
                status=upload.upload_status,
                total_records=upload.total_rows,
                processed_records=upload.processed_rows,
                upload_date=upload.created_at.isoformat(),
                processing_started_at=upload.created_at.isoformat() if upload.created_at else None,
                processing_completed_at=upload.completed_at.isoformat() if upload.completed_at else None,
                error_log=upload.validation_errors,
                file_size=upload.file_size_bytes,
                progress_percentage=upload.progress_percentage or 0.0
            )
            for upload in uploads
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/uploads/{upload_id}", response_model=MemoryUploadResponse)
async def get_memory_upload(
    upload_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db_session)  # db: Any - Using MongoDB instead
):
    """Get detailed information about a memory upload"""
    try:
        upload = db.query(MemoryUpload).filter(
            MemoryUpload.id == upload_id,
            MemoryUpload.user_id == str(current_user.get('id'))
        ).first()
        
        if not upload:
            raise HTTPException(status_code=404, detail="Memory upload not found")
        
        return MemoryUploadResponse(
            id=upload.id,
            filename=upload.filename,
            status=upload.upload_status,
            total_records=upload.total_rows,
            processed_records=upload.processed_rows,
            upload_date=upload.created_at.isoformat(),
            processing_started_at=upload.created_at.isoformat() if upload.created_at else None,
            processing_completed_at=upload.completed_at.isoformat() if upload.completed_at else None,
            error_log=upload.validation_errors,
            file_size=upload.file_size_bytes,
            progress_percentage=upload.progress_percentage or 0.0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/uploads/{upload_id}/context", response_model=MemoryContextResponse)
async def get_memory_context(
    upload_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db_session)  # db: Any - Using MongoDB instead
):
    """Get processed memory context for a completed upload"""
    try:
        upload = db.query(MemoryUpload).filter(
            MemoryUpload.id == upload_id,
            MemoryUpload.user_id == str(current_user.get('id'))
        ).first()
        
        if not upload:
            raise HTTPException(status_code=404, detail="Memory upload not found")
        
        if upload.upload_status != "COMPLETED":
            raise HTTPException(status_code=400, detail="Memory upload is not completed yet")
        
        memory_context = await memory_loader.get_memory_context(upload_id)
        
        if not memory_context:
            raise HTTPException(status_code=404, detail="Memory context not found")
        
        return MemoryContextResponse(
            website_patterns=memory_context.website_patterns,
            extraction_rules=memory_context.extraction_rules,
            success_indicators=memory_context.success_indicators,
            failure_patterns=memory_context.failure_patterns,
            custom_selectors=memory_context.custom_selectors,
            metadata=memory_context.metadata,
            total_records=memory_context.total_rows,
            processed_records=memory_context.processed_rows
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate", response_model=ValidationResponse)
async def validate_memory_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Validate memory CSV file format without processing"""
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
        # Create temporary file
        file_content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        try:
            # Validate format
            is_valid, errors = await memory_loader.validate_csv_format(temp_file_path)
            
            # Get preview data
            preview_data = None
            try:
                import pandas as pd
                df = pd.read_csv(temp_file_path)
                preview_data = df.head(5).to_dict('records')
            except:
                pass
            
            return ValidationResponse(
                is_valid=is_valid,
                errors=errors,
                warnings=[],
                preview_data=preview_data
            )
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_file_path)
            except:
                pass
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

@router.get("/uploads/{upload_id}/progress", response_model=ProcessingProgressResponse)
async def get_processing_progress(
    upload_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db_session)  # db: Any - Using MongoDB instead
):
    """Get real-time processing progress for a memory upload"""
    try:
        upload = db.query(MemoryUpload).filter(
            MemoryUpload.id == upload_id,
            MemoryUpload.user_id == str(current_user.get('id'))
        ).first()
        
        if not upload:
            raise HTTPException(status_code=404, detail="Memory upload not found")
        
        # Create progress response based on current status
        if upload.upload_status == MemoryUploadStatus.PENDING.value:
            current_step = "Waiting to start processing"
        elif upload.upload_status == MemoryUploadStatus.PROCESSING.value:
            current_step = "Processing memory data"
        elif upload.upload_status == MemoryUploadStatus.COMPLETED.value:
            current_step = "Processing completed"
        elif upload.upload_status == MemoryUploadStatus.FAILED.value:
            current_step = "Processing failed"
        else:
            current_step = "Unknown status"
        
        return ProcessingProgressResponse(
            total_rows=upload.total_records or 0,
            processed_rows=upload.processed_records or 0,
            successful_rows=upload.processed_records or 0,
            failed_rows=(upload.total_records or 0) - (upload.processed_records or 0),
            current_step=current_step,
            progress_percentage=upload.progress_percentage or 0.0,
            errors=json.loads(upload.validation_errors) if upload.validation_errors else [],
            warnings=[]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/template")
async def download_csv_template():
    """Download CSV template for memory uploads"""
    try:
        template_csv = await memory_loader.generate_csv_template()
        
        return StreamingResponse(
            iter([template_csv]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=memory_template.csv"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template generation failed: {str(e)}")

@router.delete("/uploads/{upload_id}")
async def delete_memory_upload(
    upload_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db_session)  # db: Any - Using MongoDB instead
):
    """Delete a memory upload and its data"""
    try:
        upload = db.query(MemoryUpload).filter(
            MemoryUpload.id == upload_id,
            MemoryUpload.user_id == str(current_user.get('id'))
        ).first()
        
        if not upload:
            raise HTTPException(status_code=404, detail="Memory upload not found")
        
        # Clean up file if it exists
        if upload.file_path and os.path.exists(upload.file_path):
            try:
                os.unlink(upload.file_path)
            except:
                pass
        
        # Delete from database
        db.delete(upload)
        db.commit()
        
        return {"success": True, "message": "Memory upload deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/uploads/{upload_id}/stream")
async def stream_processing_progress(
    upload_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db_session)  # db: Any - Using MongoDB instead
):
    """Stream real-time processing progress updates"""
    async def generate_progress_stream():
        try:
            while True:
                # Get current upload status
                upload = db.query(MemoryUpload).filter(
                    MemoryUpload.id == upload_id,
                    MemoryUpload.user_id == str(current_user.get('id'))
                ).first()
                
                if not upload:
                    yield f"data: {{\"error\": \"Upload not found\"}}\n\n"
                    break
                
                # Create progress data
                progress_data = {
                    "upload_id": upload_id,
                    "status": upload.upload_status,
                    "progress_percentage": (upload.progress_percentage or 0.0),
                    "total_records": upload.total_rows or 0,
                    "processed_records": upload.processed_rows or 0,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                yield f"data: {json.dumps(progress_data)}\n\n"
                
                # Stop streaming if processing is complete
                if upload.upload_status in ["COMPLETED", "FAILED"]:
                    break
                
                await asyncio.sleep(2)  # Update every 2 seconds
                
        except Exception as e:
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
    
    return StreamingResponse(
        generate_progress_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )