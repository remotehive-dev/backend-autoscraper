import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timedelta
import scrapy
from scrapy.crawler import CrawlerRunner, CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy.http import Request, Response
from scrapy.selector import Selector
from twisted.internet import reactor, defer
from twisted.internet.defer import inlineCallbacks
import logging
import random
import re
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)
import json
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor
import threading

from .multi_engine_framework import BaseJobScraper
from .types import ScrapingEngine, JobData
from ..models.mongodb_models import JobBoard
from ..ai.decision_engine import get_ai_decision_engine

class JobSpider(scrapy.Spider):
    """Scrapy spider for job scraping"""
    
    name = 'job_spider'
    
    def __init__(self, job_board: JobBoard, selectors: Dict[str, str], max_jobs: int = 100, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.job_board = job_board
        self.selectors = selectors
        self.max_jobs = max_jobs
        self.scraped_jobs = []
        self.job_count = 0
        self.ai_decision_engine = None  # Will be initialized in start_requests
        
        # Configure spider settings
        self.custom_settings = {
            'ROBOTSTXT_OBEY': False,
            'DOWNLOAD_DELAY': random.uniform(2, 5),
            'RANDOMIZE_DOWNLOAD_DELAY': True,
            'CONCURRENT_REQUESTS': 8,
            'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
            'AUTOTHROTTLE_ENABLED': True,
            'AUTOTHROTTLE_START_DELAY': 2,
            'AUTOTHROTTLE_MAX_DELAY': 10,
            'AUTOTHROTTLE_TARGET_CONCURRENCY': 2.0,
            'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'DEFAULT_REQUEST_HEADERS': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            'RETRY_ENABLED': True,
            'RETRY_TIMES': 3,
            'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],
            'COOKIES_ENABLED': True,
            'TELNETCONSOLE_ENABLED': False,
            'LOG_LEVEL': 'WARNING',  # Reduce Scrapy logging
        }
    
    def start_requests(self):
        """Generate initial requests"""
        try:
            # Initialize AI decision engine
            from ..ai.decision_engine import get_ai_decision_engine
            self.ai_decision_engine = get_ai_decision_engine()
            
            # Start with the base URL
            yield Request(
                url=self.job_board.base_url,
                callback=self.parse_job_listings,
                meta={'page': 1}
            )
            
        except Exception as e:
            logger.error(f"Failed to start requests: {e}")
    
    def parse_job_listings(self, response: Response):
        """Parse job listing pages"""
        try:
            page = response.meta.get('page', 1)
            logger.info(f"Parsing job listings page {page} for {self.job_board.name}")
            
            # Extract job URLs from current page
            job_urls = self._extract_job_urls(response)
            
            if not job_urls:
                logger.warning(f"No job URLs found on page {page}")
                return
            
            # Create requests for individual job pages
            for job_url in job_urls:
                if self.job_count >= self.max_jobs:
                    break
                    
                yield Request(
                    url=job_url,
                    callback=self.parse_job,
                    meta={'job_url': job_url}
                )
                self.job_count += 1
            
            # Try to find next page if we haven't reached max jobs
            if self.job_count < self.max_jobs and page < 10:  # Limit to 10 pages
                next_page_url = self._find_next_page(response)
                if next_page_url:
                    yield Request(
                        url=next_page_url,
                        callback=self.parse_job_listings,
                        meta={'page': page + 1}
                    )
            
        except Exception as e:
            logger.error(f"Failed to parse job listings: {e}")
    
    def _extract_job_urls(self, response: Response) -> List[str]:
        """Extract job URLs from listing page"""
        job_urls = []
        
        try:
            # Common job link selectors
            job_link_selectors = [
                'a[href*="/job/"]::attr(href)',
                'a[href*="/jobs/"]::attr(href)',
                'a[href*="/career/"]::attr(href)',
                'a[href*="/careers/"]::attr(href)',
                'a[href*="/position/"]::attr(href)',
                'a[href*="/vacancy/"]::attr(href)',
                '.job-title a::attr(href)',
                '.job-link::attr(href)',
                '.position-title a::attr(href)',
                '[data-testid*="job"] a::attr(href)',
                '[data-cy*="job"] a::attr(href)'
            ]
            
            # Try each selector
            for selector in job_link_selectors:
                urls = response.css(selector).getall()
                for url in urls:
                    if url and self._is_valid_job_url(url):
                        full_url = response.urljoin(url)
                        job_urls.append(full_url)
            
            # Remove duplicates
            job_urls = list(set(job_urls))
            
            # If no URLs found with common patterns, try AI analysis
            if not job_urls and self.ai_decision_engine:
                try:
                    html_sample = response.text[:5000]  # First 5KB
                    # Note: This would need to be adapted for async context
                    # For now, we'll skip AI analysis in Scrapy
                    pass
                except Exception as e:
                    logger.error(f"AI selector generation failed: {e}")
            
            logger.info(f"Found {len(job_urls)} job URLs on page")
            return job_urls
            
        except Exception as e:
            logger.error(f"Failed to extract job URLs: {e}")
            return job_urls
    
    def _is_valid_job_url(self, url: str) -> bool:
        """Check if URL looks like a job posting URL"""
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            # Check for job-related keywords in path
            job_keywords = ['job', 'career', 'position', 'vacancy', 'opening', 'role']
            return any(keyword in path for keyword in job_keywords)
            
        except Exception:
            return False
    
    def _find_next_page(self, response: Response) -> Optional[str]:
        """Find next page URL"""
        try:
            # Common next page selectors
            next_selectors = [
                'a[rel="next"]::attr(href)',
                '.next a::attr(href)',
                '.pagination-next::attr(href)',
                '.pager-next a::attr(href)',
                '[data-testid="next-page"]::attr(href)',
                '[aria-label*="Next"]::attr(href)'
            ]
            
            for selector in next_selectors:
                next_url = response.css(selector).get()
                if next_url:
                    return response.urljoin(next_url)
            
            # Try XPath for text-based selectors
            next_xpaths = [
                "//a[contains(text(), 'Next')]/@href",
                "//a[contains(text(), '→')]/@href",
                "//a[contains(@aria-label, 'Next')]/@href"
            ]
            
            for xpath in next_xpaths:
                next_url = response.xpath(xpath).get()
                if next_url:
                    return response.urljoin(next_url)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to find next page: {e}")
            return None
    
    def parse_job(self, response: Response):
        """Parse individual job page"""
        try:
            job_url = response.meta.get('job_url', response.url)
            logger.debug(f"Parsing job: {job_url}")
            
            # Extract job data
            job_data = self._extract_job_data(response, job_url)
            
            if job_data:
                self.scraped_jobs.append(job_data)
                logger.debug(f"Scraped job: {job_data['title']} at {job_data['company']}")
                yield job_data
            
        except Exception as e:
            logger.error(f"Failed to parse job {response.url}: {e}")
    
    def _extract_job_data(self, response: Response, job_url: str) -> Optional[Dict[str, Any]]:
        """Extract job data from job page"""
        try:
            # Extract basic fields using selectors
            title = self._extract_text_scrapy(response, self.selectors.get('job_title', ''), 'title')
            company = self._extract_text_scrapy(response, self.selectors.get('company', ''), 'company')
            location = self._extract_text_scrapy(response, self.selectors.get('location', ''), 'location')
            description = self._extract_text_scrapy(response, self.selectors.get('description', ''), 'description')
            salary = self._extract_text_scrapy(response, self.selectors.get('salary', ''), 'salary')
            date_posted_str = self._extract_text_scrapy(response, self.selectors.get('date_posted', ''), 'date')
            
            # Validate required fields
            if not title or not company:
                logger.warning(f"Missing required fields for job at {job_url}")
                return None
            
            # Parse date
            date_posted = self._parse_date(date_posted_str)
            
            # Create job data dictionary
            job_data = {
                'title': title.strip(),
                'company': company.strip(),
                'location': location.strip() if location else "Not specified",
                'description': description.strip() if description else "",
                'salary': salary.strip() if salary else None,
                'date_posted': date_posted.isoformat() if date_posted else None,
                'url': job_url,
                'job_board_id': str(self.job_board.id),
                'job_board_name': self.job_board.name,
                'scraped_at': datetime.now().isoformat(),
                'scraping_engine': ScrapingEngine.SCRAPY.value
            }
            
            return job_data
            
        except Exception as e:
            logger.error(f"Failed to extract job data: {e}")
            return None
    
    def _extract_text_scrapy(self, response: Response, selector: str, field_type: str) -> str:
        """Extract text using CSS selector with Scrapy"""
        if not selector:
            return ""
        
        try:
            # Try the provided selector first
            text = response.css(f'{selector}::text').get()
            if text and text.strip():
                return text.strip()
            
            # Try without ::text in case it's already included
            text = response.css(selector).get()
            if text and text.strip():
                # Extract text from HTML
                selector_obj = Selector(text=text)
                text_content = selector_obj.css('::text').getall()
                return ' '.join(text_content).strip()
            
            # Fallback selectors based on field type
            fallback_selectors = self._get_fallback_selectors(field_type)
            
            for fallback_selector in fallback_selectors:
                text = response.css(f'{fallback_selector}::text').get()
                if text and text.strip():
                    return text.strip()
            
            return ""
            
        except Exception as e:
            logger.error(f"Failed to extract text with selector '{selector}': {e}")
            return ""
    
    def _get_fallback_selectors(self, field_type: str) -> List[str]:
        """Get fallback selectors for different field types"""
        fallbacks = {
            'title': [
                'h1', 'h2', '.job-title', '.position-title', '.title',
                '[data-testid*="title"]', '[data-cy*="title"]'
            ],
            'company': [
                '.company', '.company-name', '.employer', '.organization',
                '[data-testid*="company"]', '[data-cy*="company"]'
            ],
            'location': [
                '.location', '.job-location', '.city', '.address',
                '[data-testid*="location"]', '[data-cy*="location"]'
            ],
            'description': [
                '.description', '.job-description', '.content', '.details',
                '[data-testid*="description"]', '[data-cy*="description"]'
            ],
            'salary': [
                '.salary', '.pay', '.compensation', '.wage',
                '[data-testid*="salary"]', '[data-cy*="salary"]'
            ],
            'date': [
                '.date', '.posted-date', '.job-date', '.publish-date',
                '[data-testid*="date"]', '[data-cy*="date"]'
            ]
        }
        
        return fallbacks.get(field_type, [])
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string to datetime"""
        if not date_str:
            return None
        
        try:
            # Common date patterns
            patterns = [
                r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
                r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
                r'(\d{1,2})-(\d{1,2})-(\d{4})',  # DD-MM-YYYY
            ]
            
            for pattern in patterns:
                match = re.search(pattern, date_str)
                if match:
                    groups = match.groups()
                    if len(groups) == 3:
                        try:
                            # Try different date formats
                            if pattern.startswith(r'(\d{4})'):
                                # YYYY-MM-DD
                                return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                            else:
                                # MM/DD/YYYY or DD-MM-YYYY
                                return datetime(int(groups[2]), int(groups[0]), int(groups[1]))
                        except ValueError:
                            continue
            
            # Try relative dates
            date_str_lower = date_str.lower()
            if 'today' in date_str_lower:
                return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            elif 'yesterday' in date_str_lower:
                return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            elif 'ago' in date_str_lower:
                # Try to parse "X days ago", "X hours ago", etc.
                match = re.search(r'(\d+)\s*(day|hour|week)s?\s*ago', date_str_lower)
                if match:
                    number = int(match.group(1))
                    unit = match.group(2)
                    
                    if unit == 'day':
                        return datetime.now() - timedelta(days=number)
                    elif unit == 'hour':
                        return datetime.now() - timedelta(hours=number)
                    elif unit == 'week':
                        return datetime.now() - timedelta(weeks=number)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse date '{date_str}': {e}")
            return None

class ScrapyJobScraper(BaseJobScraper):
    """Scrapy-based job scraper for high-performance scraping"""
    
    def __init__(self):
        super().__init__(ScrapingEngine.SCRAPY)
        self.ai_decision_engine = get_ai_decision_engine()
        self.executor = ThreadPoolExecutor(max_workers=1)  # Single thread for Scrapy
    
    async def test_connection(self, url: str) -> bool:
        """Test if we can connect to the URL"""
        try:
            # Use a simple HTTP request to test connection
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Scrapy connection test failed for {url}: {e}")
            return False
    
    async def scrape_jobs(self, job_board: JobBoard, selectors: Dict[str, str], **kwargs) -> List[JobData]:
        """Scrape jobs using Scrapy"""
        max_jobs = kwargs.get('max_jobs', 100)
        
        try:
            # Run Scrapy in a separate thread to avoid blocking
            loop = asyncio.get_event_loop()
            jobs_data = await loop.run_in_executor(
                self.executor,
                self._run_scrapy_spider,
                job_board,
                selectors,
                max_jobs
            )
            
            # Convert dictionaries to JobData objects
            jobs = []
            for job_dict in jobs_data:
                try:
                    # Parse date_posted back to datetime if it exists
                    date_posted = None
                    if job_dict.get('date_posted'):
                        date_posted = datetime.fromisoformat(job_dict['date_posted'])
                    
                    # Parse scraped_at back to datetime
                    scraped_at = datetime.fromisoformat(job_dict['scraped_at'])
                    
                    job_data = JobData(
                        title=job_dict['title'],
                        company=job_dict['company'],
                        location=job_dict['location'],
                        description=job_dict['description'],
                        salary=job_dict.get('salary'),
                        date_posted=date_posted,
                        url=job_dict['url'],
                        job_board_id=job_dict['job_board_id'],
                        job_board_name=job_dict['job_board_name'],
                        scraped_at=scraped_at,
                        scraping_engine=job_dict['scraping_engine']
                    )
                    jobs.append(job_data)
                    
                except Exception as e:
                    logger.error(f"Failed to convert job data: {e}")
                    continue
            
            logger.info(f"Scrapy scraped {len(jobs)} jobs from {job_board.name}")
            return jobs
            
        except Exception as e:
            logger.error(f"Scrapy scraping failed for {job_board.name}: {e}")
            return []
    
    def _run_scrapy_spider(self, job_board: JobBoard, selectors: Dict[str, str], max_jobs: int) -> List[Dict[str, Any]]:
        """Run Scrapy spider in synchronous context"""
        try:
            # Create a temporary file to store results
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
                temp_filename = temp_file.name
            
            # Configure Scrapy settings
            settings = get_project_settings()
            settings.update({
                'ROBOTSTXT_OBEY': False,
                'DOWNLOAD_DELAY': random.uniform(2, 5),
                'RANDOMIZE_DOWNLOAD_DELAY': True,
                'CONCURRENT_REQUESTS': 8,
                'CONCURRENT_REQUESTS_PER_DOMAIN': 4,
                'AUTOTHROTTLE_ENABLED': True,
                'AUTOTHROTTLE_START_DELAY': 2,
                'AUTOTHROTTLE_MAX_DELAY': 10,
                'AUTOTHROTTLE_TARGET_CONCURRENCY': 2.0,
                'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'RETRY_ENABLED': True,
                'RETRY_TIMES': 3,
                'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],
                'COOKIES_ENABLED': True,
                'TELNETCONSOLE_ENABLED': False,
                'LOG_LEVEL': 'WARNING',
                'FEEDS': {
                    temp_filename: {
                        'format': 'json',
                        'overwrite': True,
                    },
                },
            })
            
            # Create and run spider
            process = CrawlerProcess(settings)
            process.crawl(JobSpider, job_board=job_board, selectors=selectors, max_jobs=max_jobs)
            process.start()  # This will block until crawling is finished
            
            # Read results from temporary file
            jobs_data = []
            try:
                if os.path.exists(temp_filename) and os.path.getsize(temp_filename) > 0:
                    with open(temp_filename, 'r') as f:
                        content = f.read().strip()
                        if content:
                            # Handle both single object and array formats
                            if content.startswith('['):
                                jobs_data = json.loads(content)
                            else:
                                # Split by newlines for JSONL format
                                for line in content.split('\n'):
                                    if line.strip():
                                        jobs_data.append(json.loads(line))
                
                # Clean up temporary file
                os.unlink(temp_filename)
                
            except Exception as e:
                logger.error(f"Failed to read Scrapy results: {e}")
                # Clean up temporary file on error
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
            
            return jobs_data
            
        except Exception as e:
            logger.error(f"Failed to run Scrapy spider: {e}")
            return []
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.executor:
            self.executor.shutdown(wait=True)
            logger.info("Scrapy executor shutdown")