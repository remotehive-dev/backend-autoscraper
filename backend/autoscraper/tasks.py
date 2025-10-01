from celery import current_app as celery_app
from backend.database.database import get_database_manager
# from backend.database.models import JobPost
from backend.models.mongodb_models import JobPost
# from backend.database.models import (
#     JobBoard, ScheduleConfig, AutoScrapeScrapeJob as ScrapeJob, AutoScrapeScrapeRun as ScrapeRun, 
#     AutoScrapeRawJob as RawJob, AutoScrapeNormalizedJob as NormalizedJob, 
#     AutoScrapeEngineState as EngineState, ScrapeJobStatus, ScrapeJobMode, EngineStatus
# )
# Note: These autoscraper models need to be implemented in MongoDB or use the autoscraper service
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any, Optional
# # from sqlalchemy import and_, or_  # Using MongoDB instead  # Using MongoDB instead
import requests
import json
import feedparser
import uuid
from bs4 import BeautifulSoup
import hashlib
import time
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3, queue='autoscraper.default')
def run_scrape_job(self, job_id: str):
    """
    Main orchestrator task for running a scrape job
    
    Args:
        job_id (str): UUID of the scrape job to run
        
    Returns:
        dict: Job execution results and statistics
    """
    try:
        logger.info(f"Starting scrape job: {job_id}")
        
        # Note: This autoscraper service uses SQLite, not MongoDB
        # For now, we'll disable this functionality until proper migration
        logger.warning(f"Autoscraper task {job_id} disabled - requires SQLite database setup")
        return {
            'success': False,
            'job_id': job_id,
            'error': 'Autoscraper service requires SQLite database setup',
            'jobs_found': 0,
            'jobs_created': 0,
            'boards_processed': 0,
            'total_boards': 0
        }
        
        try:
            # Update engine state
            heartbeat.delay()
            
            # Autoscraper functionality disabled
            # job_boards = []
            job_boards = []
            
            total_boards = len(job_boards)
            processed_boards = 0
            total_jobs_found = 0
            total_jobs_created = 0
            
            for board in job_boards:
                    try:
                        if board.board_type.value == 'rss':
                            # Process RSS feeds
                            result = fetch_rss_entries.delay(board.id, job_id, run_id)
                            board_result = result.get(timeout=300)  # 5 minute timeout
                        else:
                            # Process HTML scraping
                            result = html_scrape.delay(board.id, job_id, run_id)
                            board_result = result.get(timeout=600)  # 10 minute timeout
                        
                        total_jobs_found += board_result.get('jobs_found', 0)
                        total_jobs_created += board_result.get('jobs_created', 0)
                        processed_boards += 1
                        
                        logger.info(f"Processed board {board.name}: {board_result.get('jobs_found', 0)} jobs found")
                        
                    except Exception as e:
                        logger.error(f"Failed to process board {board.name}: {e}")
                        continue
            
            # Autoscraper status update disabled
            logger.info(f"Autoscraper job {job_id} would be completed here")
            
            logger.info(f"Scrape job {job_id} completed. Found {total_jobs_found} jobs, created {total_jobs_created}")
            
            return {
                'success': True,
                'job_id': job_id,
                'run_id': run_id,
                'jobs_found': total_jobs_found,
                'jobs_created': total_jobs_created,
                'boards_processed': processed_boards,
                'total_boards': total_boards
            }
            
        except Exception as e:
            # Autoscraper error handling disabled
            logger.error(f"Autoscraper job {job_id} would be marked as failed here: {e}")
            raise e
            
    except Exception as exc:
        logger.error(f"Scrape job {job_id} failed: {exc}")
        raise self.retry(exc=exc, countdown=300, max_retries=3)

