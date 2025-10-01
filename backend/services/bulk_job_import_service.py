import asyncio
from typing import List, Dict, Any, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
# from bson import ObjectId  # Removed to fix Pydantic schema generation
from datetime import datetime
import hashlib
import json

from backend.services.job_validation_service import JobDataValidator
from backend.services.ml_parsing_service import MLParsingService
from backend.core.enums import JobType, ExperienceLevel, JobStatus, CSVImportStatus
from backend.core.config import settings

class BulkJobImportService:
    """
    Service for handling bulk job imports with advanced duplicate detection,
    data validation, and ML-enhanced processing.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.validator = JobDataValidator()
        self.ml_service = MLParsingService()
        self.duplicate_threshold = 0.85  # Similarity threshold for duplicate detection
    
    async def import_jobs_bulk(
        self,
        job_data_list: List[Dict[str, Any]],
        import_config: Dict[str, Any],
        upload_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Import multiple jobs with duplicate detection and validation.
        
        Args:
            job_data_list: List of job data dictionaries
            import_config: Configuration for import process
            upload_id: Unique identifier for this import batch
            user_id: ID of the user performing the import
        
        Returns:
            Dictionary with import results and statistics
        """
        results = {
            'total_processed': 0,
            'successful_imports': 0,
            'duplicates_found': 0,
            'validation_failures': 0,
            'processing_errors': 0,
            'imported_jobs': [],
            'duplicate_jobs': [],
            'failed_jobs': [],
            'processing_time': 0
        }
        
        start_time = datetime.utcnow()
        
        try:
            # Pre-process jobs for duplicate detection
            if import_config.get('skip_duplicates', True):
                job_data_list = await self._remove_internal_duplicates(job_data_list)
            
            # Process jobs in batches for better performance
            batch_size = import_config.get('batch_size', 50)
            
            for i in range(0, len(job_data_list), batch_size):
                batch = job_data_list[i:i + batch_size]
                batch_results = await self._process_job_batch(
                    batch=batch,
                    import_config=import_config,
                    upload_id=upload_id,
                    user_id=user_id,
                    batch_start_index=i
                )
                
                # Aggregate results
                results['total_processed'] += batch_results['total_processed']
                results['successful_imports'] += batch_results['successful_imports']
                results['duplicates_found'] += batch_results['duplicates_found']
                results['validation_failures'] += batch_results['validation_failures']
                results['processing_errors'] += batch_results['processing_errors']
                results['imported_jobs'].extend(batch_results['imported_jobs'])
                results['duplicate_jobs'].extend(batch_results['duplicate_jobs'])
                results['failed_jobs'].extend(batch_results['failed_jobs'])
                
                # Update progress
                await self._update_import_progress(
                    upload_id=upload_id,
                    processed=min(i + batch_size, len(job_data_list)),
                    total=len(job_data_list)
                )
        
        except Exception as e:
            raise Exception(f"Bulk import failed: {str(e)}")
        
        finally:
            end_time = datetime.utcnow()
            results['processing_time'] = (end_time - start_time).total_seconds()
        
        return results
    
    async def _process_job_batch(
        self,
        batch: List[Dict[str, Any]],
        import_config: Dict[str, Any],
        upload_id: str,
        user_id: str,
        batch_start_index: int
    ) -> Dict[str, Any]:
        """
        Process a batch of jobs.
        
        Args:
            batch: List of job data dictionaries in this batch
            import_config: Configuration for import process
            upload_id: Unique identifier for this import
            user_id: ID of the user performing the import
            batch_start_index: Starting index of this batch in the full list
        
        Returns:
            Dictionary with batch processing results
        """
        batch_results = {
            'total_processed': 0,
            'successful_imports': 0,
            'duplicates_found': 0,
            'validation_failures': 0,
            'processing_errors': 0,
            'imported_jobs': [],
            'duplicate_jobs': [],
            'failed_jobs': []
        }
        
        for index, job_data in enumerate(batch):
            row_number = batch_start_index + index + 1
            batch_results['total_processed'] += 1
            
            try:
                # Validate job data
                validation_result = await self.validator.validate_job_data(job_data)
                
                if not validation_result['is_valid']:
                    batch_results['validation_failures'] += 1
                    batch_results['failed_jobs'].append({
                        'row_number': row_number,
                        'data': job_data,
                        'error': 'Validation failed',
                        'details': validation_result['errors']
                    })
                    
                    # Log validation failure
                    await self._log_import_result(
                        upload_id=upload_id,
                        row_number=row_number,
                        status='validation_failed',
                        error_message=str(validation_result['errors']),
                        data=job_data
                    )
                    continue
                
                # Check for duplicates
                if import_config.get('skip_duplicates', True):
                    duplicate_job = await self._find_duplicate_job(job_data)
                    if duplicate_job:
                        batch_results['duplicates_found'] += 1
                        batch_results['duplicate_jobs'].append({
                            'row_number': row_number,
                            'data': job_data,
                            'existing_job_id': duplicate_job.id,
                            'similarity_score': await self._calculate_similarity(job_data, duplicate_job)
                        })
                        
                        # Log duplicate
                        await self._log_import_result(
                            upload_id=upload_id,
                            row_number=row_number,
                            status='duplicate',
                            error_message=f'Duplicate of job ID {duplicate_job.id}',
                            data=job_data
                        )
                        continue
                
                # Apply ML parsing if enabled
                if import_config.get('ml_parsing_enabled', False):
                    job_data = await self._apply_ml_parsing(job_data, import_config)
                
                # Create job post
                job_post = await self._create_job_post(job_data, user_id)
                
                batch_results['successful_imports'] += 1
                batch_results['imported_jobs'].append({
                    'row_number': row_number,
                    'job_id': job_post.id,
                    'title': job_post.title,
                    'company': job_post.company
                })
                
                # Log successful import
                await self._log_import_result(
                    upload_id=upload_id,
                    row_number=row_number,
                    status='success',
                    job_id=job_post.id,
                    data=job_data
                )
                
            except Exception as e:
                batch_results['processing_errors'] += 1
                batch_results['failed_jobs'].append({
                    'row_number': row_number,
                    'data': job_data,
                    'error': 'Processing error',
                    'details': str(e)
                })
                
                # Log processing error
                await self._log_import_result(
                    upload_id=upload_id,
                    row_number=row_number,
                    status='error',
                    error_message=str(e),
                    data=job_data
                )
        
        return batch_results
    
    async def _remove_internal_duplicates(self, job_data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicates within the import batch itself.
        
        Args:
            job_data_list: List of job data dictionaries
        
        Returns:
            List with internal duplicates removed
        """
        seen_hashes = set()
        unique_jobs = []
        
        for job_data in job_data_list:
            job_hash = self._generate_job_hash(job_data)
            if job_hash not in seen_hashes:
                seen_hashes.add(job_hash)
                unique_jobs.append(job_data)
        
        return unique_jobs
    
    async def _find_duplicate_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find potential duplicate jobs in the database.
        
        Args:
            job_data: Job data to check for duplicates
        
        Returns:
            Job document if duplicate found, None otherwise
        """
        title = job_data.get('title', '').strip()
        company = job_data.get('company', '').strip()
        location = job_data.get('location', '').strip()
        
        if not title or not company:
            return None
        
        # First, try exact match
        exact_match = await self.db.job_posts.find_one({
            "title": {"$regex": f"^{title}$", "$options": "i"},
            "company": {"$regex": f"^{company}$", "$options": "i"},
            "location": {"$regex": f"^{location}$", "$options": "i"}
        })
        
        if exact_match:
            return exact_match
        
        # Then try fuzzy matching
        similar_jobs = await self.db.job_posts.find({
            "$and": [
                {"title": {"$regex": title[:20], "$options": "i"}},
                {"company": {"$regex": company, "$options": "i"}}
            ]
        }).limit(10).to_list(length=10)
        
        for job in similar_jobs:
            similarity = await self._calculate_similarity(job_data, job)
            if similarity >= self.duplicate_threshold:
                return job
        
        return None
    
    async def _calculate_similarity(self, job_data: Dict[str, Any], existing_job: Dict[str, Any]) -> float:
        """
        Calculate similarity score between job data and existing job.
        
        Args:
            job_data: New job data
            existing_job: Existing job document from database
        
        Returns:
            Similarity score between 0 and 1
        """
        # Simple similarity calculation based on key fields
        title_similarity = self._text_similarity(
            job_data.get('title', ''),
            existing_job.get('title', '')
        )
        
        company_similarity = self._text_similarity(
            job_data.get('company', ''),
            existing_job.get('company', '')
        )
        
        location_similarity = self._text_similarity(
            job_data.get('location', ''),
            existing_job.get('location', '')
        )
        
        # Weighted average
        similarity = (
            title_similarity * 0.4 +
            company_similarity * 0.4 +
            location_similarity * 0.2
        )
        
        return similarity
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using simple character-based comparison.
        
        Args:
            text1: First text string
            text2: Second text string
        
        Returns:
            Similarity score between 0 and 1
        """
        if not text1 or not text2:
            return 0.0
        
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        if text1 == text2:
            return 1.0
        
        # Simple character-based similarity
        longer = text1 if len(text1) > len(text2) else text2
        shorter = text2 if len(text1) > len(text2) else text1
        
        if len(longer) == 0:
            return 1.0
        
        # Count matching characters
        matches = sum(1 for i, char in enumerate(shorter) if i < len(longer) and char == longer[i])
        
        return matches / len(longer)
    
    def _generate_job_hash(self, job_data: Dict[str, Any]) -> str:
        """
        Generate a hash for job data to identify duplicates.
        
        Args:
            job_data: Job data dictionary
        
        Returns:
            Hash string
        """
        # Create hash based on key fields
        key_fields = [
            job_data.get('title', '').lower().strip(),
            job_data.get('company', '').lower().strip(),
            job_data.get('location', '').lower().strip()
        ]
        
        hash_string = '|'.join(key_fields)
        return hashlib.md5(hash_string.encode()).hexdigest()
    
    async def _apply_ml_parsing(self, job_data: Dict[str, Any], import_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply ML parsing to enhance job data.
        
        Args:
            job_data: Original job data
            import_config: Import configuration
        
        Returns:
            Enhanced job data
        """
        try:
            # Use ML service to parse and enhance job data
            ml_result = await self.ml_service.parse_job_data(
                html_content=job_data.get('description', ''),
                field_mapping=import_config.get('field_mappings', [])
            )
            
            # Only use ML results if confidence is high enough
            confidence_threshold = import_config.get('ml_confidence_threshold', 0.7)
            if ml_result['confidence'] >= confidence_threshold:
                # Merge ML results with original data
                enhanced_data = job_data.copy()
                enhanced_data.update(ml_result['data'])
                return enhanced_data
        
        except Exception as e:
            # Log ML parsing error but continue with original data
            print(f"ML parsing failed: {str(e)}")
        
        return job_data
    
    async def _create_job_post(self, job_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Create a new job post from validated data.
        
        Args:
            job_data: Validated job data
            user_id: ID of the user creating the job
        
        Returns:
            Created job document
        """
        # Map job type
        job_type_str = job_data.get('job_type', '').lower()
        job_type = JobType.FULL_TIME.value  # default
        if 'part' in job_type_str:
            job_type = JobType.PART_TIME.value
        elif 'contract' in job_type_str:
            job_type = JobType.CONTRACT.value
        elif 'intern' in job_type_str:
            job_type = JobType.INTERNSHIP.value
        elif 'freelance' in job_type_str:
            job_type = JobType.FREELANCE.value
        
        # Map experience level
        exp_level_str = job_data.get('experience_level', '').lower()
        experience_level = ExperienceLevel.MID.value  # default
        if 'entry' in exp_level_str or 'junior' in exp_level_str:
            experience_level = ExperienceLevel.ENTRY.value
        elif 'senior' in exp_level_str:
            experience_level = ExperienceLevel.SENIOR.value
        elif 'lead' in exp_level_str or 'principal' in exp_level_str:
            experience_level = ExperienceLevel.LEAD.value
        
        # Create job document
        job_document = {
            "title": job_data.get('title', ''),
            "company": job_data.get('company', ''),
            "location": job_data.get('location', ''),
            "job_type": job_type,
            "experience_level": experience_level,
            "salary_min": job_data.get('salary_min'),
            "salary_max": job_data.get('salary_max'),
            "description": job_data.get('description', ''),
            "requirements": job_data.get('requirements', ''),
            "benefits": job_data.get('benefits', ''),
            "application_url": job_data.get('application_url', ''),
            "remote_friendly": job_data.get('remote_friendly', False),
            "tags": job_data.get('tags', ''),
            "status": JobStatus.ACTIVE.value,  # Auto-approve imported jobs
            "is_active": True,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await self.db.job_posts.insert_one(job_document)
        job_document["_id"] = result.inserted_id
        
        return job_document
    
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
        Log the result of processing a single job.
        
        Args:
            upload_id: Unique identifier for the upload
            row_number: Row number in the CSV
            status: Processing status
            job_id: ID of created job (if successful)
            error_message: Error message (if failed)
            data: Original job data
        """
        log_document = {
            "upload_id": upload_id,
            "row_number": row_number,
            "status": status,
            "job_id": job_id,
            "error_message": error_message,
            "data": json.dumps(data) if data else None,
            "created_at": datetime.utcnow()
        }
        
        await self.db.csv_import_logs.insert_one(log_document)
    
    async def _update_import_progress(
        self,
        upload_id: str,
        processed: int,
        total: int
    ) -> None:
        """
        Update the progress of an import operation.
        
        Args:
            upload_id: Unique identifier for the upload
            processed: Number of jobs processed so far
            total: Total number of jobs to process
        """
        # Determine status based on progress
        status = CSVImportStatus.PROCESSING.value
        if processed == total:
            status = CSVImportStatus.COMPLETED.value
        elif processed > 0:
            status = CSVImportStatus.PROCESSING.value
        
        # Update the CSV import record with current progress
        await self.db.csv_imports.update_one(
            {"upload_id": upload_id},
            {
                "$set": {
                    "processed_count": processed,
                    "total_count": total,
                    "progress_percentage": (processed / total * 100) if total > 0 else 0,
                    "status": status,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    
    async def get_import_status(self, upload_id: str) -> Dict[str, Any]:
        """
        Get the current status of an import operation.
        
        Args:
            upload_id: Unique identifier for the upload
        
        Returns:
            Dictionary with import status information
        """
        csv_import = await self.db.csv_imports.find_one(
            {"upload_id": upload_id}
        )
        
        if not csv_import:
            return {'error': 'Import not found'}
        
        # Get detailed logs
        logs = await self.db.csv_import_logs.find(
            {"upload_id": upload_id}
        ).sort("row_number", 1).to_list(length=None)
        
        # Calculate statistics
        total_logs = len(logs)
        success_count = len([log for log in logs if log.get('status') == 'success'])
        error_count = len([log for log in logs if log.get('status') == 'error'])
        duplicate_count = len([log for log in logs if log.get('status') == 'duplicate'])
        validation_failed_count = len([log for log in logs if log.get('status') == 'validation_failed'])
        
        return {
            'upload_id': upload_id,
            'status': csv_import.get('status'),
            'total_count': csv_import.get('total_count'),
            'processed_count': csv_import.get('processed_count'),
            'progress_percentage': csv_import.get('progress_percentage'),
            'created_at': csv_import.get('created_at').isoformat() if csv_import.get('created_at') else None,
            'updated_at': csv_import.get('updated_at').isoformat() if csv_import.get('updated_at') else None,
            'statistics': {
                'total_processed': total_logs,
                'successful_imports': success_count,
                'errors': error_count,
                'duplicates': duplicate_count,
                'validation_failures': validation_failed_count
            },
            'logs': [{
                'row_number': log.get('row_number'),
                'status': log.get('status'),
                'job_id': log.get('job_id'),
                'error_message': log.get('error_message'),
                'created_at': log.get('created_at').isoformat() if log.get('created_at') else None
            } for log in logs[-50:]]  # Return last 50 logs
        }
    
    async def cancel_import(self, upload_id: str) -> bool:
        """
        Cancel an ongoing import operation.
        
        Args:
            upload_id: Unique identifier for the upload
        
        Returns:
            True if cancelled successfully, False otherwise
        """
        csv_import = await self.db.csv_imports.find_one(
            {"upload_id": upload_id}
        )
        
        if not csv_import:
            return False
        
        # Only allow cancellation of pending or processing imports
        if csv_import.get('status') in [CSVImportStatus.PENDING.value, CSVImportStatus.PROCESSING.value, CSVImportStatus.VALIDATING.value]:
            result = await self.db.csv_imports.update_one(
                {"upload_id": upload_id},
                {
                    "$set": {
                        "status": CSVImportStatus.CANCELLED.value,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        
        return False
    
    async def get_import_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get import history for a user.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of imports to return
        
        Returns:
            List of import history records
        """
        imports = await self.db.csv_imports.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit).to_list(length=None)
        
        history = []
        for import_record in imports:
            # Get statistics for this import
            logs = await self.db.csv_import_logs.find(
                {"upload_id": import_record.get('upload_id')}
            ).to_list(length=None)
            
            success_count = len([log for log in logs if log.get('status') == 'success'])
            error_count = len([log for log in logs if log.get('status') == 'error'])
            
            history.append({
                'upload_id': import_record.get('upload_id'),
                'filename': import_record.get('filename'),
                'status': import_record.get('status'),
                'total_count': import_record.get('total_count'),
                'processed_count': import_record.get('processed_count'),
                'progress_percentage': import_record.get('progress_percentage'),
                'successful_imports': success_count,
                'errors': error_count,
                'created_at': import_record.get('created_at').isoformat() if import_record.get('created_at') else None,
                'updated_at': import_record.get('updated_at').isoformat() if import_record.get('updated_at') else None
            })
        
        return history