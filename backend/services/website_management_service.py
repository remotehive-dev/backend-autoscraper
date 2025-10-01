import csv
import io
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
# from sqlalchemy.orm import Session  # Using MongoDB instead
# from sqlalchemy import and_, or_  # Using MongoDB instead
import re
import asyncio
from urllib.parse import urlparse

# from backend.models.mongodb_models import ManagedWebsite, MemoryUpload  # Models not available in MongoDB structure
from backend.schemas.website_management import (
    WebsiteUploadResponse, WebsiteUploadStatus, WebsiteValidationResult, WebsiteConfig
)

logger = logging.getLogger(__name__)

class WebsiteManagementService:
    """Service for managing bulk website uploads and operations."""
    
    def __init__(self, db=None):  # db: Session - Using MongoDB instead
        self.db = db
        self.required_fields = ['name', 'url', 'category']
        self.optional_fields = [
            'scraping_enabled', 'rate_limit', 'max_pages', 
            'custom_headers', 'selectors'
        ]
        
    async def process_bulk_upload(
        self,
        csv_content: str,
        user_id: int,
        enable_validation: bool = True,
        auto_categorize: bool = False,
        default_rate_limit: int = 5,
        default_max_pages: int = 100
    ) -> WebsiteUploadResponse:
        """Process bulk website upload from CSV content."""
        
        upload_id = str(uuid.uuid4())
        
        try:
            # Parse CSV content
            websites_data = self._parse_csv_content(csv_content)
            
            if not websites_data:
                raise ValueError("No valid website data found in CSV")
            
            # Create upload record
            upload_record = MemoryUpload(
                id=upload_id,
                user_id=str(user_id),
                memory_type="websites",
                filename=f"websites_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                original_filename=f"websites_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                file_size_bytes=len(csv_content.encode('utf-8')),
                upload_status="processing",
                total_rows=len(websites_data),
                processed_rows=0,
                progress_percentage=0.0  # Initialize to prevent None values
            )
            self.db.add(upload_record)
            self.db.commit()
            
            # Process websites asynchronously
            asyncio.create_task(self._process_websites_async(
                upload_id=upload_id,
                websites_data=websites_data,
                user_id=user_id,
                enable_validation=enable_validation,
                auto_categorize=auto_categorize,
                default_rate_limit=default_rate_limit,
                default_max_pages=default_max_pages
            ))
            
            return WebsiteUploadResponse(
                upload_id=upload_id,
                status="processing",
                message="Website upload started successfully",
                total_websites=len(websites_data),
                processed_websites=0,
                failed_websites=0,
                created_at=upload_record.created_at
            )
            
        except Exception as e:
            logger.error(f"Error processing bulk upload: {str(e)}")
            # Update upload record with error
            if 'upload_record' in locals():
                upload_record.status = "failed"
                upload_record.error_message = str(e)
                self.db.commit()
            raise
    
    async def _process_websites_async(
        self,
        upload_id: str,
        websites_data: List[Dict[str, Any]],
        user_id: int,
        enable_validation: bool,
        auto_categorize: bool,
        default_rate_limit: int,
        default_max_pages: int
    ):
        """Process websites asynchronously in background."""
        
        upload_record = self.db.query(MemoryUpload).filter(
            MemoryUpload.upload_id == upload_id
        ).first()
        
        if not upload_record:
            logger.error(f"Upload record not found: {upload_id}")
            return
        
        processed_count = 0
        failed_count = 0
        error_details = []
        
        try:
            for idx, website_data in enumerate(websites_data):
                try:
                    # Validate website data
                    if enable_validation:
                        validation_errors = self._validate_website_data(website_data)
                        if validation_errors:
                            failed_count += 1
                            error_details.append({
                                "row": idx + 2,  # +2 for header and 0-based index
                                "errors": validation_errors
                            })
                            continue
                    
                    # Auto-categorize if enabled
                    if auto_categorize and not website_data.get('category'):
                        website_data['category'] = self._auto_categorize_website(
                            website_data['url']
                        )
                    
                    # Apply defaults
                    website_data.setdefault('rate_limit', default_rate_limit)
                    website_data.setdefault('max_pages', default_max_pages)
                    website_data.setdefault('scraping_enabled', True)
                    
                    # Create website record
                    website = ManagedWebsite(
                        user_id=user_id,
                        name=website_data['name'],
                        url=website_data['url'],
                        category=website_data['category'],
                        scraping_enabled=website_data.get('scraping_enabled', True),
                        rate_limit=website_data.get('rate_limit', default_rate_limit),
                        max_pages=website_data.get('max_pages', default_max_pages),
                        custom_headers=website_data.get('custom_headers', {}),
                        selectors=website_data.get('selectors', {}),
                        status="active"
                    )
                    
                    self.db.add(website)
                    processed_count += 1
                    
                    # Update progress every 10 websites
                    if processed_count % 10 == 0:
                        upload_record.processed_records = processed_count
                        upload_record.failed_records = failed_count
                        self.db.commit()
                    
                except Exception as e:
                    failed_count += 1
                    error_details.append({
                        "row": idx + 2,
                        "errors": [f"Processing error: {str(e)}"]
                    })
                    logger.error(f"Error processing website {idx}: {str(e)}")
            
            # Final update
            upload_record.processed_records = processed_count
            upload_record.failed_records = failed_count
            upload_record.status = "completed" if failed_count == 0 else "completed_with_errors"
            upload_record.error_details = error_details if error_details else None
            upload_record.completed_at = datetime.utcnow()
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error in async processing: {str(e)}")
            upload_record.status = "failed"
            upload_record.error_message = str(e)
            self.db.commit()
    
    def _parse_csv_content(self, csv_content: str) -> List[Dict[str, Any]]:
        """Parse CSV content and return list of website data."""
        
        websites_data = []
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        for row_idx, row in enumerate(csv_reader):
            # Skip empty rows
            if not any(row.values()):
                continue
            
            # Clean and process row data
            website_data = {}
            for key, value in row.items():
                if key and value:
                    clean_key = key.strip().lower().replace(' ', '_')
                    clean_value = value.strip()
                    
                    # Handle special fields
                    if clean_key == 'scraping_enabled':
                        website_data[clean_key] = clean_value.lower() in ['true', '1', 'yes', 'enabled']
                    elif clean_key in ['rate_limit', 'max_pages']:
                        try:
                            website_data[clean_key] = int(clean_value)
                        except ValueError:
                            website_data[clean_key] = clean_value
                    elif clean_key in ['custom_headers', 'selectors']:
                        # Try to parse JSON-like strings
                        try:
                            import json
                            website_data[clean_key] = json.loads(clean_value)
                        except:
                            website_data[clean_key] = {}
                    else:
                        website_data[clean_key] = clean_value
            
            if website_data:
                websites_data.append(website_data)
        
        return websites_data
    
    def _validate_website_data(self, website_data: Dict[str, Any]) -> List[str]:
        """Validate individual website data."""
        
        errors = []
        
        # Check required fields
        for field in self.required_fields:
            if field not in website_data or not website_data[field]:
                errors.append(f"Missing required field: {field}")
        
        # Validate URL format
        if 'url' in website_data:
            url = website_data['url']
            if not self._is_valid_url(url):
                errors.append(f"Invalid URL format: {url}")
        
        # Validate numeric fields
        for field in ['rate_limit', 'max_pages']:
            if field in website_data:
                try:
                    value = int(website_data[field])
                    if value <= 0:
                        errors.append(f"{field} must be a positive integer")
                except (ValueError, TypeError):
                    errors.append(f"{field} must be a valid integer")
        
        return errors
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
        except:
            return False
    
    def _auto_categorize_website(self, url: str) -> str:
        """Auto-categorize website based on URL patterns."""
        
        url_lower = url.lower()
        
        # Simple categorization rules
        if any(keyword in url_lower for keyword in ['job', 'career', 'employment', 'hiring']):
            return 'job_boards'
        elif any(keyword in url_lower for keyword in ['news', 'blog', 'article']):
            return 'news_media'
        elif any(keyword in url_lower for keyword in ['shop', 'store', 'buy', 'sell', 'commerce']):
            return 'ecommerce'
        elif any(keyword in url_lower for keyword in ['social', 'community', 'forum']):
            return 'social_media'
        elif any(keyword in url_lower for keyword in ['edu', 'university', 'school', 'learn']):
            return 'education'
        else:
            return 'general'
    
    async def get_upload_status(self, upload_id: str, user_id: int) -> Optional[WebsiteUploadStatus]:
        """Get upload status by ID."""
        
        upload_record = self.db.query(MemoryUpload).filter(
            and_(
                MemoryUpload.upload_id == upload_id,
                MemoryUpload.user_id == user_id
            )
        ).first()
        
        if not upload_record:
            return None
        
        progress_percentage = 0
        if upload_record.total_records > 0:
            progress_percentage = (upload_record.processed_records / upload_record.total_records) * 100
        
        return WebsiteUploadStatus(
            upload_id=upload_record.upload_id,
            status=upload_record.status,
            progress_percentage=progress_percentage,
            total_websites=upload_record.total_records,
            processed_websites=upload_record.processed_records,
            failed_websites=upload_record.failed_records,
            error_details=upload_record.error_details,
            created_at=upload_record.created_at,
            updated_at=upload_record.updated_at
        )
    
    async def get_upload_history(
        self, 
        user_id: int, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get upload history for user."""
        
        uploads = self.db.query(MemoryUpload).filter(
            and_(
                MemoryUpload.user_id == user_id,
                MemoryUpload.memory_type == "websites"
            )
        ).order_by(MemoryUpload.created_at.desc()).offset(offset).limit(limit).all()
        
        return [
            {
                "upload_id": upload.upload_id,
                "filename": upload.filename,
                "status": upload.status,
                "total_records": upload.total_records,
                "processed_records": upload.processed_records,
                "failed_records": upload.failed_records,
                "created_at": upload.created_at,
                "completed_at": upload.completed_at
            }
            for upload in uploads
        ]
    
    async def cancel_upload(self, upload_id: str, user_id: int) -> bool:
        """Cancel an ongoing upload."""
        
        upload_record = self.db.query(MemoryUpload).filter(
            and_(
                MemoryUpload.upload_id == upload_id,
                MemoryUpload.user_id == user_id,
                MemoryUpload.status == "processing"
            )
        ).first()
        
        if not upload_record:
            return False
        
        upload_record.status = "cancelled"
        upload_record.completed_at = datetime.utcnow()
        self.db.commit()
        
        return True
    
    async def validate_website_csv(self, csv_content: str) -> WebsiteValidationResult:
        """Validate website CSV without processing."""
        
        try:
            websites_data = self._parse_csv_content(csv_content)
            
            total_rows = len(websites_data)
            valid_rows = 0
            invalid_rows = 0
            errors = []
            warnings = []
            
            for idx, website_data in enumerate(websites_data):
                row_errors = self._validate_website_data(website_data)
                
                if row_errors:
                    invalid_rows += 1
                    errors.append({
                        "row": idx + 2,
                        "errors": row_errors
                    })
                else:
                    valid_rows += 1
                
                # Check for warnings
                row_warnings = self._check_website_warnings(website_data)
                if row_warnings:
                    warnings.append({
                        "row": idx + 2,
                        "warnings": row_warnings
                    })
            
            return WebsiteValidationResult(
                is_valid=invalid_rows == 0,
                total_rows=total_rows,
                valid_rows=valid_rows,
                invalid_rows=invalid_rows,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Error validating CSV: {str(e)}")
            return WebsiteValidationResult(
                is_valid=False,
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                errors=[{"row": 0, "errors": [f"CSV parsing error: {str(e)}"]}],
                warnings=[]
            )
    
    def _check_website_warnings(self, website_data: Dict[str, Any]) -> List[str]:
        """Check for potential warnings in website data."""
        
        warnings = []
        
        # Check for missing optional but recommended fields
        if not website_data.get('category'):
            warnings.append("Category not specified - will be auto-categorized")
        
        # Check for high rate limits
        rate_limit = website_data.get('rate_limit', 5)
        if isinstance(rate_limit, int) and rate_limit > 10:
            warnings.append(f"High rate limit ({rate_limit}s) may slow down scraping")
        
        # Check for very high max_pages
        max_pages = website_data.get('max_pages', 100)
        if isinstance(max_pages, int) and max_pages > 1000:
            warnings.append(f"High max_pages ({max_pages}) may take very long to scrape")
        
        return warnings
    
    async def get_website_stats(self, user_id: int) -> Dict[str, Any]:
        """Get website management statistics."""
        
        total_websites = self.db.query(ManagedWebsite).filter(
            ManagedWebsite.user_id == user_id
        ).count()
        
        active_websites = self.db.query(ManagedWebsite).filter(
            and_(
                ManagedWebsite.user_id == user_id,
                ManagedWebsite.status == "active"
            )
        ).count()
        
        enabled_websites = self.db.query(ManagedWebsite).filter(
            and_(
                ManagedWebsite.user_id == user_id,
                ManagedWebsite.scraping_enabled == True
            )
        ).count()
        
        # Get category distribution
        # from sqlalchemy import func  # TODO: MongoDB Migration - Remove SQLAlchemy dependency
        category_stats = self.db.query(
            ManagedWebsite.category,
            func.count(ManagedWebsite.id).label('count')
        ).filter(
            ManagedWebsite.user_id == user_id
        ).group_by(ManagedWebsite.category).all()
        
        return {
            "total_websites": total_websites,
            "active_websites": active_websites,
            "enabled_websites": enabled_websites,
            "category_distribution": {
                category: count for category, count in category_stats
            }
        }
    
    async def list_websites(
        self,
        user_id: int,
        category: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List managed websites with filtering."""
        
        query = self.db.query(ManagedWebsite).filter(
            ManagedWebsite.user_id == user_id
        )
        
        if category:
            query = query.filter(ManagedWebsite.category == category)
        
        if status:
            query = query.filter(ManagedWebsite.status == status)
        
        websites = query.order_by(
            ManagedWebsite.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        return [
            {
                "id": website.id,
                "name": website.name,
                "url": website.url,
                "category": website.category,
                "status": website.status,
                "scraping_enabled": website.scraping_enabled,
                "rate_limit": website.rate_limit,
                "max_pages": website.max_pages,
                "created_at": website.created_at,
                "updated_at": website.updated_at
            }
            for website in websites
        ]
    
    async def update_website(
        self,
        website_id: int,
        user_id: int,
        website_config: WebsiteConfig
    ) -> Optional[Dict[str, Any]]:
        """Update a managed website."""
        
        website = self.db.query(ManagedWebsite).filter(
            and_(
                ManagedWebsite.id == website_id,
                ManagedWebsite.user_id == user_id
            )
        ).first()
        
        if not website:
            return None
        
        # Update fields
        website.name = website_config.name
        website.url = website_config.url
        website.category = website_config.category
        website.scraping_enabled = website_config.scraping_enabled
        website.rate_limit = website_config.rate_limit
        website.max_pages = website_config.max_pages
        website.custom_headers = website_config.custom_headers
        website.selectors = website_config.selectors
        website.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        return {
            "id": website.id,
            "name": website.name,
            "url": website.url,
            "category": website.category,
            "status": website.status,
            "scraping_enabled": website.scraping_enabled,
            "rate_limit": website.rate_limit,
            "max_pages": website.max_pages,
            "updated_at": website.updated_at
        }
    
    async def delete_website(self, website_id: int, user_id: int) -> bool:
        """Delete a managed website."""
        
        website = self.db.query(ManagedWebsite).filter(
            and_(
                ManagedWebsite.id == website_id,
                ManagedWebsite.user_id == user_id
            )
        ).first()
        
        if not website:
            return False
        
        self.db.delete(website)
        self.db.commit()
        
        return True