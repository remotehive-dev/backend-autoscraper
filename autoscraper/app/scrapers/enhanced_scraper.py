#!/usr/bin/env python3
"""
Enhanced Web Scraping Engine
Robust scraping engine with error handling, retry mechanisms, and support for multiple scraping types
"""

import asyncio
import aiohttp
import time
import logging
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import random

import feedparser
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# Import shared types
from .types import ScrapingStatus, ScrapingResult, JobPriority, JobData, ScrapingMetrics

from .job_board_configs import JobBoardConfigs, JobBoardType
from .deduplication import JobDeduplicator, deduplicate_jobs
from .scraping_monitor import ScrapingMonitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScrapingStatus(Enum):
    """Scraping operation status"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"

@dataclass
class ScrapingResult:
    """Result of a scraping operation"""
    status: ScrapingStatus
    jobs: List[Dict[str, Any]]
    total_found: int
    pages_scraped: int
    errors: List[str]
    execution_time: float
    job_board_name: str
    timestamp: datetime

class RateLimiter:
    """Rate limiter to prevent overwhelming job boards"""
    
    def __init__(self):
        self.last_requests = {}
    
    async def wait_if_needed(self, domain: str, delay: float):
        """Wait if needed to respect rate limits"""
        now = time.time()
        if domain in self.last_requests:
            time_since_last = now - self.last_requests[domain]
            if time_since_last < delay:
                wait_time = delay - time_since_last
                logger.info(f"Rate limiting: waiting {wait_time:.2f}s for {domain}")
                await asyncio.sleep(wait_time)
        
        self.last_requests[domain] = time.time()

class EnhancedScraper:
    """Enhanced web scraping engine with robust error handling"""
    
    def __init__(self, rate_limiter: Optional[RateLimiter] = None,
                 max_retries: int = 3,
                 timeout: int = 30,
                 user_agents: Optional[List[str]] = None,
                 enable_deduplication: bool = True,
                 enable_monitoring: bool = True):
        
        self.rate_limiter = rate_limiter or RateLimiter()
        self.max_retries = max_retries
        self.timeout = timeout
        self.session = None
        self.driver = None
        self.scraped_urls = set()  # Deduplication
        
        # Deduplication and monitoring
        self.enable_deduplication = enable_deduplication
        self.deduplicator = JobDeduplicator() if enable_deduplication else None
        self.monitor = ScrapingMonitor() if enable_monitoring else None
        
        # User agents for rotation
        self.user_agents = user_agents or [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        
        # Statistics
        self.stats = {
            'requests_made': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retries_used': 0,
            'rate_limited': 0,
            'jobs_scraped': 0,
            'duplicates_found': 0
        }
        
        # Error tracking
        self.error_counts = defaultdict(int)
        self.recent_errors = deque(maxlen=100)
        
        logger.info("EnhancedScraper initialized with deduplication and monitoring")
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=10, limit_per_host=5)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
        if self.driver:
            self.driver.quit()
    
    def _setup_selenium_driver(self) -> webdriver.Chrome:
        """Setup Selenium Chrome driver for JavaScript-heavy sites"""
        if self.driver:
            return self.driver
            
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
            return self.driver
        except Exception as e:
            logger.error(f"Failed to setup Selenium driver: {e}")
            return None
    
    async def scrape_job_board(self, job_board_config: Dict[str, Any], 
                              query: str = "remote", 
                              location: str = "worldwide",
                              max_pages: Optional[int] = None) -> ScrapingResult:
        """Scrape a job board with the given configuration"""
        start_time = time.time()
        job_board_name = job_board_config.get('name', 'Unknown')
        
        logger.info(f"Starting scrape of {job_board_name} for query: {query}")
        
        # Start monitoring
        if self.monitor:
            self.monitor.start_scraping_session(job_board_name, job_board_config.get('type', 'unknown'))
        
        try:
            if job_board_config['type'] == JobBoardType.RSS.value:
                result = await self._scrape_rss_feed(job_board_config, query, location)
            elif job_board_config['type'] == JobBoardType.HTML.value:
                result = await self._scrape_html_pages(job_board_config, query, location, max_pages)
            elif job_board_config['type'] == JobBoardType.API.value:
                result = await self._scrape_api_endpoint(job_board_config, query, location, max_pages)
            elif job_board_config['type'] == JobBoardType.HYBRID.value:
                result = await self._scrape_hybrid(job_board_config, query, location, max_pages)
            else:
                raise ValueError(f"Unsupported scraping type: {job_board_config['type']}")
            
            # Apply deduplication if enabled
            if self.enable_deduplication and self.deduplicator and result.jobs:
                unique_jobs, duplicates = self.deduplicator.process_jobs(result.jobs)
                self.stats['duplicates_found'] += len(duplicates)
                
                if self.monitor:
                    self.monitor.log_deduplication_results(len(unique_jobs), len(duplicates))
                
                # Update result with deduplicated jobs
                result.jobs = unique_jobs
                result.total_found = len(unique_jobs)
            
            # Update statistics
            self.stats['jobs_scraped'] += len(result.jobs)
            
            # End monitoring
            if self.monitor:
                self.monitor.end_scraping_session(job_board_name, len(result.jobs), success=True)
            
            return result
                
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Failed to scrape {job_board_name}: {e}")
            
            # Log error to monitor
            if self.monitor:
                self.monitor.log_error(job_board_name, str(e), 'scraping_error')
                self.monitor.end_scraping_session(job_board_name, 0, success=False)
            
            self.recent_errors.append({
                'timestamp': datetime.now(),
                'error': str(e),
                'job_board': job_board_name
            })
            
            return ScrapingResult(
                status=ScrapingStatus.FAILED,
                jobs=[],
                total_found=0,
                pages_scraped=0,
                errors=[str(e)],
                execution_time=execution_time,
                job_board_name=job_board_name,
                timestamp=datetime.now()
            )
    
    async def _scrape_rss_feed(self, config: Dict[str, Any], 
                              query: str, location: str) -> ScrapingResult:
        """Scrape RSS feed for job listings"""
        start_time = time.time()
        job_board_name = config.get('name', 'Unknown')
        errors = []
        jobs = []
        
        try:
            rss_url = config.get('rss_url', config.get('search_url_template', ''))
            if not rss_url:
                raise ValueError("No RSS URL provided")
            
            # Rate limiting
            domain = urlparse(rss_url).netloc
            await self.rate_limiter.wait_if_needed(domain, config.get('rate_limit_delay', 2.0))
            
            # Fetch RSS feed
            headers = config.get('headers', {})
            async with self.session.get(rss_url, headers=headers) as response:
                if response.status != 200:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status
                    )
                
                content = await response.text()
                feed = feedparser.parse(content)
                
                for entry in feed.entries:
                    try:
                        job_data = self._extract_rss_job_data(entry, config)
                        if job_data and self._is_quality_job(job_data, config):
                            jobs.append(job_data)
                    except Exception as e:
                        errors.append(f"Error processing RSS entry: {e}")
                        continue
            
            execution_time = time.time() - start_time
            status = ScrapingStatus.SUCCESS if jobs else ScrapingStatus.FAILED
            
            return ScrapingResult(
                status=status,
                jobs=jobs,
                total_found=len(jobs),
                pages_scraped=1,
                errors=errors,
                execution_time=execution_time,
                job_board_name=job_board_name,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"RSS scraping failed for {job_board_name}: {e}")
            return ScrapingResult(
                status=ScrapingStatus.FAILED,
                jobs=jobs,
                total_found=len(jobs),
                pages_scraped=0,
                errors=errors + [str(e)],
                execution_time=execution_time,
                job_board_name=job_board_name,
                timestamp=datetime.now()
            )
    
    async def _scrape_html_pages(self, config: Dict[str, Any], 
                                query: str, location: str, 
                                max_pages: Optional[int] = None) -> ScrapingResult:
        """Scrape HTML pages for job listings"""
        start_time = time.time()
        job_board_name = config.get('name', 'Unknown')
        errors = []
        jobs = []
        pages_scraped = 0
        
        max_pages = max_pages or config.get('max_pages', 5)
        requires_js = config.get('requires_js', False)
        
        try:
            for page in range(1, max_pages + 1):
                try:
                    page_jobs = await self._scrape_single_page(
                        config, query, location, page, requires_js
                    )
                    
                    if not page_jobs:
                        logger.info(f"No jobs found on page {page}, stopping")
                        break
                    
                    jobs.extend(page_jobs)
                    pages_scraped += 1
                    
                    # Rate limiting between pages
                    domain = urlparse(config['base_url']).netloc
                    await self.rate_limiter.wait_if_needed(
                        domain, config.get('rate_limit_delay', 2.0)
                    )
                    
                except Exception as e:
                    error_msg = f"Error scraping page {page}: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    continue
            
            execution_time = time.time() - start_time
            status = self._determine_scraping_status(jobs, errors, pages_scraped)
            
            return ScrapingResult(
                status=status,
                jobs=jobs,
                total_found=len(jobs),
                pages_scraped=pages_scraped,
                errors=errors,
                execution_time=execution_time,
                job_board_name=job_board_name,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"HTML scraping failed for {job_board_name}: {e}")
            return ScrapingResult(
                status=ScrapingStatus.FAILED,
                jobs=jobs,
                total_found=len(jobs),
                pages_scraped=pages_scraped,
                errors=errors + [str(e)],
                execution_time=execution_time,
                job_board_name=job_board_name,
                timestamp=datetime.now()
            )
    
    async def _scrape_single_page(self, config: Dict[str, Any], 
                                 query: str, location: str, 
                                 page: int, requires_js: bool) -> List[Dict[str, Any]]:
        """Scrape a single page for job listings"""
        url = self._build_search_url(config, query, location, page)
        
        if requires_js:
            return await self._scrape_with_selenium(config, url)
        else:
            return await self._scrape_with_requests(config, url)
    
    async def _scrape_with_requests(self, config: Dict[str, Any], 
                                   url: str) -> List[Dict[str, Any]]:
        """Scrape using aiohttp requests"""
        jobs = []
        headers = config.get('headers', {})
        timeout = config.get('request_timeout', 30)
        retry_attempts = config.get('retry_attempts', 3)
        
        for attempt in range(retry_attempts):
            try:
                async with self.session.get(url, headers=headers, timeout=timeout) as response:
                    if response.status == 429:  # Rate limited
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    if response.status != 200:
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status
                        )
                    
                    html = await response.text()
                    jobs = self._parse_html_jobs(html, config, url)
                    break
                    
            except asyncio.TimeoutError:
                if attempt == retry_attempts - 1:
                    raise
                logger.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                if attempt == retry_attempts - 1:
                    raise
                logger.warning(f"Request failed on attempt {attempt + 1}: {e}")
                await asyncio.sleep(2 ** attempt)
        
        return jobs
    
    async def _scrape_with_selenium(self, config: Dict[str, Any], 
                                   url: str) -> List[Dict[str, Any]]:
        """Scrape using Selenium for JavaScript-heavy sites"""
        jobs = []
        
        try:
            driver = self._setup_selenium_driver()
            if not driver:
                raise Exception("Failed to setup Selenium driver")
            
            driver.get(url)
            
            # Wait for job listings to load
            wait = WebDriverWait(driver, 10)
            job_container_selector = config['selectors']['job_container']
            
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, job_container_selector)))
            except TimeoutException:
                logger.warning(f"Timeout waiting for job listings to load: {url}")
                return jobs
            
            # Get page source and parse
            html = driver.page_source
            jobs = self._parse_html_jobs(html, config, url)
            
        except WebDriverException as e:
            logger.error(f"Selenium error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Selenium scraping: {e}")
            raise
        
        return jobs
    
    def _parse_html_jobs(self, html: str, config: Dict[str, Any], 
                        page_url: str) -> List[Dict[str, Any]]:
        """Parse HTML to extract job listings"""
        jobs = []
        soup = BeautifulSoup(html, 'html.parser')
        selectors = config['selectors']
        
        job_containers = soup.select(selectors['job_container'])
        
        for container in job_containers:
            try:
                job_data = self._extract_html_job_data(container, selectors, config, page_url)
                if job_data and self._is_quality_job(job_data, config):
                    # Deduplication check
                    job_hash = self._generate_job_hash(job_data)
                    if job_hash not in self.scraped_urls:
                        jobs.append(job_data)
                        self.scraped_urls.add(job_hash)
            except Exception as e:
                logger.warning(f"Error extracting job data: {e}")
                continue
        
        return jobs
    
    def _extract_html_job_data(self, container, selectors: Dict[str, str], 
                              config: Dict[str, Any], page_url: str) -> Dict[str, Any]:
        """Extract job data from HTML container"""
        job_data = {
            'source': config.get('name', 'Unknown'),
            'scraped_at': datetime.now().isoformat(),
            'page_url': page_url
        }
        
        # Extract each field using selectors
        for field, selector in selectors.items():
            if field == 'job_container':
                continue
                
            try:
                element = container.select_one(selector)
                if element:
                    if field == 'url':
                        href = element.get('href', '')
                        if href:
                            job_data[field] = urljoin(config['base_url'], href)
                    else:
                        job_data[field] = element.get_text(strip=True)
            except Exception as e:
                logger.debug(f"Error extracting {field}: {e}")
                job_data[field] = None
        
        return job_data
    
    def _extract_rss_job_data(self, entry, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract job data from RSS entry"""
        return {
            'title': getattr(entry, 'title', ''),
            'company': getattr(entry, 'author', ''),
            'description': getattr(entry, 'summary', ''),
            'url': getattr(entry, 'link', ''),
            'posted_date': getattr(entry, 'published', ''),
            'source': config.get('name', 'Unknown'),
            'scraped_at': datetime.now().isoformat()
        }
    
    def _build_search_url(self, config: Dict[str, Any], 
                         query: str, location: str, page: int) -> str:
        """Build search URL for the given parameters"""
        template = config.get('search_url_template', '')
        
        # Handle different pagination types
        pagination_type = config.get('pagination_type', 'page_number')
        if pagination_type == 'offset':
            items_per_page = config.get('items_per_page', 20)
            page_param = (page - 1) * items_per_page
        else:
            page_param = page
        
        return template.format(
            query=query.replace(' ', '+'),
            location=location.replace(' ', '+'),
            page=page_param
        )
    
    def _is_quality_job(self, job_data: Dict[str, Any], 
                       config: Dict[str, Any]) -> bool:
        """Check if job meets quality threshold"""
        quality_threshold = config.get('quality_threshold', 0.7)
        
        # Calculate quality score based on available fields
        score = 0.0
        total_fields = 5  # title, company, description, url, location
        
        if job_data.get('title'):
            score += 0.3
        if job_data.get('company'):
            score += 0.2
        if job_data.get('description'):
            score += 0.2
        if job_data.get('url'):
            score += 0.2
        if job_data.get('location'):
            score += 0.1
        
        return score >= quality_threshold
    
    def _generate_job_hash(self, job_data: Dict[str, Any]) -> str:
        """Generate hash for job deduplication"""
        key_fields = [
            job_data.get('title', ''),
            job_data.get('company', ''),
            job_data.get('url', '')
        ]
        content = '|'.join(key_fields).lower()
        return hashlib.md5(content.encode()).hexdigest()
    
    def _determine_scraping_status(self, jobs: List[Dict[str, Any]], 
                                  errors: List[str], 
                                  pages_scraped: int) -> ScrapingStatus:
        """Determine overall scraping status"""
        if not jobs and errors:
            return ScrapingStatus.FAILED
        elif jobs and not errors:
            return ScrapingStatus.SUCCESS
        elif jobs and errors:
            return ScrapingStatus.PARTIAL
        else:
            return ScrapingStatus.FAILED
    
    async def _scrape_api_endpoint(self, config: Dict[str, Any], 
                                  query: str, location: str, 
                                  max_pages: Optional[int] = None) -> ScrapingResult:
        """Scrape API endpoint (placeholder for future implementation)"""
        # TODO: Implement API scraping for job boards that provide APIs
        return ScrapingResult(
            status=ScrapingStatus.FAILED,
            jobs=[],
            total_found=0,
            pages_scraped=0,
            errors=["API scraping not yet implemented"],
            execution_time=0.0,
            job_board_name=config.get('name', 'Unknown'),
            timestamp=datetime.now()
        )
    
    async def _scrape_hybrid(self, config: Dict[str, Any], 
                            query: str, location: str, 
                            max_pages: Optional[int] = None) -> ScrapingResult:
        """Scrape using hybrid approach (placeholder for future implementation)"""
        # TODO: Implement hybrid scraping (RSS + HTML + API)
        return ScrapingResult(
            status=ScrapingStatus.FAILED,
            jobs=[],
            total_found=0,
            pages_scraped=0,
            errors=["Hybrid scraping not yet implemented"],
            execution_time=0.0,
            job_board_name=config.get('name', 'Unknown'),
            timestamp=datetime.now()
        )

