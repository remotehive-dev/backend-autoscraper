from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
# from sqlalchemy.orm import Session  # Using MongoDB instead
from loguru import logger
import requests
import feedparser
from bs4 import BeautifulSoup
import re
import time
import hashlib
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

from backend.database.database import get_database_manager
# TODO: MongoDB Migration - Update imports to use MongoDB models
# from backend.database.models import (
#     JobBoard, AutoScrapeScrapeJob as ScrapeJob, AutoScrapeScrapeRun as ScrapeRun, 
#     AutoScrapeRawJob as RawJob, AutoScrapeNormalizedJob as NormalizedJob,
#     JobBoardType, ScrapeJobStatus
# )
# from backend.database.models import JobPost
from backend.models.mongodb_models import (
    JobBoard, AutoScrapeScrapeJob as ScrapeJob, AutoScrapeScrapeRun as ScrapeRun, 
    AutoScrapeRawJob as RawJob, AutoScrapeNormalizedJob as NormalizedJob,
    JobBoardType, ScrapeJobStatus, JobPost
)
from backend.services.job_post_service import JobPostService


@dataclass
class ScrapingResult:
    """Result of a scraping operation"""
    success: bool
    items_found: int
    items_processed: int
    items_saved: int
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class NormalizationResult:
    """Result of a normalization operation"""
    success: bool
    raw_jobs_processed: int
    normalized_jobs_created: int
    jobs_published: int
    error_message: Optional[str] = None
    quality_scores: Optional[List[float]] = None


