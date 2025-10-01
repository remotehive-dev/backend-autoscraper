import csv
import io
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse

import aiohttp
import pandas as pd
# from sqlalchemy.orm import Session  # Using MongoDB instead
# from sqlalchemy import select, and_  # Using MongoDB instead

# TODO: Migrate ScraperMemory and CSVImport to MongoDB or handle differently
# from backend.database.models import ScraperConfig, ScraperMemory, CSVImport
from backend.database.mongodb_models import ScraperConfig
# ScraperMemory and CSVImport need to be migrated to MongoDB
from backend.database import get_db_session
from backend.core.config import settings

logger = logging.getLogger(__name__)

class JobBoardConfigService:
    """Service for handling job board CSV configurations and imports."""
    
    # Required CSV columns
    REQUIRED_COLUMNS = ['name', 'url']
    
    # Optional CSV columns with defaults
    OPTIONAL_COLUMNS = {
        'search_url': '',
        'region': '',
        'selectors': '{}',
        'headers': '{}',
        'max_pages': '10',
        'delay_seconds': '2',
        'rate_limit': '60',
        'enabled': 'true',
        'description': '',
        'category': 'general'
    }
    
    # All valid columns
    ALL_COLUMNS = REQUIRED_COLUMNS + list(OPTIONAL_COLUMNS.keys())
    
    def __init__(self, db=None):  # db: Session - Using MongoDB instead
        self.db = db
    
    async def validate_csv_format(self, file_content: bytes) -> Tuple[bool, str, Optional[pd.DataFrame]]:
        """Validate CSV format and structure for job board configurations."""
        try:
            # Read CSV content
            csv_string = file_content.decode('utf-8')
            df = pd.read_csv(io.StringIO(csv_string))
            
            if df.empty:
                return False, "CSV file is empty", None
            
            # Check required columns
            missing_columns = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
            if missing_columns:
                return False, f"Missing required columns: {', '.join(missing_columns)}", None
            
            # Check for unknown columns
            unknown_columns = [col for col in df.columns if col not in self.ALL_COLUMNS]
            if unknown_columns:
                logger.warning(f"Unknown columns found: {', '.join(unknown_columns)}")
            
            # Validate data types and formats
            validation_errors = []
            
            for index, row in df.iterrows():
                row_errors = self._validate_row(row, index + 1)
                validation_errors.extend(row_errors)
            
            if validation_errors:
                return False, "\n".join(validation_errors), None
            
            return True, "CSV format is valid", df
            
        except UnicodeDecodeError:
            return False, "Invalid file encoding. Please use UTF-8", None
        except pd.errors.EmptyDataError:
            return False, "CSV file is empty or corrupted", None
        except Exception as e:
            logger.error(f"CSV validation error: {str(e)}")
            return False, f"CSV validation failed: {str(e)}", None
    
    def _validate_row(self, row: pd.Series, row_number: int) -> List[str]:
        """Validate individual CSV row data."""
        errors = []
        
        # Check required fields are not empty
        for col in self.REQUIRED_COLUMNS:
            if pd.isna(row.get(col)) or str(row.get(col)).strip() == '':
                errors.append(f"Row {row_number}: '{col}' is required and cannot be empty")
        
        # Validate URL formats
        for url_col in ['url', 'search_url']:
            if url_col in row and not pd.isna(row[url_col]):
                url_value = str(row[url_col]).strip()
                if url_value and not self._is_valid_url(url_value):
                    errors.append(f"Row {row_number}: '{url_col}' is not a valid URL")
        
        # Validate JSON fields
        for json_col in ['selectors', 'headers']:
            if json_col in row and not pd.isna(row[json_col]):
                json_value = str(row[json_col]).strip()
                if json_value and not self._is_valid_json(json_value):
                    errors.append(f"Row {row_number}: '{json_col}' must be valid JSON")
        
        # Validate numeric fields
        for num_col in ['max_pages', 'delay_seconds', 'rate_limit']:
            if num_col in row and not pd.isna(row[num_col]):
                try:
                    value = float(row[num_col])
                    if value < 0:
                        errors.append(f"Row {row_number}: '{num_col}' must be a positive number")
                except (ValueError, TypeError):
                    errors.append(f"Row {row_number}: '{num_col}' must be a valid number")
        
        # Validate boolean fields
        if 'enabled' in row and not pd.isna(row['enabled']):
            enabled_value = str(row['enabled']).lower().strip()
            if enabled_value not in ['true', 'false', '1', '0', 'yes', 'no']:
                errors.append(f"Row {row_number}: 'enabled' must be true/false or yes/no")
        
        return errors
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _is_valid_json(self, json_str: str) -> bool:
        """Check if string is valid JSON."""
        try:
            json.loads(json_str)
            return True
        except json.JSONDecodeError:
            return False
    
    async def test_website_accessibility(self, url: str, timeout: int = 10) -> Tuple[bool, str]:
        """Test if a website is accessible."""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        return True, "Website is accessible"
                    else:
                        return False, f"Website returned status code: {response.status}"
        except aiohttp.ClientError as e:
            return False, f"Connection error: {str(e)}"
        except Exception as e:
            return False, f"Accessibility test failed: {str(e)}"
    
    async def process_csv_import(self, 
                               upload_id: str, 
                               df: pd.DataFrame, 
                               test_accessibility: bool = True) -> Dict[str, Any]:
        """Process job board CSV import and create scraper configurations."""
        
        results = {
            'upload_id': upload_id,
            'total_rows': len(df),
            'processed': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': [],
            'warnings': []
        }
        
        try:
            # TODO: Create CSV import record in MongoDB when model is migrated
            # csv_import = CSVImport(
            #     id=upload_id,
            #     filename=f"job_boards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            #     import_type='job_boards',
            #     status='processing',
            #     total_rows=len(df),
            #     processed_rows=0,
            #     created_rows=0,
            #     error_rows=0,
            #     started_at=datetime.utcnow()
            # )
            # self.db.add(csv_import)
            # self.db.commit()
            
            for index, row in df.iterrows():
                try:
                    # Process each row
                    row_result = self._process_job_board_row(
                        row, index + 1, test_accessibility
                    )
                    
                    results['processed'] += 1
                    
                    if row_result['status'] == 'created':
                        results['created'] += 1
                    elif row_result['status'] == 'updated':
                        results['updated'] += 1
                    elif row_result['status'] == 'skipped':
                        results['skipped'] += 1
                    
                    if row_result.get('warnings'):
                        results['warnings'].extend(row_result['warnings'])
                    
                except Exception as e:
                    error_msg = f"Row {index + 1}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(f"Error processing row {index + 1}: {str(e)}")
            
            # Update CSV import record
            csv_import.status = 'completed' if not results['errors'] else 'completed_with_errors'
            csv_import.processed_rows = results['processed']
            csv_import.created_rows = results['created']
            csv_import.error_rows = len(results['errors'])
            csv_import.completed_at = datetime.utcnow()
            csv_import.result_summary = json.dumps(results)
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"CSV import failed: {str(e)}")
            results['errors'].append(f"Import failed: {str(e)}")
            
            # Update CSV import record with error
            if 'csv_import' in locals():
                csv_import.status = 'failed'
                csv_import.error_message = str(e)
                csv_import.completed_at = datetime.utcnow()
                self.db.commit()
        
        return results
    
    async def _process_job_board_row(self, 
                                   row: pd.Series, 
                                   row_number: int, 
                                   test_accessibility: bool) -> Dict[str, Any]:
        """Process individual job board row and create/update scraper config."""
        
        result = {
            'row_number': row_number,
            'status': 'skipped',
            'warnings': []
        }
        
        # Extract and clean data
        name = str(row['name']).strip()
        url = str(row['url']).strip()
        search_url = str(row.get('search_url', '')).strip() if not pd.isna(row.get('search_url')) else ''
        region = str(row.get('region', '')).strip() if not pd.isna(row.get('region')) else ''
        
        # Test website accessibility if requested
        if test_accessibility:
            try:
                import asyncio
                accessible, access_msg = asyncio.run(self.test_website_accessibility(url))
                if not accessible:
                    result['warnings'].append(f"Row {row_number}: {access_msg}")
            except Exception as e:
                result['warnings'].append(f"Row {row_number}: Accessibility test failed: {str(e)}")
        
        # Check if scraper config already exists
        existing_config = self.db.execute(
            select(ScraperConfig).where(ScraperConfig.scraper_name == name)
        )
        existing_config = existing_config.scalar_one_or_none()
        
        # Prepare configuration data
        config_data = self._prepare_config_data(row)
        
        if existing_config:
            # Update existing configuration
            for key, value in config_data.items():
                setattr(existing_config, key, value)
            existing_config.updated_at = datetime.utcnow()
            result['status'] = 'updated'
        else:
            # Create new configuration
            new_config = ScraperConfig(
                id=str(uuid.uuid4()),
                scraper_name=name,
                **config_data,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(new_config)
            result['status'] = 'created'
            
            # Create scraper memory entry
            memory_entry = ScraperMemory(
                id=str(uuid.uuid4()),
                scraper_config_id=new_config.id,
                website_url=url,
                last_scraped_at=None,
                total_jobs_found=0,
                success_rate=0.0,
                average_response_time=0.0,
                last_error=None,
                metadata=json.dumps({
                    'imported_from_csv': True,
                    'import_date': datetime.utcnow().isoformat(),
                    'search_url': search_url,
                    'region': region
                }),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self.db.add(memory_entry)
        
        self.db.commit()
        return result
    
    def _prepare_config_data(self, row: pd.Series) -> Dict[str, Any]:
        """Prepare scraper configuration data from CSV row."""
        # Handle optional search_url and region
        search_url = str(row.get('search_url', '')).strip() if not pd.isna(row.get('search_url')) else ''
        region = str(row.get('region', '')).strip() if not pd.isna(row.get('region')) else ''
        
        # Use region in description if no description provided
        description = str(row.get('description', '')).strip()
        if not description and region:
            description = f"Job board from {region}"
        
        config_data = {
            'url': str(row['url']).strip(),
            'search_url': search_url,
            'enabled': self._parse_boolean(row.get('enabled', 'true')),
            'max_pages': int(float(row.get('max_pages', 10))),
            'delay_seconds': float(row.get('delay_seconds', 2)),
            'rate_limit': int(float(row.get('rate_limit', 60))),
            'description': description,
            'category': str(row.get('category', 'general')).strip()
        }
        
        # Parse JSON fields
        selectors_str = str(row.get('selectors', '{}')).strip()
        if selectors_str and selectors_str != 'nan':
            try:
                config_data['selectors'] = json.loads(selectors_str)
            except json.JSONDecodeError:
                config_data['selectors'] = {}
        else:
            config_data['selectors'] = {}
        
        headers_str = str(row.get('headers', '{}')).strip()
        if headers_str and headers_str != 'nan':
            try:
                config_data['headers'] = json.loads(headers_str)
            except json.JSONDecodeError:
                config_data['headers'] = {}
        else:
            config_data['headers'] = {}
        
        return config_data
    
    def _parse_boolean(self, value: Any) -> bool:
        """Parse boolean value from various formats."""
        if pd.isna(value):
            return True
        
        str_value = str(value).lower().strip()
        return str_value in ['true', '1', 'yes', 'on', 'enabled']
    
    def generate_csv_template(self) -> str:
        """Generate CSV template for job board configurations."""
        
        # Sample data for template - matching the current job_boards.csv format
        sample_data = [
            {
                'name': 'RemoteOK',
                'url': 'https://remoteok.io',
                'region': 'Worldwide',
                'search_url': 'https://remoteok.io/remote-jobs',
                'selectors': '{"job_title": ".job-title", "company": ".company", "location": ".location"}',
                'headers': '{"User-Agent": "Mozilla/5.0 (compatible; RemoteHive/1.0)"}',
                'max_pages': '5',
                'delay_seconds': '2',
                'rate_limit': '60',
                'enabled': 'true',
                'description': 'Remote job board for tech positions',
                'category': 'technology'
            },
            {
                'name': 'WeWorkRemotely',
                'url': 'https://weworkremotely.com',
                'region': 'North America',
                'search_url': 'https://weworkremotely.com/remote-jobs',
                'selectors': '{}',
                'headers': '{}',
                'max_pages': '10',
                'delay_seconds': '3',
                'rate_limit': '30',
                'enabled': 'true',
                'description': 'Popular remote work job board',
                'category': 'general'
            },
            {
                'name': 'TechJobs',
                'url': 'https://techjobs.com',
                'region': 'Europe',
                'search_url': '',
                'selectors': '{}',
                'headers': '{}',
                'max_pages': '10',
                'delay_seconds': '2',
                'rate_limit': '60',
                'enabled': 'true',
                'description': '',
                'category': 'general'
            }
        ]
        
        # Create CSV string
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=self.ALL_COLUMNS)
        writer.writeheader()
        writer.writerows(sample_data)
        
        return output.getvalue()
    
    async def get_import_status(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Get status of job board CSV import."""
        
        # TODO: Implement MongoDB query when CSVImport model is migrated
        # csv_import = self.db.execute(
        #     select(CSVImport).where(
        #         and_(
        #             CSVImport.id == upload_id,
        #             CSVImport.import_type == 'job_boards'
        #         )
        #     )
        # )
        # csv_import = csv_import.scalar_one_or_none()
        
        # if not csv_import:
        #     return None
        
        # TODO: Return actual status from MongoDB
        status_data = {
            'upload_id': upload_id,
            'filename': f"job_boards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            'status': 'processing',
            'total_rows': 0,
            'processed_rows': 0,
            'created_rows': 0,
            'error_rows': 0,
            'started_at': datetime.utcnow().isoformat(),
            'completed_at': None,
            'error_message': None
        }
        
        # TODO: Parse result summary from MongoDB when available
        # if csv_import.result_summary:
        #     try:
        #         result_summary = json.loads(csv_import.result_summary)
        #         status_data.update(result_summary)
        #     except json.JSONDecodeError:
        #         pass
        
        return status_data