@celery_app.task(bind=True, max_retries=3, queue='autoscraper.default')
def fetch_rss_entries(self, board_id: str, job_id: str, run_id: str):
    """
    Fetch and process RSS feed entries from a job board
    
    Args:
        board_id (str): UUID of the job board
        job_id (str): UUID of the scrape job
        run_id (str): UUID of the scrape run
        
    Returns:
        dict: Processing results
    """
    try:
        logger.info(f"Fetching RSS entries for board {board_id}")
        
        # Autoscraper RSS functionality disabled
        logger.warning(f"RSS fetch for board {board_id} disabled - requires SQLite database setup")
        return {
            'success': False,
            'board_id': board_id,
            'error': 'Autoscraper RSS service requires SQLite database setup',
            'jobs_found': 0,
            'jobs_created': 0
        }
        
        # Fetch RSS feed
        try:
            response = requests.get(board.rss_url, timeout=30)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            if feed.bozo:
                logger.warning(f"RSS feed parsing warning for {board.name}: {feed.bozo_exception}")
            
            entries = feed.entries
            logger.info(f"Found {len(entries)} RSS entries for {board.name}")
            
        except Exception as e:
            logger.error(f"Failed to fetch RSS feed for {board.name}: {e}")
            raise e
        
        jobs_found = 0
        jobs_created = 0
        
        for entry in entries:
            try:
                # Create raw job entry
                raw_data = {
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'description': entry.get('description', ''),
                    'published': entry.get('published', ''),
                    'author': entry.get('author', ''),
                    'tags': [tag.get('term', '') for tag in entry.get('tags', [])],
                    'source': board.name,
                    'board_id': board_id
                }
                
                # Generate content hash for deduplication
                content_hash = hashlib.md5(
                    f"{raw_data['title']}{raw_data['link']}".encode('utf-8')
                ).hexdigest()
                
                # Duplicate check disabled
                existing = None
                if existing:
                    logger.debug(f"Duplicate job found, skipping: {raw_data['title']}")
                    continue
                
                # Persist raw item
                persist_result = persist_raw_item.delay(
                    raw_data, content_hash, job_id, run_id, board_id
                )
                raw_job_id = persist_result.get(timeout=60)
                
                if raw_job_id:
                    jobs_found += 1
                    
                    # Trigger normalization
                    normalize_result = normalize_raw_job.delay(raw_job_id)
                    normalized = normalize_result.get(timeout=120)
                    
                    if normalized and normalized.get('created_job_post'):
                        jobs_created += 1
                
            except Exception as e:
                logger.error(f"Failed to process RSS entry: {e}")
                continue
        
        logger.info(f"RSS processing completed for {board.name}: {jobs_found} found, {jobs_created} created")
        
        return {
            'success': True,
            'board_id': board_id,
            'board_name': board.name,
            'jobs_found': jobs_found,
            'jobs_created': jobs_created,
            'total_entries': len(entries)
        }
        
    except Exception as exc:
        logger.error(f"RSS fetch failed for board {board_id}: {exc}")
        raise self.retry(exc=exc, countdown=60, max_retries=3)