class ScrapingService:
    """Service for handling web scraping operations"""
    
    def __init__(self, db_session = None):
        self.db = db_session or get_database_manager().get_session()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def scrape_rss_feed(self, job_board: JobBoard, scrape_job: ScrapeJob) -> ScrapingResult:
        """
        Scrape RSS feed from a job board
        """
        try:
            logger.info(f"Starting RSS scraping for {job_board.name}")
            
            if not job_board.rss_url:
                return ScrapingResult(
                    success=False,
                    items_found=0,
                    items_processed=0,
                    items_saved=0,
                    error_message="No RSS URL configured for job board"
                )
            
            # Apply custom headers if configured
            headers = job_board.headers or {}
            if headers:
                self.session.headers.update(headers)
            
            # Fetch RSS feed
            response = self.session.get(job_board.rss_url, timeout=30)
            response.raise_for_status()
            
            # Parse RSS feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"RSS feed parsing warning for {job_board.name}: {feed.bozo_exception}")
            
            items_found = len(feed.entries)
            items_processed = 0
            items_saved = 0
            
            logger.info(f"Found {items_found} RSS entries for {job_board.name}")
            
            for entry in feed.entries:
                try:
                    # Extract basic information
                    title = entry.get('title', '').strip()
                    link = entry.get('link', '').strip()
                    description = entry.get('description', '').strip()
                    pub_date = entry.get('published_parsed')
                    
                    if not title or not link:
                        continue
                    
                    # Convert publication date
                    published_at = None
                    if pub_date:
                        try:
                            published_at = datetime(*pub_date[:6])
                        except (TypeError, ValueError):
                            pass
                    
                    # Create content hash for deduplication
                    content_hash = self._create_content_hash(title, link, description)
                    
                    # Check for existing raw job
                    existing_raw = self.db.query(RawJob).filter(
                        RawJob.content_hash == content_hash,
                        RawJob.job_board_id == job_board.id
                    ).first()
                    
                    if existing_raw:
                        logger.debug(f"Skipping duplicate RSS entry: {title}")
                        continue
                    
                    # Create raw job entry
                    raw_job = RawJob(
                        job_board_id=job_board.id,
                        scrape_job_id=scrape_job.id,
                        source_url=link,
                        content_hash=content_hash,
                        raw_data={
                            'title': title,
                            'link': link,
                            'description': description,
                            'published': entry.get('published', ''),
                            'author': entry.get('author', ''),
                            'category': entry.get('category', ''),
                            'tags': entry.get('tags', []),
                            'source': 'rss',
                            'scrape_timestamp': datetime.utcnow().isoformat()
                        },
                        scraped_at=datetime.utcnow(),
                        published_at=published_at
                    )
                    
                    self.db.add(raw_job)
                    items_saved += 1
                    
                    # Apply rate limiting
                    if job_board.rate_limit_delay > 0:
                        time.sleep(job_board.rate_limit_delay)
                    
                    items_processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing RSS entry: {str(e)}")
                    continue
            
            self.db.commit()
            
            logger.info(f"RSS scraping completed for {job_board.name}: {items_saved} items saved")
            
            return ScrapingResult(
                success=True,
                items_found=items_found,
                items_processed=items_processed,
                items_saved=items_saved,
                metadata={
                    'feed_title': feed.feed.get('title', ''),
                    'feed_description': feed.feed.get('description', ''),
                    'feed_updated': feed.feed.get('updated', '')
                }
            )
            
        except Exception as e:
            logger.error(f"RSS scraping failed for {job_board.name}: {str(e)}")
            self.db.rollback()
            return ScrapingResult(
                success=False,
                items_found=0,
                items_processed=0,
                items_saved=0,
                error_message=str(e)
            )
    
    def scrape_html_pages(self, job_board: JobBoard, scrape_job: ScrapeJob, max_pages: int = None) -> ScrapingResult:
        """
        Scrape HTML pages from a job board
        """
        try:
            logger.info(f"Starting HTML scraping for {job_board.name}")
            
            if not job_board.selectors:
                return ScrapingResult(
                    success=False,
                    items_found=0,
                    items_processed=0,
                    items_saved=0,
                    error_message="No selectors configured for job board"
                )
            
            selectors = job_board.selectors
            base_url = job_board.base_url
            
            # Apply custom headers
            headers = job_board.headers or {}
            if headers:
                self.session.headers.update(headers)
            
            total_items_found = 0
            total_items_processed = 0
            total_items_saved = 0
            
            # Determine pagination strategy
            max_pages = max_pages or scrape_job.max_pages or 5
            current_page = 1
            
            while current_page <= max_pages:
                try:
                    # Build page URL
                    if 'pagination_url_pattern' in selectors:
                        page_url = selectors['pagination_url_pattern'].format(
                            base_url=base_url,
                            page=current_page
                        )
                    else:
                        page_url = base_url if current_page == 1 else f"{base_url}?page={current_page}"
                    
                    logger.info(f"Scraping page {current_page}: {page_url}")
                    
                    # Fetch page
                    response = self.session.get(page_url, timeout=30)
                    response.raise_for_status()
                    
                    # Parse HTML
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Extract job listings
                    job_container_selector = selectors.get('job_container', '.job-listing')
                    job_elements = soup.select(job_container_selector)
                    
                    if not job_elements:
                        logger.info(f"No job listings found on page {current_page}, stopping pagination")
                        break
                    
                    page_items_found = len(job_elements)
                    page_items_processed = 0
                    page_items_saved = 0
                    
                    logger.info(f"Found {page_items_found} job listings on page {current_page}")
                    
                    for job_element in job_elements:
                        try:
                            # Extract job data using selectors
                            job_data = self._extract_job_data(job_element, selectors, base_url)
                            
                            if not job_data.get('title') or not job_data.get('url'):
                                continue
                            
                            # Create content hash
                            content_hash = self._create_content_hash(
                                job_data.get('title', ''),
                                job_data.get('url', ''),
                                job_data.get('description', '')
                            )
                            
                            # Check for duplicates
                            existing_raw = self.db.query(RawJob).filter(
                                RawJob.content_hash == content_hash,
                                RawJob.job_board_id == job_board.id
                            ).first()
                            
                            if existing_raw:
                                logger.debug(f"Skipping duplicate job: {job_data.get('title')}")
                                continue
                            
                            # Create raw job entry
                            raw_job = RawJob(
                                job_board_id=job_board.id,
                                scrape_job_id=scrape_job.id,
                                source_url=job_data.get('url'),
                                content_hash=content_hash,
                                raw_data={
                                    **job_data,
                                    'source': 'html',
                                    'page_number': current_page,
                                    'scrape_timestamp': datetime.utcnow().isoformat()
                                },
                                scraped_at=datetime.utcnow()
                            )
                            
                            self.db.add(raw_job)
                            page_items_saved += 1
                            
                            # Apply rate limiting
                            if job_board.rate_limit_delay > 0:
                                time.sleep(job_board.rate_limit_delay)
                            
                            page_items_processed += 1
                            
                        except Exception as e:
                            logger.error(f"Error processing job element: {str(e)}")
                            continue
                    
                    total_items_found += page_items_found
                    total_items_processed += page_items_processed
                    total_items_saved += page_items_saved
                    
                    # Check if we should continue pagination
                    if page_items_saved == 0:
                        logger.info(f"No new items found on page {current_page}, stopping pagination")
                        break
                    
                    current_page += 1
                    
                    # Inter-page delay
                    if job_board.rate_limit_delay > 0:
                        time.sleep(job_board.rate_limit_delay * 2)
                    
                except Exception as e:
                    logger.error(f"Error scraping page {current_page}: {str(e)}")
                    break
            
            self.db.commit()
            
            logger.info(f"HTML scraping completed for {job_board.name}: {total_items_saved} items saved across {current_page - 1} pages")
            
            return ScrapingResult(
                success=True,
                items_found=total_items_found,
                items_processed=total_items_processed,
                items_saved=total_items_saved,
                metadata={
                    'pages_scraped': current_page - 1,
                    'max_pages_configured': max_pages
                }
            )
            
        except Exception as e:
            logger.error(f"HTML scraping failed for {job_board.name}: {str(e)}")
            self.db.rollback()
            return ScrapingResult(
                success=False,
                items_found=0,
                items_processed=0,
                items_saved=0,
                error_message=str(e)
            )
    
    def _extract_job_data(self, job_element, selectors: Dict[str, str], base_url: str) -> Dict[str, Any]:
        """
        Extract job data from HTML element using configured selectors
        """
        job_data = {}
        
        try:
            # Title
            title_selector = selectors.get('title', 'h2, h3, .job-title')
            title_element = job_element.select_one(title_selector)
            job_data['title'] = title_element.get_text(strip=True) if title_element else ''
            
            # URL
            url_selector = selectors.get('url', 'a')
            url_element = job_element.select_one(url_selector)
            if url_element:
                href = url_element.get('href', '')
                job_data['url'] = urljoin(base_url, href) if href else ''
            else:
                job_data['url'] = ''
            
            # Company
            company_selector = selectors.get('company', '.company, .employer')
            company_element = job_element.select_one(company_selector)
            job_data['company'] = company_element.get_text(strip=True) if company_element else ''
            
            # Location
            location_selector = selectors.get('location', '.location, .job-location')
            location_element = job_element.select_one(location_selector)
            job_data['location'] = location_element.get_text(strip=True) if location_element else ''
            
            # Description
            description_selector = selectors.get('description', '.description, .job-summary')
            description_element = job_element.select_one(description_selector)
            job_data['description'] = description_element.get_text(strip=True) if description_element else ''
            
            # Salary
            salary_selector = selectors.get('salary', '.salary, .pay')
            salary_element = job_element.select_one(salary_selector)
            job_data['salary'] = salary_element.get_text(strip=True) if salary_element else ''
            
            # Job type
            job_type_selector = selectors.get('job_type', '.job-type, .employment-type')
            job_type_element = job_element.select_one(job_type_selector)
            job_data['job_type'] = job_type_element.get_text(strip=True) if job_type_element else ''
            
            # Posted date
            date_selector = selectors.get('posted_date', '.posted-date, .date')
            date_element = job_element.select_one(date_selector)
            job_data['posted_date'] = date_element.get_text(strip=True) if date_element else ''
            
            # Tags/Skills
            tags_selector = selectors.get('tags', '.tags, .skills')
            tags_elements = job_element.select(tags_selector)
            job_data['tags'] = [tag.get_text(strip=True) for tag in tags_elements]
            
        except Exception as e:
            logger.error(f"Error extracting job data: {str(e)}")
        
        return job_data
    
    def _create_content_hash(self, title: str, url: str, description: str) -> str:
        """
        Create a hash for content deduplication
        """
        content = f"{title.lower().strip()}{url.strip()}{description.lower().strip()[:200]}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def __del__(self):
        """Cleanup session"""
        if hasattr(self, 'session'):
            self.session.close()


