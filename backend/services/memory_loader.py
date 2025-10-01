import pandas as pd
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Callable
from datetime import datetime
from pathlib import Path
import logging
from dataclasses import dataclass

# from backend.database.models import MemoryUpload  # TODO: Migrate MemoryUpload to MongoDB models
# from backend.models.mongodb_models import MemoryUpload  # TODO: Create MemoryUpload MongoDB model
# from backend.core.enums import MemoryUploadStatus  # No longer needed, using string values
from backend.database import get_db_session
# from sqlalchemy.orm import Session  # Using MongoDB instead

logger = logging.getLogger(__name__)

@dataclass
class MemoryContext:
    """Represents processed memory context from CSV"""
    website_patterns: Dict[str, Any]
    extraction_rules: Dict[str, List[str]]
    success_indicators: List[str]
    failure_patterns: List[str]
    custom_selectors: Dict[str, str]
    metadata: Dict[str, Any]
    total_records: int
    processed_records: int
    validation_errors: List[str]

@dataclass
class ProcessingProgress:
    """Track memory processing progress"""
    total_rows: int
    processed_rows: int
    successful_rows: int
    failed_rows: int
    current_step: str
    errors: List[str]
    warnings: List[str]
    
    @property
    def progress_percentage(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return (self.processed_rows / self.total_rows) * 100

class MemoryLoader:
    """Service for loading and processing memory CSV files"""
    
    def __init__(self):
        self.required_columns = [
            'website_url',
            'target_data_type',
            'successful_selectors',
            'extraction_context'
        ]
        self.optional_columns = [
            'failure_patterns',
            'success_indicators',
            'custom_headers',
            'notes',
            'priority',
            'tags'
        ]
        self.processing_callbacks = {}
    
    async def validate_csv_format(self, file_path: str) -> Tuple[bool, List[str]]:
        """Validate CSV file format and structure"""
        errors = []
        
        try:
            # Read CSV file
            df = pd.read_csv(file_path)
            
            # Check if file is empty
            if df.empty:
                errors.append("CSV file is empty")
                return False, errors
            
            # Check required columns
            missing_columns = [col for col in self.required_columns if col not in df.columns]
            if missing_columns:
                errors.append(f"Missing required columns: {', '.join(missing_columns)}")
            
            # Check for duplicate URLs
            if df['website_url'].duplicated().any():
                duplicate_count = df['website_url'].duplicated().sum()
                errors.append(f"Found {duplicate_count} duplicate website URLs")
            
            # Validate URL format
            invalid_urls = []
            for idx, url in enumerate(df['website_url']):
                if pd.isna(url) or not self._is_valid_url(str(url)):
                    invalid_urls.append(f"Row {idx + 2}: Invalid URL format")
            
            if invalid_urls:
                errors.extend(invalid_urls[:10])  # Limit to first 10 errors
                if len(invalid_urls) > 10:
                    errors.append(f"... and {len(invalid_urls) - 10} more URL format errors")
            
            # Check data types
            required_data_types = ['text', 'links', 'images', 'tables', 'forms', 'custom']
            invalid_types = []
            for idx, data_type in enumerate(df['target_data_type']):
                if pd.notna(data_type) and str(data_type).lower() not in required_data_types:
                    invalid_types.append(f"Row {idx + 2}: Invalid data type '{data_type}'")
            
            if invalid_types:
                errors.extend(invalid_types[:5])  # Limit to first 5 errors
                if len(invalid_types) > 5:
                    errors.append(f"... and {len(invalid_types) - 5} more data type errors")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"Error reading CSV file: {str(e)}")
            return False, errors
    
    def _is_valid_url(self, url: str) -> bool:
        """Basic URL validation"""
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+'  # domain...
            r'(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # host...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return bool(url_pattern.match(url))
    
    async def process_memory_upload(
        self, 
        upload_id: str, 
        file_path: str,
        progress_callback: Optional[Callable] = None
    ) -> MemoryContext:
        """Process uploaded memory CSV file"""
        logger.info(f"Starting memory processing for upload {upload_id}")
        
        # Initialize progress tracking
        progress = ProcessingProgress(
            total_rows=0,
            processed_rows=0,
            successful_rows=0,
            failed_rows=0,
            current_step="Initializing",
            errors=[],
            warnings=[]
        )
        
        try:
            # Update upload status
            await self._update_upload_status(upload_id, "PROCESSING")
            
            # Step 1: Validate file format
            progress.current_step = "Validating file format"
            if progress_callback:
                await progress_callback(progress)
            
            is_valid, validation_errors = await self.validate_csv_format(file_path)
            if not is_valid:
                progress.errors.extend(validation_errors)
                await self._update_upload_status(upload_id, "FAILED", validation_errors)
                raise ValueError(f"CSV validation failed: {'; '.join(validation_errors)}")
            
            # Step 2: Load and parse CSV
            progress.current_step = "Loading CSV data"
            df = pd.read_csv(file_path)
            progress.total_rows = len(df)
            
            if progress_callback:
                await progress_callback(progress)
            
            # Step 3: Process each row
            progress.current_step = "Processing memory records"
            
            website_patterns = {}
            extraction_rules = {}
            success_indicators = []
            failure_patterns = []
            custom_selectors = {}
            
            for idx, row in df.iterrows():
                try:
                    # Process individual row
                    await self._process_memory_row(row, website_patterns, extraction_rules, 
                                                 success_indicators, failure_patterns, custom_selectors)
                    progress.successful_rows += 1
                    
                except Exception as e:
                    progress.failed_rows += 1
                    progress.errors.append(f"Row {idx + 2}: {str(e)}")
                    logger.warning(f"Failed to process row {idx + 2}: {str(e)}")
                
                progress.processed_rows += 1
                
                # Update progress every 10 rows
                if progress.processed_rows % 10 == 0 and progress_callback:
                    await progress_callback(progress)
                
                # Small delay to prevent blocking
                if progress.processed_rows % 100 == 0:
                    await asyncio.sleep(0.01)
            
            # Step 4: Finalize processing
            progress.current_step = "Finalizing memory context"
            if progress_callback:
                await progress_callback(progress)
            
            # Create memory context
            memory_context = MemoryContext(
                website_patterns=website_patterns,
                extraction_rules=extraction_rules,
                success_indicators=list(set(success_indicators)),
                failure_patterns=list(set(failure_patterns)),
                custom_selectors=custom_selectors,
                metadata={
                    'total_websites': len(website_patterns),
                    'processing_date': datetime.utcnow().isoformat(),
                    'file_name': Path(file_path).name,
                    'success_rate': (progress.successful_rows / progress.total_rows) * 100 if progress.total_rows > 0 else 0
                },
                total_records=progress.total_rows,
                processed_records=progress.successful_rows,
                validation_errors=progress.errors
            )
            
            # Update upload status to completed
            await self._update_upload_status(
                upload_id, 
                "COMPLETED",
                memory_context=memory_context
            )
            
            logger.info(f"Memory processing completed for upload {upload_id}. "
                       f"Processed {progress.successful_rows}/{progress.total_rows} records")
            
            return memory_context
            
        except Exception as e:
            logger.error(f"Memory processing failed for upload {upload_id}: {str(e)}")
            await self._update_upload_status(upload_id, "FAILED", [str(e)])
            raise
    
    async def _process_memory_row(
        self, 
        row: pd.Series, 
        website_patterns: Dict,
        extraction_rules: Dict,
        success_indicators: List,
        failure_patterns: List,
        custom_selectors: Dict
    ):
        """Process individual memory row"""
        url = str(row['website_url']).strip()
        data_type = str(row['target_data_type']).lower().strip()
        selectors = str(row['successful_selectors']).strip()
        context = str(row['extraction_context']).strip()
        
        # Extract domain for pattern grouping
        domain = self._extract_domain(url)
        
        # Store website patterns
        if domain not in website_patterns:
            website_patterns[domain] = {
                'urls': [],
                'data_types': set(),
                'selectors': {},
                'context': [],
                'metadata': {}
            }
        
        website_patterns[domain]['urls'].append(url)
        website_patterns[domain]['data_types'].add(data_type)
        website_patterns[domain]['context'].append(context)
        
        # Process selectors
        if selectors and selectors != 'nan':
            selector_list = [s.strip() for s in selectors.split(',') if s.strip()]
            if data_type not in website_patterns[domain]['selectors']:
                website_patterns[domain]['selectors'][data_type] = []
            website_patterns[domain]['selectors'][data_type].extend(selector_list)
            
            # Add to custom selectors
            for selector in selector_list:
                custom_selectors[f"{domain}_{data_type}_{len(custom_selectors)}"] = selector
        
        # Store extraction rules
        if data_type not in extraction_rules:
            extraction_rules[data_type] = []
        extraction_rules[data_type].append({
            'domain': domain,
            'context': context,
            'selectors': selectors.split(',') if selectors and selectors != 'nan' else []
        })
        
        # Process optional fields
        if 'success_indicators' in row and pd.notna(row['success_indicators']):
            indicators = [s.strip() for s in str(row['success_indicators']).split(',')]
            success_indicators.extend(indicators)
        
        if 'failure_patterns' in row and pd.notna(row['failure_patterns']):
            patterns = [s.strip() for s in str(row['failure_patterns']).split(',')]
            failure_patterns.extend(patterns)
        
        # Add metadata
        if 'priority' in row and pd.notna(row['priority']):
            website_patterns[domain]['metadata']['priority'] = row['priority']
        
        if 'tags' in row and pd.notna(row['tags']):
            tags = [s.strip() for s in str(row['tags']).split(',')]
            website_patterns[domain]['metadata']['tags'] = tags
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except:
            return url.lower()
    
    async def _update_upload_status(
        self, 
        upload_id: str, 
        status: str, 
        errors: Optional[List[str]] = None,
        memory_context: Optional[MemoryContext] = None
    ):
        """Update memory upload status in database"""
        try:
            db = next(get_db_session())
            upload = db.query(MemoryUpload).filter(MemoryUpload.id == upload_id).first()
            
            if upload:
                upload.upload_status = status
                # Note: updated_at field doesn't exist in current schema
                
                if errors:
                    upload.error_log = json.dumps(errors)
                
                if memory_context:
                    upload.processed_data = {
                        'website_patterns': memory_context.website_patterns,
                        'extraction_rules': memory_context.extraction_rules,
                        'success_indicators': memory_context.success_indicators,
                        'failure_patterns': memory_context.failure_patterns,
                        'custom_selectors': memory_context.custom_selectors,
                        'metadata': memory_context.metadata
                    }
                    upload.total_records = memory_context.total_records
                    upload.processed_records = memory_context.processed_records
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Failed to update upload status: {str(e)}")
    
    async def get_memory_context(self, upload_id: str) -> Optional[MemoryContext]:
        """Retrieve processed memory context"""
        try:
            db = next(get_db_session())
            upload = db.query(MemoryUpload).filter(MemoryUpload.id == upload_id).first()
            
            if upload and upload.processed_data:
                data = upload.processed_data
                return MemoryContext(
                    website_patterns=data.get('website_patterns', {}),
                    extraction_rules=data.get('extraction_rules', {}),
                    success_indicators=data.get('success_indicators', []),
                    failure_patterns=data.get('failure_patterns', []),
                    custom_selectors=data.get('custom_selectors', {}),
                    metadata=data.get('metadata', {}),
                    total_records=upload.total_records or 0,
                    processed_records=upload.processed_records or 0,
                    validation_errors=[]
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get memory context: {str(e)}")
            return None
    
    async def generate_csv_template(self) -> str:
        """Generate CSV template with sample data"""
        template_data = {
            'website_url': [
                'https://example.com/products',
                'https://sample-site.com/articles',
                'https://demo.com/listings'
            ],
            'target_data_type': [
                'text',
                'links',
                'images'
            ],
            'successful_selectors': [
                '.product-title, .product-price',
                'a.article-link',
                'img.listing-image'
            ],
            'extraction_context': [
                'E-commerce product information',
                'Blog article links',
                'Property listing images'
            ],
            'success_indicators': [
                'price found, title not empty',
                'valid article URL',
                'image loaded successfully'
            ],
            'failure_patterns': [
                'out of stock, price missing',
                'broken link, 404 error',
                'image not found'
            ],
            'priority': [1, 2, 1],
            'tags': [
                'ecommerce, products',
                'content, articles',
                'real-estate, images'
            ],
            'notes': [
                'Focus on product pages',
                'Check for pagination',
                'Handle lazy loading'
            ]
        }
        
        df = pd.DataFrame(template_data)
        return df.to_csv(index=False)
    
    def register_progress_callback(self, upload_id: str, callback: Callable):
        """Register callback for progress updates"""
        self.processing_callbacks[upload_id] = callback
    
    def unregister_progress_callback(self, upload_id: str):
        """Unregister progress callback"""
        if upload_id in self.processing_callbacks:
            del self.processing_callbacks[upload_id]