@celery_app.task(bind=True, max_retries=3, queue='autoscraper.heavy')
def html_scrape(self, board_id: str, job_id: str, run_id: str):
    """
    Perform HTML scraping on a job board website
    
    Args:
        board_id (str): UUID of the job board
        job_id (str): UUID of the scrape job
        run_id (str): UUID of the scrape run
        
    Returns:
        dict: Scraping results
    """
    try:
        logger.info(f"Starting HTML scrape for board {board_id}")
        
        # HTML scraping functionality disabled
        logger.warning(f"HTML scrape for board {board_id} disabled - requires SQLite database setup")
        return {
            'success': False,
            'board_id': board_id,
            'error': 'HTML scraping requires SQLite database setup',
            'jobs_found': 0,
            'jobs_created': 0,
            'pages_scraped': 0
        }
        
        jobs_found = 0
        jobs_created = 0
        pages_scraped = 0
        max_pages = board.max_pages or 5
        
        # Build search URL
        search_url = board.base_url
        if board.search_params:
            # Add search parameters
            params = board.search_params.copy()
            if '?' in search_url:
                search_url += '&' + '&'.join([f"{k}={v}" for k, v in params.items()])
            else:
                search_url += '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
        
        for page in range(1, max_pages + 1):
            try:
                # Build page URL
                page_url = search_url
                if '{page}' in page_url:
                    page_url = page_url.replace('{page}', str(page))
                elif 'page=' not in page_url:
                    separator = '&' if '?' in page_url else '?'
                    page_url += f"{separator}page={page}"
                
                logger.info(f"Scraping page {page}: {page_url}")
                
                # Fetch page
                response = requests.get(page_url, timeout=30, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract job listings using selectors
                job_elements = []
                if board.job_selector:
                    job_elements = soup.select(board.job_selector)
                else:
                    # Fallback: common job listing selectors
                    selectors = [
                        '.job', '.job-item', '.job-listing', '.position',
                        '[data-job]', '.vacancy', '.opening'
                    ]
                    for selector in selectors:
                        job_elements = soup.select(selector)
                        if job_elements:
                            break
                
                if not job_elements:
                    logger.warning(f"No job elements found on page {page}")
                    continue
                
                page_jobs_found = 0
                
                for job_element in job_elements:
                    try:
                        # Extract job data
                        raw_data = extract_job_data(job_element, board, page_url)
                        
                        if not raw_data.get('title') or not raw_data.get('link'):
                            continue
                        
                        # Generate content hash
                        content_hash = hashlib.md5(
                            f"{raw_data['title']}{raw_data['link']}".encode('utf-8')
                        ).hexdigest()
                        
                        # Duplicate check disabled
                        existing = None
                        if existing:
                            continue
                        
                        # Persist raw item
                        persist_result = persist_raw_item.delay(
                            raw_data, content_hash, job_id, run_id, board_id
                        )
                        raw_job_id = persist_result.get(timeout=60)
                        
                        if raw_job_id:
                            page_jobs_found += 1
                            jobs_found += 1
                            
                            # Trigger normalization
                            normalize_result = normalize_raw_job.delay(raw_job_id)
                            normalized = normalize_result.get(timeout=120)
                            
                            if normalized and normalized.get('created_job_post'):
                                jobs_created += 1
                    
                    except Exception as e:
                        logger.error(f"Failed to process job element: {e}")
                        continue
                
                pages_scraped += 1
                logger.info(f"Page {page} completed: {page_jobs_found} jobs found")
                
                # Rate limiting
                time.sleep(board.delay_between_requests or 1)
                
                # Stop if no jobs found on this page
                if page_jobs_found == 0:
                    logger.info(f"No jobs found on page {page}, stopping")
                    break
                    
            except Exception as e:
                logger.error(f"Failed to scrape page {page}: {e}")
                continue
        
        logger.info(f"HTML scraping completed for {board.name}: {jobs_found} found, {jobs_created} created")
        
        return {
            'success': True,
            'board_id': board_id,
            'board_name': board.name,
            'jobs_found': jobs_found,
            'jobs_created': jobs_created,
            'pages_scraped': pages_scraped
        }
        
    except Exception as exc:
        logger.error(f"HTML scrape failed for board {board_id}: {exc}")
        raise self.retry(exc=exc, countdown=120, max_retries=3)

def extract_job_data(job_element, board: Any, page_url: str) -> Dict[str, Any]:
    """
    Extract job data from HTML element using board selectors
    
    Args:
        job_element: BeautifulSoup element containing job data
        board: JobBoard configuration
        page_url: URL of the page being scraped
        
    Returns:
        dict: Extracted job data
    """
    data = {
        'source': board.name,
        'board_id': board.id,
        'scraped_at': datetime.utcnow().isoformat()
    }
    
    try:
        # Extract title
        if board.title_selector:
            title_elem = job_element.select_one(board.title_selector)
            data['title'] = title_elem.get_text(strip=True) if title_elem else ''
        else:
            # Fallback selectors
            for selector in ['.title', '.job-title', 'h2', 'h3', '.position-title']:
                title_elem = job_element.select_one(selector)
                if title_elem:
                    data['title'] = title_elem.get_text(strip=True)
                    break
        
        # Extract link
        if board.link_selector:
            link_elem = job_element.select_one(board.link_selector)
            if link_elem:
                href = link_elem.get('href', '')
                data['link'] = urljoin(page_url, href) if href else ''
        else:
            # Fallback: look for any link in the job element
            link_elem = job_element.select_one('a[href]')
            if link_elem:
                href = link_elem.get('href', '')
                data['link'] = urljoin(page_url, href) if href else ''
        
        # Extract company
        if board.company_selector:
            company_elem = job_element.select_one(board.company_selector)
            data['company'] = company_elem.get_text(strip=True) if company_elem else ''
        
        # Extract location
        if board.location_selector:
            location_elem = job_element.select_one(board.location_selector)
            data['location'] = location_elem.get_text(strip=True) if location_elem else ''
        
        # Extract description
        if board.description_selector:
            desc_elem = job_element.select_one(board.description_selector)
            data['description'] = desc_elem.get_text(strip=True) if desc_elem else ''
        
        # Extract salary
        if board.salary_selector:
            salary_elem = job_element.select_one(board.salary_selector)
            data['salary'] = salary_elem.get_text(strip=True) if salary_elem else ''
        
        # Extract date
        if board.date_selector:
            date_elem = job_element.select_one(board.date_selector)
            data['posted_date'] = date_elem.get_text(strip=True) if date_elem else ''
        
        # Extract all text as fallback
        data['raw_html'] = str(job_element)
        data['raw_text'] = job_element.get_text(strip=True)
        
    except Exception as e:
        logger.error(f"Error extracting job data: {e}")
    
    return data

@celery_app.task(bind=True, max_retries=3, queue='autoscraper.default')
def persist_raw_item(self, raw_data: Dict[str, Any], content_hash: str, 
                    job_id: str, run_id: str, board_id: str):
    """
    Persist raw scraped item to database
    
    Args:
        raw_data: Raw scraped job data
        content_hash: Hash for deduplication
        job_id: UUID of the scrape job
        run_id: UUID of the scrape run
        board_id: UUID of the job board
        
    Returns:
        str: ID of created raw job record
    """
    try:
        # Raw job persistence disabled - requires SQLite database setup
        logger.warning(f"Raw job persistence disabled for job {job_id} - requires SQLite database setup")
        return None
            
    except Exception as exc:
        logger.error(f"Failed to persist raw item: {exc}")
        raise self.retry(exc=exc, countdown=30, max_retries=3)

@celery_app.task(bind=True, max_retries=3, queue='autoscraper.default')
def normalize_raw_job(self, raw_job_id: str):
    """
    Normalize raw job data and create JobPost if valid
    
    Args:
        raw_job_id: UUID of the raw job to normalize
        
    Returns:
        dict: Normalization results
    """
    try:
        # Job normalization disabled - requires SQLite database setup
        logger.warning(f"Job normalization disabled for raw job {raw_job_id} - requires SQLite database setup")
        return {
            'success': False,
            'raw_job_id': raw_job_id,
            'error': 'Job normalization requires SQLite database setup',
            'created_job_post': False
        }
            
    except Exception as exc:
        logger.error(f"Normalization failed for raw job {raw_job_id}: {exc}")
        
        # Raw job status update disabled - requires SQLite database setup
        logger.warning(f"Raw job status update disabled for {raw_job_id} - requires SQLite database setup")
        
        raise self.retry(exc=exc, countdown=60, max_retries=3)

@celery_app.task(queue='autoscraper.default')
def heartbeat():
    """
    Update engine state and system health metrics
    
    Returns:
        dict: System status information
    """
    try:
        # For now, return a simple heartbeat status since we're using MongoDB
        # and the autoscraper service has its own SQLite database
        heartbeat_data = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'autoscraper',
            'message': 'Heartbeat successful'
        }
        
        logger.info("Autoscraper heartbeat completed", extra=heartbeat_data)
        
        return {
            'success': True,
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat()
        }
            
    except Exception as e:
        logger.error(f"Heartbeat failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Utility functions

def clean_text(text: str) -> str:
    """Clean and normalize text data"""
    if not text:
        return ''
    
    # Remove extra whitespace and normalize
    text = ' '.join(text.split())
    return text.strip()

def extract_salary(salary_text: str) -> Optional[str]:
    """Extract and normalize salary information"""
    if not salary_text:
        return None
    
    # Basic salary extraction logic
    import re
    
    # Look for common salary patterns
    patterns = [
        r'\$[\d,]+(?:\s*-\s*\$[\d,]+)?',
        r'[\d,]+\s*-\s*[\d,]+\s*(?:USD|EUR|GBP)',
        r'[\d,]+k?\s*-\s*[\d,]+k?'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, salary_text, re.IGNORECASE)
        if match:
            return match.group(0)
    
    return None

def extract_job_type(text: str) -> Optional[str]:
    """Extract job type from text"""
    if not text:
        return None
    
    text_lower = text.lower()
    
    if any(word in text_lower for word in ['full-time', 'full time', 'fulltime']):
        return 'full-time'
    elif any(word in text_lower for word in ['part-time', 'part time', 'parttime']):
        return 'part-time'
    elif any(word in text_lower for word in ['contract', 'contractor', 'freelance']):
        return 'contract'
    elif any(word in text_lower for word in ['intern', 'internship']):
        return 'internship'
    
    return None

def extract_remote_type(text: str) -> Optional[str]:
    """Extract remote work type from text"""
    if not text:
        return None
    
    text_lower = text.lower()
    
    if any(word in text_lower for word in ['fully remote', '100% remote', 'remote only']):
        return 'fully-remote'
    elif any(word in text_lower for word in ['hybrid', 'remote/office']):
        return 'hybrid'
    elif any(word in text_lower for word in ['remote', 'work from home', 'wfh']):
        return 'remote-friendly'
    elif any(word in text_lower for word in ['on-site', 'onsite', 'office']):
        return 'on-site'
    
    return None

def parse_date(date_text: str) -> Optional[datetime]:
    """Parse date from various formats"""
    if not date_text:
        return None
    
    import dateutil.parser
    
    try:
        return dateutil.parser.parse(date_text)
    except:
        return None

def extract_tags(text: str) -> List[str]:
    """Extract relevant tags from job text"""
    if not text:
        return []
    
    text_lower = text.lower()
    tags = []
    
    # Technology tags
    tech_keywords = [
        'python', 'javascript', 'java', 'react', 'node.js', 'angular', 'vue',
        'django', 'flask', 'fastapi', 'sql', 'postgresql', 'mysql', 'mongodb',
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'git', 'linux'
    ]
    
    for keyword in tech_keywords:
        if keyword in text_lower:
            tags.append(keyword)
    
    # Experience level tags
    if any(word in text_lower for word in ['senior', 'lead', 'principal']):
        tags.append('senior-level')
    elif any(word in text_lower for word in ['junior', 'entry', 'graduate']):
        tags.append('entry-level')
    elif any(word in text_lower for word in ['mid', 'intermediate']):
        tags.append('mid-level')
    
    return list(set(tags))  # Remove duplicates

def calculate_quality_score(data: Dict[str, Any]) -> float:
    """Calculate data quality score for normalized job"""
    score = 0.0
    
    # Title quality (30%)
    if data.get('title'):
        title_len = len(data['title'])
        if title_len >= 10:
            score += 0.3
        elif title_len >= 5:
            score += 0.15
    
    # Company quality (20%)
    if data.get('company') and len(data['company']) >= 2:
        score += 0.2
    
    # Description quality (25%)
    if data.get('description'):
        desc_len = len(data['description'])
        if desc_len >= 100:
            score += 0.25
        elif desc_len >= 50:
            score += 0.15
        elif desc_len >= 20:
            score += 0.1
    
    # Location quality (10%)
    if data.get('location') and len(data['location']) >= 2:
        score += 0.1
    
    # Additional fields (15%)
    bonus_fields = ['salary_range', 'job_type', 'remote_type', 'posted_date']
    filled_bonus = sum(1 for field in bonus_fields if data.get(field))
    score += (filled_bonus / len(bonus_fields)) * 0.15
    
    return min(score, 1.0)  # Cap at 1.0