class NormalizationService:
    """Service for normalizing raw job data into structured format"""
    
    def __init__(self, db_session = None):
        self.db = db_session or get_database_manager().get_session()
        self.job_post_service = JobPostService(self.db)
    
    def normalize_raw_jobs(self, job_board: JobBoard, scrape_job: ScrapeJob, limit: int = None) -> NormalizationResult:
        """
        Normalize raw jobs from a scrape job into structured format
        """
        try:
            logger.info(f"Starting normalization for scrape job {scrape_job.id}")
            
            # Get raw jobs to normalize
            query = self.db.query(RawJob).filter(
                RawJob.scrape_job_id == scrape_job.id,
                RawJob.is_processed == False
            ).order_by(RawJob.scraped_at.desc())
            
            if limit:
                query = query.limit(limit)
            
            raw_jobs = query.all()
            
            if not raw_jobs:
                logger.info(f"No raw jobs to normalize for scrape job {scrape_job.id}")
                return NormalizationResult(
                    success=True,
                    raw_jobs_processed=0,
                    normalized_jobs_created=0,
                    jobs_published=0
                )
            
            logger.info(f"Found {len(raw_jobs)} raw jobs to normalize")
            
            raw_jobs_processed = 0
            normalized_jobs_created = 0
            jobs_published = 0
            quality_scores = []
            
            for raw_job in raw_jobs:
                try:
                    # Normalize the raw job
                    normalized_data = self._normalize_job_data(raw_job, job_board)
                    
                    if not normalized_data:
                        raw_job.is_processed = True
                        raw_job.processing_error = "Failed to normalize job data"
                        continue
                    
                    # Calculate quality score
                    quality_score = self._calculate_quality_score(normalized_data)
                    quality_scores.append(quality_score)
                    
                    # Check quality threshold
                    if quality_score < job_board.quality_threshold:
                        logger.debug(f"Job quality score {quality_score} below threshold {job_board.quality_threshold}")
                        raw_job.is_processed = True
                        raw_job.processing_error = f"Quality score {quality_score} below threshold"
                        continue
                    
                    # Check for existing normalized job
                    existing_normalized = self.db.query(NormalizedJob).filter(
                        NormalizedJob.content_hash == raw_job.content_hash
                    ).first()
                    
                    if existing_normalized:
                        logger.debug(f"Normalized job already exists for content hash {raw_job.content_hash}")
                        raw_job.is_processed = True
                        continue
                    
                    # Create normalized job
                    normalized_job = NormalizedJob(
                        raw_job_id=raw_job.id,
                        job_board_id=job_board.id,
                        scrape_job_id=scrape_job.id,
                        content_hash=raw_job.content_hash,
                        title=normalized_data['title'],
                        company=normalized_data.get('company', ''),
                        location=normalized_data.get('location', ''),
                        description=normalized_data.get('description', ''),
                        salary_min=normalized_data.get('salary_min'),
                        salary_max=normalized_data.get('salary_max'),
                        salary_currency=normalized_data.get('salary_currency', 'USD'),
                        job_type=normalized_data.get('job_type', ''),
                        experience_level=normalized_data.get('experience_level', ''),
                        skills=normalized_data.get('skills', []),
                        benefits=normalized_data.get('benefits', []),
                        requirements=normalized_data.get('requirements', []),
                        source_url=raw_job.source_url,
                        posted_at=normalized_data.get('posted_at') or raw_job.published_at,
                        quality_score=quality_score,
                        normalized_at=datetime.utcnow(),
                        metadata={
                            'normalization_version': '1.0',
                            'original_data_keys': list(raw_job.raw_data.keys()),
                            'quality_factors': normalized_data.get('quality_factors', {})
                        }
                    )
                    
                    self.db.add(normalized_job)
                    normalized_jobs_created += 1
                    
                    # Mark raw job as processed
                    raw_job.is_processed = True
                    raw_job.processed_at = datetime.utcnow()
                    
                    # Optionally publish to main job posts
                    if normalized_job.quality_score >= 0.8:  # High quality threshold for auto-publishing
                        try:
                            job_post = self._create_job_post(normalized_job)
                            if job_post:
                                normalized_job.is_published = True
                                normalized_job.published_at = datetime.utcnow()
                                normalized_job.job_post_id = job_post.id
                                jobs_published += 1
                        except Exception as e:
                            logger.error(f"Failed to publish job post: {str(e)}")
                    
                    raw_jobs_processed += 1
                    
                except Exception as e:
                    logger.error(f"Error normalizing raw job {raw_job.id}: {str(e)}")
                    raw_job.is_processed = True
                    raw_job.processing_error = str(e)
                    continue
            
            self.db.commit()
            
            avg_quality_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            
            logger.info(f"Normalization completed: {normalized_jobs_created} jobs created, {jobs_published} published, avg quality: {avg_quality_score:.2f}")
            
            return NormalizationResult(
                success=True,
                raw_jobs_processed=raw_jobs_processed,
                normalized_jobs_created=normalized_jobs_created,
                jobs_published=jobs_published,
                quality_scores=quality_scores
            )
            
        except Exception as e:
            logger.error(f"Normalization failed for scrape job {scrape_job.id}: {str(e)}")
            self.db.rollback()
            return NormalizationResult(
                success=False,
                raw_jobs_processed=0,
                normalized_jobs_created=0,
                jobs_published=0,
                error_message=str(e)
            )
    
    def _normalize_job_data(self, raw_job: RawJob, job_board: JobBoard) -> Optional[Dict[str, Any]]:
        """
        Normalize raw job data into structured format
        """
        try:
            raw_data = raw_job.raw_data
            normalized = {}
            
            # Title normalization
            title = raw_data.get('title', '').strip()
            if not title:
                return None
            
            normalized['title'] = self._clean_text(title)
            
            # Company normalization
            company = raw_data.get('company', '').strip()
            normalized['company'] = self._clean_text(company) if company else ''
            
            # Location normalization
            location = raw_data.get('location', '').strip()
            normalized['location'] = self._normalize_location(location)
            
            # Description normalization
            description = raw_data.get('description', '').strip()
            normalized['description'] = self._clean_html(description) if description else ''
            
            # Salary normalization
            salary_info = self._normalize_salary(raw_data.get('salary', ''))
            normalized.update(salary_info)
            
            # Job type normalization
            job_type = raw_data.get('job_type', '').strip()
            normalized['job_type'] = self._normalize_job_type(job_type)
            
            # Experience level extraction
            normalized['experience_level'] = self._extract_experience_level(title, description)
            
            # Skills extraction
            normalized['skills'] = self._extract_skills(title, description)
            
            # Benefits extraction
            normalized['benefits'] = self._extract_benefits(description)
            
            # Requirements extraction
            normalized['requirements'] = self._extract_requirements(description)
            
            # Posted date normalization
            posted_date = raw_data.get('posted_date', '')
            normalized['posted_at'] = self._normalize_date(posted_date)
            
            # Quality factors for scoring
            normalized['quality_factors'] = {
                'has_company': bool(normalized['company']),
                'has_location': bool(normalized['location']),
                'has_description': len(normalized['description']) > 50,
                'has_salary': bool(salary_info.get('salary_min')),
                'has_skills': len(normalized['skills']) > 0,
                'title_length': len(normalized['title']),
                'description_length': len(normalized['description'])
            }
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error normalizing job data: {str(e)}")
            return None
    
    def _calculate_quality_score(self, normalized_data: Dict[str, Any]) -> float:
        """
        Calculate quality score for normalized job data
        """
        try:
            factors = normalized_data.get('quality_factors', {})
            score = 0.0
            
            # Base score for having a title
            score += 0.2
            
            # Company information
            if factors.get('has_company'):
                score += 0.15
            
            # Location information
            if factors.get('has_location'):
                score += 0.15
            
            # Description quality
            if factors.get('has_description'):
                score += 0.2
                # Bonus for longer descriptions
                desc_length = factors.get('description_length', 0)
                if desc_length > 200:
                    score += 0.1
            
            # Salary information
            if factors.get('has_salary'):
                score += 0.1
            
            # Skills information
            if factors.get('has_skills'):
                score += 0.1
            
            # Title quality
            title_length = factors.get('title_length', 0)
            if 10 <= title_length <= 100:
                score += 0.05
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating quality score: {str(e)}")
            return 0.5  # Default score
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text content
        """
        if not text:
            return ''
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?()-]', '', text)
        
        return text
    
    def _clean_html(self, html_content: str) -> str:
        """
        Clean HTML content and extract text
        """
        if not html_content:
            return ''
        
        # Parse HTML and extract text
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        
        return self._clean_text(text)
    
    def _normalize_location(self, location: str) -> str:
        """
        Normalize location information
        """
        if not location:
            return ''
        
        # Clean location text
        location = self._clean_text(location)
        
        # Common location normalizations
        location = re.sub(r'\b(remote|work from home|wfh)\b', 'Remote', location, flags=re.IGNORECASE)
        location = re.sub(r'\b(usa|united states)\b', 'United States', location, flags=re.IGNORECASE)
        location = re.sub(r'\b(uk|united kingdom)\b', 'United Kingdom', location, flags=re.IGNORECASE)
        
        return location
    
    def _normalize_salary(self, salary_text: str) -> Dict[str, Any]:
        """
        Extract and normalize salary information
        """
        result = {
            'salary_min': None,
            'salary_max': None,
            'salary_currency': 'USD'
        }
        
        if not salary_text:
            return result
        
        # Extract currency
        currency_match = re.search(r'\b(USD|EUR|GBP|CAD|AUD)\b', salary_text, re.IGNORECASE)
        if currency_match:
            result['salary_currency'] = currency_match.group(1).upper()
        
        # Extract salary numbers
        salary_numbers = re.findall(r'[\d,]+(?:\.\d{2})?', salary_text.replace(',', ''))
        
        if salary_numbers:
            try:
                numbers = [float(num.replace(',', '')) for num in salary_numbers]
                numbers.sort()
                
                if len(numbers) >= 2:
                    result['salary_min'] = int(numbers[0])
                    result['salary_max'] = int(numbers[-1])
                elif len(numbers) == 1:
                    # Single number - could be min or exact
                    if 'up to' in salary_text.lower():
                        result['salary_max'] = int(numbers[0])
                    else:
                        result['salary_min'] = int(numbers[0])
            except (ValueError, IndexError):
                pass
        
        return result
    
    def _normalize_job_type(self, job_type: str) -> str:
        """
        Normalize job type information
        """
        if not job_type:
            return ''
        
        job_type = job_type.lower().strip()
        
        # Map common variations
        type_mapping = {
            'full-time': 'Full-time',
            'fulltime': 'Full-time',
            'full time': 'Full-time',
            'part-time': 'Part-time',
            'parttime': 'Part-time',
            'part time': 'Part-time',
            'contract': 'Contract',
            'contractor': 'Contract',
            'freelance': 'Freelance',
            'temporary': 'Temporary',
            'temp': 'Temporary',
            'internship': 'Internship',
            'intern': 'Internship'
        }
        
        return type_mapping.get(job_type, job_type.title())
    
    def _extract_experience_level(self, title: str, description: str) -> str:
        """
        Extract experience level from title and description
        """
        text = f"{title} {description}".lower()
        
        if any(word in text for word in ['senior', 'sr.', 'lead', 'principal', 'architect']):
            return 'Senior'
        elif any(word in text for word in ['junior', 'jr.', 'entry', 'graduate', 'intern']):
            return 'Junior'
        elif any(word in text for word in ['mid', 'intermediate', 'experienced']):
            return 'Mid-level'
        
        return 'Not specified'
    
    def _extract_skills(self, title: str, description: str) -> List[str]:
        """
        Extract skills from title and description
        """
        text = f"{title} {description}".lower()
        
        # Common tech skills
        skills = []
        skill_patterns = [
            r'\b(python|java|javascript|typescript|react|angular|vue|node\.?js|php|ruby|go|rust|swift|kotlin)\b',
            r'\b(sql|mysql|postgresql|mongodb|redis|elasticsearch)\b',
            r'\b(aws|azure|gcp|docker|kubernetes|jenkins|git)\b',
            r'\b(html|css|sass|less|bootstrap|tailwind)\b',
            r'\b(django|flask|spring|express|laravel|rails)\b'
        ]
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            skills.extend([match.title() for match in matches])
        
        # Remove duplicates and return
        return list(set(skills))
    
    def _extract_benefits(self, description: str) -> List[str]:
        """
        Extract benefits from job description
        """
        if not description:
            return []
        
        text = description.lower()
        benefits = []
        
        benefit_keywords = {
            'health insurance': ['health insurance', 'medical insurance', 'healthcare'],
            'dental insurance': ['dental insurance', 'dental coverage'],
            'vision insurance': ['vision insurance', 'vision coverage'],
            '401k': ['401k', '401(k)', 'retirement plan'],
            'paid time off': ['pto', 'paid time off', 'vacation days'],
            'remote work': ['remote work', 'work from home', 'wfh'],
            'flexible hours': ['flexible hours', 'flexible schedule'],
            'stock options': ['stock options', 'equity', 'stock grants']
        }
        
        for benefit, keywords in benefit_keywords.items():
            if any(keyword in text for keyword in keywords):
                benefits.append(benefit)
        
        return benefits
    
    def _extract_requirements(self, description: str) -> List[str]:
        """
        Extract requirements from job description
        """
        if not description:
            return []
        
        requirements = []
        
        # Look for degree requirements
        if re.search(r'\b(bachelor|degree|bs|ba)\b', description, re.IGNORECASE):
            requirements.append('Bachelor\'s degree')
        
        if re.search(r'\b(master|ms|ma|mba)\b', description, re.IGNORECASE):
            requirements.append('Master\'s degree')
        
        # Look for experience requirements
        exp_match = re.search(r'(\d+)\+?\s*years?\s*(of\s*)?experience', description, re.IGNORECASE)
        if exp_match:
            years = exp_match.group(1)
            requirements.append(f'{years}+ years of experience')
        
        return requirements
    
    def _normalize_date(self, date_str: str) -> Optional[datetime]:
        """
        Normalize date string to datetime object
        """
        if not date_str:
            return None
        
        # Common date patterns
        patterns = [
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
            r'(\d{1,2})\s+(\w+)\s+(\d{4})',  # DD Month YYYY
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    if '/' in pattern:
                        month, day, year = match.groups()
                        return datetime(int(year), int(month), int(day))
                    elif '-' in pattern:
                        year, month, day = match.groups()
                        return datetime(int(year), int(month), int(day))
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _create_job_post(self, normalized_job: NormalizedJob) -> Optional[JobPost]:
        """
        Create a JobPost from normalized job data
        """
        try:
            # Create job post using the job post service
            job_post_data = {
                'title': normalized_job.title,
                'company_name': normalized_job.company,
                'location': normalized_job.location,
                'description': normalized_job.description,
                'job_type': normalized_job.job_type,
                'salary_min': normalized_job.salary_min,
                'salary_max': normalized_job.salary_max,
                'salary_currency': normalized_job.salary_currency,
                'skills_required': normalized_job.skills,
                'experience_level': normalized_job.experience_level,
                'source_url': normalized_job.source_url,
                'is_active': True,
                'is_featured': False,
                'posted_at': normalized_job.posted_at or datetime.utcnow()
            }
            
            # Use the job post service to create the job post
            job_post = self.job_post_service.create_job_post(job_post_data)
            
            logger.info(f"Created job post {job_post.id} from normalized job {normalized_job.id}")
            return job_post
            
        except Exception as e:
            logger.error(f"Failed to create job post from normalized job {normalized_job.id}: {str(e)}")
            return None