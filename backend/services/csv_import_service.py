import csv
import io
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorDatabase
# from bson import ObjectId  # Removed to fix Pydantic schema generation
import asyncio
from concurrent.futures import ThreadPoolExecutor
from backend.services.job_validation_service import JobDataValidator
from backend.services.ml_parsing_service import MLParsingService
from backend.schemas.job_post import JobPostCreate
from backend.core.enums import JobType, ExperienceLevel, CSVImportStatus
from backend.core.config import settings

class CSVImportService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.validator = JobDataValidator()
        self.ml_service = MLParsingService()
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def validate_csv(
        self,
        csv_content: str,
        filename: str,
        upload_id: str,
        user_id: str,
        config: Optional[str] = None,
        validate_only: bool = False
    ) -> Dict[str, Any]:
        """
        Validate CSV content and return validation results.
        
        Args:
            csv_content: Raw CSV content as string
            filename: Original filename
            upload_id: Unique identifier for this upload
            user_id: ID of the user performing the upload
            config: Optional JSON configuration string
            validate_only: If True, don't create database records
        
        Returns:
            Dictionary with validation results
        """
        try:
            # Parse configuration
            import_config = self._parse_config(config) if config else {}
            
            # Read CSV data
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(csv_reader)
            
            total_rows = len(rows)
            valid_rows = 0
            invalid_rows = 0
            errors = []
            
            # Create CSV import record if not validate_only
            if not validate_only:
                csv_import_doc = {
                    '_id': upload_id,
                    'filename': filename,
                    'user_id': user_id,
                    'total_rows': total_rows,
                    'status': CSVImportStatus.VALIDATING.value,
                    'config': config,
                    'created_at': datetime.utcnow()
                }
                await self.db.csv_imports.insert_one(csv_import_doc)
            
            # Validate each row
            for row_index, row in enumerate(rows, start=1):
                try:
                    # Apply field mappings if configured
                    mapped_row = self._apply_field_mappings(row, import_config.get('field_mappings', []))
                    
                    # Validate job data
                    validation_result = await self.validator.validate_job_data(mapped_row)
                    
                    if validation_result['is_valid']:
                        # Check for duplicates if enabled
                        if import_config.get('skip_duplicates', True):
                            if await self._check_duplicate(mapped_row):
                                errors.append({
                                    'row': row_index,
                                    'type': 'duplicate',
                                    'message': 'Job already exists in database',
                                    'data': mapped_row
                                })
                                invalid_rows += 1
                                continue
                        
                        valid_rows += 1
                    else:
                        invalid_rows += 1
                        errors.append({
                            'row': row_index,
                            'type': 'validation',
                            'message': validation_result['errors'],
                            'data': mapped_row
                        })
                        
                except Exception as e:
                    invalid_rows += 1
                    errors.append({
                        'row': row_index,
                        'type': 'parsing',
                        'message': f'Error parsing row: {str(e)}',
                        'data': row
                    })
            
            # Update import record if not validate_only
            if not validate_only:
                await self.db.csv_imports.update_one(
                    {'_id': upload_id},
                    {'$set': {
                        'valid_rows': valid_rows,
                        'invalid_rows': invalid_rows,
                        'status': CSVImportStatus.VALIDATED.value
                    }}
                )
            
            return {
                'total_rows': total_rows,
                'valid_rows': valid_rows,
                'invalid_rows': invalid_rows,
                'errors': errors[:100]  # Limit errors to first 100
            }
            
        except Exception as e:
            if not validate_only:
                # Update import record with error status
                await self.db.csv_imports.update_one(
                    {'_id': upload_id},
                    {'$set': {
                        'status': CSVImportStatus.FAILED.value,
                        'error_message': str(e)
                    }}
                )
            
            raise Exception(f"CSV validation failed: {str(e)}")
    
    async def process_csv_import(
        self,
        upload_id: str,
        csv_content: str,
        config: Optional[str] = None
    ) -> None:
        """
        Process CSV import in background.
        
        Args:
            upload_id: Unique identifier for the upload
            csv_content: Raw CSV content
            config: Optional JSON configuration string
        """
        try:
            # Get import record
            csv_import = await self.db.csv_imports.find_one({'_id': upload_id})
            if not csv_import:
                raise Exception("Import record not found")
            
            # Update status to processing
            await self.db.csv_imports.update_one(
                {'_id': upload_id},
                {'$set': {
                    'status': CSVImportStatus.PROCESSING.value,
                    'started_at': datetime.utcnow()
                }}
            )
            
            # Parse configuration
            import_config = self._parse_config(config) if config else {}
            
            # Read CSV data
            csv_reader = csv.DictReader(io.StringIO(csv_content))
            rows = list(csv_reader)
            
            successful_imports = 0
            failed_imports = 0
            
            # Process each valid row
            for row_index, row in enumerate(rows, start=1):
                try:
                    # Apply field mappings
                    mapped_row = self._apply_field_mappings(row, import_config.get('field_mappings', []))
                    
                    # Validate job data
                    validation_result = await self.validator.validate_job_data(mapped_row)
                    
                    if validation_result['is_valid']:
                        # Check for duplicates
                        if import_config.get('skip_duplicates', True):
                            if await self._check_duplicate(mapped_row):
                                continue
                        
                        # Create job post
                        job_data = self._convert_to_job_post(mapped_row)
                        
                        # Apply ML parsing if enabled
                        if import_config.get('ml_parsing_enabled', False):
                            ml_result = await self.ml_service.parse_job_data(
                                html_content=mapped_row.get('description', ''),
                                field_mapping=import_config.get('field_mappings', [])
                            )
                            if ml_result['confidence'] > 0.7:
                                job_data.update(ml_result['data'])
                        
                        # Save to database
                        job_data['_id'] = ObjectId()
                        job_data['created_at'] = datetime.utcnow()
                        result = await self.db.job_posts.insert_one(job_data)
                        job_id = result.inserted_id
                        
                        # Log successful import
                        await self._log_import_result(
                            upload_id=upload_id,
                            row_number=row_index,
                            status='success',
                            job_id=str(job_id),
                            data=mapped_row
                        )
                        
                        successful_imports += 1
                        
                    else:
                        # Log validation failure
                        await self._log_import_result(
                            upload_id=upload_id,
                            row_number=row_index,
                            status='validation_failed',
                            error_message=str(validation_result['errors']),
                            data=mapped_row
                        )
                        failed_imports += 1
                        
                except Exception as e:
                    # Log processing error
                    await self._log_import_result(
                        upload_id=upload_id,
                        row_number=row_index,
                        status='error',
                        error_message=str(e),
                        data=row
                    )
                    failed_imports += 1
                
                # Update progress
                progress = (row_index / len(rows)) * 100
                
                # Update every 10 rows
                if row_index % 10 == 0:
                    await self.db.csv_imports.update_one(
                        {'_id': upload_id},
                        {'$set': {
                            'progress': progress,
                            'processed_rows': row_index,
                            'successful_imports': successful_imports,
                            'failed_imports': failed_imports
                        }}
                    )
            
            # Final update
            await self.db.csv_imports.update_one(
                {'_id': upload_id},
                {'$set': {
                    'status': CSVImportStatus.COMPLETED.value,
                    'completed_at': datetime.utcnow(),
                    'progress': 100.0,
                    'processed_rows': len(rows),
                    'successful_imports': successful_imports,
                    'failed_imports': failed_imports
                }}
            )
            
        except Exception as e:
            # Update import record with error
            await self.db.csv_imports.update_one(
                {'_id': upload_id},
                {'$set': {
                    'status': CSVImportStatus.FAILED.value,
                    'error_message': str(e),
                    'completed_at': datetime.utcnow()
                }}
            )
            
            raise
    
    async def get_import_status(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of an import operation.
        
        Args:
            upload_id: Unique identifier for the upload
        
        Returns:
            Dictionary with import status information
        """
        csv_import = await self.db.csv_imports.find_one({'_id': upload_id})
        
        if not csv_import:
            return None
        
        # Get recent errors from logs
        recent_errors = await self.db.csv_import_logs.find({
            'upload_id': upload_id,
            'status': {'$in': ['validation_failed', 'error']}
        }).sort('created_at', -1).limit(10).to_list(length=10)
        
        errors = []
        for log in recent_errors:
            errors.append({
                'row': log.get('row_number'),
                'message': log.get('error_message'),
                'data': json.loads(log.get('data')) if log.get('data') else None
            })
        
        return {
            'upload_id': csv_import.get('_id'),
            'status': csv_import.get('status'),
            'progress': csv_import.get('progress', 0.0),
            'total_rows': csv_import.get('total_rows'),
            'processed_rows': csv_import.get('processed_rows', 0),
            'successful_imports': csv_import.get('successful_imports', 0),
            'failed_imports': csv_import.get('failed_imports', 0),
            'errors': errors,
            'started_at': csv_import.get('started_at'),
            'completed_at': csv_import.get('completed_at')
        }
    
    async def get_import_history(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get import history for a user.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of records
            offset: Number of records to skip
        
        Returns:
            List of import history records
        """
        imports = await self.db.csv_imports.find({
            'user_id': user_id
        }).sort('created_at', -1).skip(offset).limit(limit).to_list(length=limit)
        
        history = []
        for imp in imports:
            history.append({
                'upload_id': imp.get('_id'),
                'filename': imp.get('filename'),
                'status': imp.get('status'),
                'total_rows': imp.get('total_rows'),
                'successful_imports': imp.get('successful_imports', 0),
                'failed_imports': imp.get('failed_imports', 0),
                'created_at': imp.get('created_at'),
                'completed_at': imp.get('completed_at')
            })
        
        return history
    
    async def cancel_import(self, upload_id: str) -> bool:
        """
        Cancel an ongoing import operation.
        
        Args:
            upload_id: Unique identifier for the upload
        
        Returns:
            True if cancelled successfully, False otherwise
        """
        csv_import = await self.db.csv_imports.find_one({'_id': upload_id})
        
        if not csv_import or csv_import.get('status') not in [CSVImportStatus.PROCESSING.value, CSVImportStatus.VALIDATING.value]:
            return False
        
        result = await self.db.csv_imports.update_one(
            {'_id': upload_id},
            {'$set': {
                'status': CSVImportStatus.CANCELLED.value,
                'completed_at': datetime.utcnow()
            }}
        )
        
        return result.modified_count > 0
    
    def _parse_config(self, config_str: str) -> Dict[str, Any]:
        """
        Parse configuration JSON string.
        
        Args:
            config_str: JSON configuration string
        
        Returns:
            Parsed configuration dictionary
        """
        try:
            return json.loads(config_str)
        except json.JSONDecodeError:
            return {}
    
    def _apply_field_mappings(self, row: Dict[str, str], mappings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Apply field mappings to a CSV row.
        
        Args:
            row: Original CSV row data
            mappings: List of field mapping configurations
        
        Returns:
            Mapped row data
        """
        if not mappings:
            return row
        
        mapped_row = {}
        
        for mapping in mappings:
            csv_field = mapping.get('csv_field')
            job_field = mapping.get('job_field')
            transform = mapping.get('transform')
            
            if csv_field in row:
                value = row[csv_field]
                
                # Apply transformations
                if transform == 'lowercase':
                    value = value.lower()
                elif transform == 'uppercase':
                    value = value.upper()
                elif transform == 'strip':
                    value = value.strip()
                elif transform == 'boolean':
                    value = value.lower() in ['true', '1', 'yes', 'y']
                elif transform == 'integer':
                    try:
                        value = int(value)
                    except ValueError:
                        value = None
                elif transform == 'float':
                    try:
                        value = float(value)
                    except ValueError:
                        value = None
                
                mapped_row[job_field] = value
        
        # Copy unmapped fields
        for key, value in row.items():
            if key not in [m.get('csv_field') for m in mappings]:
                mapped_row[key] = value
        
        return mapped_row
    
    async def _check_duplicate(self, job_data: Dict[str, Any]) -> bool:
        """
        Check if a job already exists in the database.
        
        Args:
            job_data: Job data to check
        
        Returns:
            True if duplicate found, False otherwise
        """
        title = job_data.get('title', '')
        company = job_data.get('company', '')
        location = job_data.get('location', '')
        
        if not title or not company:
            return False
        
        existing_job = await self.db.job_posts.find_one({
            'title': {'$regex': title, '$options': 'i'},
            'company': {'$regex': company, '$options': 'i'},
            'location': {'$regex': location, '$options': 'i'}
        })
        
        return existing_job is not None
    
    def _convert_to_job_post(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert validated job data to JobPost format.
        
        Args:
            job_data: Validated job data
        
        Returns:
            JobPost-compatible data dictionary
        """
        # Map job type
        job_type_str = job_data.get('job_type', '').lower()
        job_type = JobType.FULL_TIME  # default
        if 'part' in job_type_str:
            job_type = JobType.PART_TIME
        elif 'contract' in job_type_str:
            job_type = JobType.CONTRACT
        elif 'intern' in job_type_str:
            job_type = JobType.INTERNSHIP
        
        # Map experience level
        exp_level_str = job_data.get('experience_level', '').lower()
        experience_level = ExperienceLevel.MID_LEVEL  # default
        if 'entry' in exp_level_str or 'junior' in exp_level_str:
            experience_level = ExperienceLevel.ENTRY_LEVEL
        elif 'senior' in exp_level_str:
            experience_level = ExperienceLevel.SENIOR_LEVEL
        elif 'lead' in exp_level_str or 'principal' in exp_level_str:
            experience_level = ExperienceLevel.LEAD_LEVEL
        
        return {
            'title': job_data.get('title', ''),
            'company': job_data.get('company', ''),
            'location': job_data.get('location', ''),
            'job_type': job_type,
            'experience_level': experience_level,
            'salary_min': job_data.get('salary_min'),
            'salary_max': job_data.get('salary_max'),
            'description': job_data.get('description', ''),
            'requirements': job_data.get('requirements', ''),
            'benefits': job_data.get('benefits', ''),
            'application_url': job_data.get('application_url', ''),
            'remote_friendly': job_data.get('remote_friendly', False),
            'tags': job_data.get('tags', ''),
            'is_active': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
    
    async def _log_import_result(
        self,
        upload_id: str,
        row_number: int,
        status: str,
        job_id: Optional[str] = None,
        error_message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log the result of processing a single row.
        
        Args:
            upload_id: Unique identifier for the upload
            row_number: Row number in the CSV
            status: Processing status (success, validation_failed, error)
            job_id: ID of created job (if successful)
            error_message: Error message (if failed)
            data: Original row data
        """
        log_entry = {
            '_id': str(ObjectId()),
            'upload_id': upload_id,
            'row_number': row_number,
            'status': status,
            'job_id': job_id,
            'error_message': error_message,
            'data': json.dumps(data) if data else None,
            'created_at': datetime.utcnow()
        }
        
        await self.db.csv_import_logs.insert_one(log_entry)