# Utility functions for batch scraping
async def scrape_multiple_job_boards(job_board_names: List[str], 
                                    query: str = "remote", 
                                    location: str = "worldwide",
                                    max_pages: Optional[int] = None) -> List[ScrapingResult]:
    """Scrape multiple job boards concurrently"""
    all_configs = JobBoardConfigs.get_all_configs()
    selected_configs = [config for config in all_configs 
                       if config['name'] in job_board_names and config.get('is_active', True)]
    
    results = []
    
    async with EnhancedScraper() as scraper:
        tasks = []
        for config in selected_configs:
            task = scraper.scrape_job_board(config, query, location, max_pages)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out exceptions and convert to ScrapingResult objects
    valid_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error scraping {selected_configs[i]['name']}: {result}")
            valid_results.append(ScrapingResult(
                status=ScrapingStatus.FAILED,
                jobs=[],
                total_found=0,
                pages_scraped=0,
                errors=[str(result)],
                execution_time=0.0,
                job_board_name=selected_configs[i]['name'],
                timestamp=datetime.now()
            ))
        else:
            valid_results.append(result)
    
    return valid_results

async def scrape_all_active_job_boards(query: str = "remote", 
                                      location: str = "worldwide",
                                      max_pages: Optional[int] = None) -> List[ScrapingResult]:
    """Scrape all active job boards"""
    all_configs = JobBoardConfigs.get_all_configs()
    active_names = [config['name'] for config in all_configs if config.get('is_active', True)]
    
    return await scrape_multiple_job_boards(active_names, query, location, max_pages)