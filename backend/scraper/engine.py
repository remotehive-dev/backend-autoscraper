"""Web scraping engine for RemoteHive job scraping"""

import time
import logging
import asyncio
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, parse_qs
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

from backend.scraper.utils import RateLimiter, ScrapingUtils, ScrapingResult
from backend.scraper.parsers import JobPostParser, ParsedJobPost
from backend.scraper.exceptions import (
    ScrapingError, RateLimitError, NetworkError, TimeoutError,
    CaptchaError, AuthenticationError, ConfigurationError
)
from backend.scraper.playwright_engine import PlaywrightScrapingEngine, PlaywrightConfig
from backend.scraper.config import get_scraping_config, EnhancedScrapingConfig, ScrapingMode
from backend.core.enums import ScraperSource
from backend.performance.tracker import PerformanceTracker, MetricType

logger = logging.getLogger(__name__)

@dataclass
class ScrapingConfig:
    """Configuration for web scraping operations"""
    source: ScraperSource
    base_url: str
    max_pages: int = 10
    rate_limit_delay: float = 1.0
    request_timeout: float = 30.0
    max_retries: int = 3
    user_agent: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    proxy: Optional[str] = None
    verify_ssl: bool = True
    follow_redirects: bool = True
    parsing_rules: Dict[str, Any] = field(default_factory=dict)
    search_query: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    date_posted: Optional[str] = None  # 'today', 'week', 'month'
    remote_only: bool = False
    # Playwright-specific settings
    use_playwright: bool = False
    headless: bool = True
    enable_stealth: bool = True
    enable_deduplication: bool = True
    intelligent_rate_limiting: bool = True

@dataclass
class ScrapingSession:
    """Container for scraping session results"""
    session_id: str
    config: ScrapingConfig
    start_time: datetime
    end_time: Optional[datetime] = None
    pages_scraped: int = 0
    jobs_found: int = 0
    jobs_parsed: int = 0
    jobs_valid: int = 0
    errors: List[str] = field(default_factory=list)
    raw_jobs: List[Dict[str, Any]] = field(default_factory=list)
    parsed_jobs: List[ParsedJobPost] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    
    @property
    def duration(self) -> Optional[float]:
        """Get session duration in seconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def success_rate(self) -> float:
        """Get success rate of job parsing"""
        if self.jobs_found == 0:
            return 0.0
        return self.jobs_valid / self.jobs_found

class WebScrapingEngine:
    """Main web scraping engine for job boards"""
    
    def __init__(self, config: ScrapingConfig, performance_session_id: str = None, enhanced_config: EnhancedScrapingConfig = None):
        self.config = config
        self.performance_session_id = performance_session_id
        self.enhanced_config = enhanced_config or get_scraping_config()
        
        # Initialize engines based on configuration
        self.playwright_engine = None
        self.scraping_mode = self.enhanced_config.scraping_mode
        
        # Always initialize Playwright engine if mode requires it
        if (self.scraping_mode in [ScrapingMode.PLAYWRIGHT, ScrapingMode.HYBRID] or 
            config.use_playwright):
            playwright_config = PlaywrightConfig(
                headless=self.enhanced_config.playwright.headless,
                timeout=self.enhanced_config.playwright.timeout,
                user_agent=self.enhanced_config.playwright.user_agent or config.user_agent,
                proxy=self.enhanced_config.playwright.proxy or config.proxy,
                stealth_mode=self.enhanced_config.playwright.enable_stealth,
                disable_images=not self.enhanced_config.playwright.enable_images
            )
            self.playwright_engine = PlaywrightScrapingEngine(playwright_config, performance_session_id)
            self.session = None
        else:
            self.session = self._create_session()
            self.playwright_engine = None
            
        # Always create session for requests-based scraping in hybrid mode
        if self.scraping_mode in [ScrapingMode.REQUESTS, ScrapingMode.HYBRID] and not self.session:
            self.session = self._create_session()
            
        self.rate_limiter = RateLimiter(1.0 / config.rate_limit_delay)
        self.parser = JobPostParser(
            parsing_rules=config.parsing_rules,
            base_url=config.base_url,
            source=config.source
        )
        
        # Performance tracking
        if performance_session_id:
            self.performance_tracker = PerformanceTracker()
        else:
            self.performance_tracker = None
    
    def _create_session(self) -> requests.Session:
        """Create configured requests session"""
        session = requests.Session()
        
        # Set headers
        default_headers = {
            'User-Agent': self.config.user_agent or ScrapingUtils.generate_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        default_headers.update(self.config.headers)
        session.headers.update(default_headers)
        
        # Set cookies
        if self.config.cookies:
            session.cookies.update(self.config.cookies)
        
        # Configure retries
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set proxy
        if self.config.proxy:
            session.proxies = {
                'http': self.config.proxy,
                'https': self.config.proxy
            }
        
        return session
    
    async def scrape_jobs(self, search_query: str = None, location: str = None, 
                   job_type: str = None) -> ScrapingSession:
        """Main method to scrape jobs from the configured source with intelligent engine selection"""
        session_id = ScrapingUtils.generate_request_id(self.config.base_url)
        scraping_session = ScrapingSession(
            session_id=session_id,
            config=self.config,
            start_time=datetime.utcnow()
        )
        
        # Determine which engine to use based on configuration and URL
        use_playwright = self._should_use_playwright_for_url(self.config.base_url)
        
        logger.info(f"Starting scraping session {session_id} for {self.config.source.value} (Engine: {'Playwright' if use_playwright else 'Requests'})")
        
        # Record performance metrics
        if self.performance_tracker and self.performance_session_id:
            self.performance_tracker.record_metric(
                self.performance_session_id, "scraping_session_started", 1, MetricType.COUNTER
            )
        
        try:
            if use_playwright and self.playwright_engine:
                # Use Playwright-based scraping
                result = await self._scrape_with_playwright(
                    scraping_session,
                    search_query or self.config.search_query,
                    location or self.config.location,
                    job_type or self.config.job_type
                )
                scraping_session = result
            elif self.session:
                # Use traditional requests-based scraping
                self._scrape_with_requests(scraping_session, search_query, location, job_type)
            else:
                raise ScrapingError("No suitable scraping engine available")
            
            # Mark as successful if we got some valid jobs
            scraping_session.success = scraping_session.jobs_valid > 0
            
        except Exception as e:
            error_msg = f"Scraping session failed: {str(e)}"
            logger.error(error_msg)
            scraping_session.errors.append(error_msg)
            scraping_session.success = False
        
        finally:
            scraping_session.end_time = datetime.utcnow()
            
            # Record final performance metrics
            if self.performance_tracker and self.performance_session_id:
                self.performance_tracker.record_metric(
                    self.performance_session_id, "scraping_session_completed", 1, MetricType.COUNTER
                )
                self.performance_tracker.record_metric(
                    self.performance_session_id, "jobs_scraped_total", scraping_session.jobs_found, MetricType.COUNTER
                )
                self.performance_tracker.record_metric(
                    self.performance_session_id, "jobs_valid_total", scraping_session.jobs_valid, MetricType.COUNTER
                )
            
            logger.info(
                f"Scraping session {session_id} completed. "
                f"Pages: {scraping_session.pages_scraped}, "
                f"Jobs found: {scraping_session.jobs_found}, "
                f"Valid jobs: {scraping_session.jobs_valid}, "
                f"Duration: {scraping_session.duration:.2f}s"
            )
        
        return scraping_session
    
    def _should_use_playwright_for_url(self, url: str) -> bool:
        """Determine if Playwright should be used for a specific URL"""
        if self.scraping_mode == ScrapingMode.PLAYWRIGHT:
            return True
        elif self.scraping_mode == ScrapingMode.REQUESTS:
            return False
        else:  # HYBRID mode
            return self.enhanced_config.should_use_playwright(url)
    
    async def _scrape_with_playwright(self, scraping_session: ScrapingSession, 
                                    search_query: str = None, location: str = None, 
                                    job_type: str = None) -> ScrapingSession:
        """Scrape jobs using Playwright engine"""
        try:
            # Build search URLs
            search_urls = self._build_search_urls(search_query, location, job_type)
            
            if not search_urls:
                raise ConfigurationError("No search URLs could be generated")
            
            # Initialize Playwright engine
            await self.playwright_engine.initialize()
            
            # Scrape each search URL
            for search_url in search_urls:
                try:
                    jobs = await self.playwright_engine.scrape_job_listings(
                        [search_url], 
                        self.config.source
                    )
                    
                    # Convert Playwright results to our format
                    for job in jobs:
                        if isinstance(job, dict):
                            scraping_session.raw_jobs.append(job)
                        else:
                            # Convert ParsedJobPost to dict format
                            job_dict = {
                                'title': job.title,
                                'company': job.company,
                                'location': job.location,
                                'description': job.description,
                                'job_url': job.source_url,
                                'salary': f"{job.salary_min}-{job.salary_max}" if job.salary_min and job.salary_max else None,
                                'source_url': search_url,
                                'scraped_at': datetime.utcnow().isoformat()
                            }
                            scraping_session.raw_jobs.append(job_dict)
                        scraping_session.jobs_found += 1
                    
                    scraping_session.pages_scraped += min(self.config.max_pages, len(jobs) // 10 + 1)
                    
                except Exception as e:
                    error_msg = f"Failed to scrape {search_url} with Playwright: {str(e)}"
                    logger.error(error_msg)
                    scraping_session.errors.append(error_msg)
                    continue
            
            # Parse raw jobs
            self._parse_raw_jobs(scraping_session)
            
        finally:
            # Clean up Playwright resources
            if self.playwright_engine:
                await self.playwright_engine.cleanup()
        
        return scraping_session
    
    def _scrape_with_requests(self, scraping_session: ScrapingSession, 
                            search_query: str = None, location: str = None, 
                            job_type: str = None):
        """Scrape jobs using traditional requests"""
        # Build search URLs
        search_urls = self._build_search_urls(
            search_query or self.config.search_query,
            location or self.config.location,
            job_type or self.config.job_type
        )
        
        if not search_urls:
            raise ConfigurationError("No search URLs could be generated")
        
        # Scrape each search URL
        for search_url in search_urls:
            try:
                self._scrape_search_results(scraping_session, search_url)
            except Exception as e:
                error_msg = f"Failed to scrape {search_url}: {str(e)}"
                logger.error(error_msg)
                scraping_session.errors.append(error_msg)
                continue
        
        # Parse raw jobs
        self._parse_raw_jobs(scraping_session)
    
    def _build_search_urls(self, search_query: str = None, location: str = None, 
                          job_type: str = None) -> List[str]:
        """Build search URLs based on configuration and parameters"""
        urls = []
        base_url = self.config.base_url
        
        # Source-specific URL building
        if self.config.source == ScraperSource.INDEED:
            urls = self._build_indeed_urls(base_url, search_query, location, job_type)
        elif self.config.source == ScraperSource.LINKEDIN:
            urls = self._build_linkedin_urls(base_url, search_query, location, job_type)
        elif self.config.source == ScraperSource.GLASSDOOR:
            urls = self._build_glassdoor_urls(base_url, search_query, location, job_type)
        elif self.config.source == ScraperSource.REMOTE_OK:
            urls = self._build_remote_ok_urls(base_url, search_query, location, job_type)
        elif self.config.source == ScraperSource.WE_WORK_REMOTELY:
            urls = self._build_wwr_urls(base_url, search_query, location, job_type)
        else:
            # Generic URL building
            urls = [base_url]
        
        return urls
    
    def _build_indeed_urls(self, base_url: str, query: str = None, 
                          location: str = None, job_type: str = None) -> List[str]:
        """Build Indeed search URLs"""
        urls = []
        
        # Indeed search parameters
        params = {}
        if query:
            params['q'] = query
        if location:
            params['l'] = location
        if job_type:
            params['jt'] = job_type
        if self.config.remote_only:
            params['remotejob'] = '1'
        if self.config.salary_min:
            params['salary'] = f"${self.config.salary_min}+"
        
        # Build URL with parameters
        if params:
            param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            search_url = f"{base_url}/jobs?{param_string}"
        else:
            search_url = f"{base_url}/jobs"
        
        urls.append(search_url)
        return urls
    
    def _build_linkedin_urls(self, base_url: str, query: str = None, 
                            location: str = None, job_type: str = None) -> List[str]:
        """Build LinkedIn search URLs"""
        urls = []
        
        # LinkedIn job search parameters
        params = {}
        if query:
            params['keywords'] = query
        if location:
            params['location'] = location
        if self.config.remote_only:
            params['f_WT'] = '2'  # Remote work filter
        
        # Build URL
        if params:
            param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            search_url = f"{base_url}/jobs/search/?{param_string}"
        else:
            search_url = f"{base_url}/jobs/search/"
        
        urls.append(search_url)
        return urls
    
    def _build_glassdoor_urls(self, base_url: str, query: str = None, 
                             location: str = None, job_type: str = None) -> List[str]:
        """Build Glassdoor search URLs"""
        urls = []
        
        # Glassdoor parameters
        params = {}
        if query:
            params['sc.keyword'] = query
        if location:
            params['locT'] = 'C'
            params['locId'] = location
        
        # Build URL
        if params:
            param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            search_url = f"{base_url}/Job/jobs.htm?{param_string}"
        else:
            search_url = f"{base_url}/Job/jobs.htm"
        
        urls.append(search_url)
        return urls
    
    def _build_remote_ok_urls(self, base_url: str, query: str = None, 
                             location: str = None, job_type: str = None) -> List[str]:
        """Build Remote OK search URLs"""
        urls = []
        
        # Remote OK is simpler - just categories
        if query:
            # Try to map query to categories
            query_lower = query.lower()
            if 'developer' in query_lower or 'engineer' in query_lower:
                urls.append(f"{base_url}/remote-dev-jobs")
            elif 'design' in query_lower:
                urls.append(f"{base_url}/remote-design-jobs")
            elif 'marketing' in query_lower:
                urls.append(f"{base_url}/remote-marketing-jobs")
            else:
                urls.append(base_url)
        else:
            urls.append(base_url)
        
        return urls
    
    def _build_wwr_urls(self, base_url: str, query: str = None, 
                       location: str = None, job_type: str = None) -> List[str]:
        """Build We Work Remotely search URLs"""
        urls = []
        
        # WWR categories
        categories = []
        if query:
            query_lower = query.lower()
            if 'developer' in query_lower or 'engineer' in query_lower:
                categories.append('2')
            elif 'design' in query_lower:
                categories.append('3')
            elif 'marketing' in query_lower:
                categories.append('7')
        
        if categories:
            for category in categories:
                urls.append(f"{base_url}/categories/{category}")
        else:
            urls.append(f"{base_url}/categories/2")  # Default to programming
        
        return urls
    
    def _scrape_search_results(self, scraping_session: ScrapingSession, search_url: str):
        """Scrape job listings from search results pages"""
        logger.info(f"Scraping search results from: {search_url}")
        
        current_page = 1
        
        while current_page <= self.config.max_pages:
            try:
                # Build page URL
                page_url = self._build_page_url(search_url, current_page)
                
                # Rate limiting
                self.rate_limiter.acquire()
                
                # Make request
                response = self._make_request(page_url)
                
                if not response:
                    break
                
                scraping_session.pages_scraped += 1
                
                # Extract job listings from page
                jobs_on_page = self._extract_jobs_from_page(response.text, page_url)
                
                if not jobs_on_page:
                    logger.info(f"No jobs found on page {current_page}, stopping pagination")
                    break
                
                scraping_session.raw_jobs.extend(jobs_on_page)
                scraping_session.jobs_found += len(jobs_on_page)
                
                logger.info(f"Found {len(jobs_on_page)} jobs on page {current_page}")
                
                # Record performance metrics
                if self.performance_tracker and self.performance_session_id:
                    self.performance_tracker.record_metric(
                        self.performance_session_id, "page_scraped", 1, MetricType.COUNTER
                    )
                    self.performance_tracker.record_metric(
                        self.performance_session_id, "jobs_found_on_page", len(jobs_on_page), MetricType.COUNTER
                    )
                
                current_page += 1
                
                # Add delay between pages
                if current_page <= self.config.max_pages:
                    delay = ScrapingUtils.get_random_delay(self.config.rate_limit_delay, self.config.rate_limit_delay * 2)
                    time.sleep(delay)
                
            except Exception as e:
                error_msg = f"Error scraping page {current_page} of {search_url}: {str(e)}"
                logger.error(error_msg)
                scraping_session.errors.append(error_msg)
                break
    
    def _build_page_url(self, base_search_url: str, page_number: int) -> str:
        """Build URL for specific page number"""
        if page_number == 1:
            return base_search_url
        
        # Source-specific pagination
        if self.config.source == ScraperSource.INDEED:
            start = (page_number - 1) * 10  # Indeed shows 10 jobs per page
            separator = '&' if '?' in base_search_url else '?'
            return f"{base_search_url}{separator}start={start}"
        elif self.config.source == ScraperSource.LINKEDIN:
            start = (page_number - 1) * 25  # LinkedIn shows 25 jobs per page
            separator = '&' if '?' in base_search_url else '?'
            return f"{base_search_url}{separator}start={start}"
        else:
            # Generic pagination
            separator = '&' if '?' in base_search_url else '?'
            return f"{base_search_url}{separator}page={page_number}"
    
    def _make_request(self, url: str) -> Optional[requests.Response]:
        """Make HTTP request with error handling"""
        try:
            logger.debug(f"Making request to: {url}")
            
            response = self.session.get(
                url,
                timeout=self.config.request_timeout,
                verify=self.config.verify_ssl,
                allow_redirects=self.config.follow_redirects
            )
            
            # Check for common error conditions
            if response.status_code == 429:
                raise RateLimitError(f"Rate limited by {urlparse(url).netloc}")
            elif response.status_code == 403:
                # Check for CAPTCHA
                if 'captcha' in response.text.lower() or 'robot' in response.text.lower():
                    raise CaptchaError(f"CAPTCHA detected on {url}")
                else:
                    raise AuthenticationError(f"Access forbidden to {url}")
            elif response.status_code >= 400:
                raise NetworkError(f"HTTP {response.status_code} error for {url}")
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Request timeout for {url}")
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"Connection error for {url}: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise ScrapingError(f"Request failed for {url}: {str(e)}")
    
    def _extract_jobs_from_page(self, html_content: str, page_url: str) -> List[Dict[str, Any]]:
        """Extract job listings from a search results page"""
        jobs = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Source-specific job extraction
            if self.config.source == ScraperSource.INDEED:
                jobs = self._extract_indeed_jobs(soup, page_url)
            elif self.config.source == ScraperSource.LINKEDIN:
                jobs = self._extract_linkedin_jobs(soup, page_url)
            elif self.config.source == ScraperSource.GLASSDOOR:
                jobs = self._extract_glassdoor_jobs(soup, page_url)
            elif self.config.source == ScraperSource.REMOTE_OK:
                jobs = self._extract_remote_ok_jobs(soup, page_url)
            elif self.config.source == ScraperSource.WE_WORK_REMOTELY:
                jobs = self._extract_wwr_jobs(soup, page_url)
            else:
                # Generic extraction using parsing rules
                jobs = self._extract_generic_jobs(soup, page_url)
            
        except Exception as e:
            logger.error(f"Failed to extract jobs from page {page_url}: {str(e)}")
        
        return jobs
    
    def _extract_indeed_jobs(self, soup: BeautifulSoup, page_url: str) -> List[Dict[str, Any]]:
        """Extract jobs from Indeed search results"""
        jobs = []
        
        # Indeed job cards
        job_cards = soup.select('.jobsearch-SerpJobCard, .job_seen_beacon')
        
        for card in job_cards:
            try:
                job_data = {
                    'title': self._safe_extract_text(card, 'h2 a[data-jk], .jobTitle a'),
                    'company': self._safe_extract_text(card, '.companyName'),
                    'location': self._safe_extract_text(card, '.companyLocation'),
                    'summary': self._safe_extract_text(card, '.summary'),
                    'salary': self._safe_extract_text(card, '.salaryText'),
                    'job_url': self._safe_extract_href(card, 'h2 a[data-jk], .jobTitle a'),
                    'source_url': page_url,
                    'scraped_at': datetime.utcnow().isoformat()
                }
                
                # Resolve relative URLs
                if job_data['job_url']:
                    job_data['job_url'] = urljoin(self.config.base_url, job_data['job_url'])
                
                if job_data['title'] and job_data['company']:
                    jobs.append(job_data)
                    
            except Exception as e:
                logger.warning(f"Failed to extract job from Indeed card: {str(e)}")
                continue
        
        return jobs
    
    def _extract_linkedin_jobs(self, soup: BeautifulSoup, page_url: str) -> List[Dict[str, Any]]:
        """Extract jobs from LinkedIn search results"""
        jobs = []
        
        # LinkedIn job cards
        job_cards = soup.select('.jobs-search__results-list li, .job-result-card')
        
        for card in job_cards:
            try:
                job_data = {
                    'title': self._safe_extract_text(card, '.job-result-card__title, h3'),
                    'company': self._safe_extract_text(card, '.job-result-card__subtitle, h4'),
                    'location': self._safe_extract_text(card, '.job-result-card__location'),
                    'summary': self._safe_extract_text(card, '.job-result-card__snippet'),
                    'job_url': self._safe_extract_href(card, 'a'),
                    'source_url': page_url,
                    'scraped_at': datetime.utcnow().isoformat()
                }
                
                # Resolve relative URLs
                if job_data['job_url']:
                    job_data['job_url'] = urljoin(self.config.base_url, job_data['job_url'])
                
                if job_data['title'] and job_data['company']:
                    jobs.append(job_data)
                    
            except Exception as e:
                logger.warning(f"Failed to extract job from LinkedIn card: {str(e)}")
                continue
        
        return jobs
    
    def _extract_glassdoor_jobs(self, soup: BeautifulSoup, page_url: str) -> List[Dict[str, Any]]:
        """Extract jobs from Glassdoor search results"""
        jobs = []
        
        # Glassdoor job listings
        job_cards = soup.select('.react-job-listing, .jobContainer')
        
        for card in job_cards:
            try:
                job_data = {
                    'title': self._safe_extract_text(card, '.jobTitle, .jobLink'),
                    'company': self._safe_extract_text(card, '.employerName'),
                    'location': self._safe_extract_text(card, '.jobLocation'),
                    'salary': self._safe_extract_text(card, '.salaryEstimate'),
                    'job_url': self._safe_extract_href(card, '.jobTitle a, .jobLink'),
                    'source_url': page_url,
                    'scraped_at': datetime.utcnow().isoformat()
                }
                
                # Resolve relative URLs
                if job_data['job_url']:
                    job_data['job_url'] = urljoin(self.config.base_url, job_data['job_url'])
                
                if job_data['title'] and job_data['company']:
                    jobs.append(job_data)
                    
            except Exception as e:
                logger.warning(f"Failed to extract job from Glassdoor card: {str(e)}")
                continue
        
        return jobs
    
    def _extract_remote_ok_jobs(self, soup: BeautifulSoup, page_url: str) -> List[Dict[str, Any]]:
        """Extract jobs from Remote OK"""
        jobs = []
        
        # Remote OK job rows
        job_rows = soup.select('tr.job')
        
        for row in job_rows:
            try:
                job_data = {
                    'title': self._safe_extract_text(row, '.company_and_position h2'),
                    'company': self._safe_extract_text(row, '.company_and_position h3'),
                    'location': 'Remote',  # All jobs on Remote OK are remote
                    'tags': [tag.get_text().strip() for tag in row.select('.tags .tag')],
                    'salary': self._safe_extract_text(row, '.salary'),
                    'job_url': self._safe_extract_href(row, 'a'),
                    'source_url': page_url,
                    'scraped_at': datetime.utcnow().isoformat()
                }
                
                # Resolve relative URLs
                if job_data['job_url']:
                    job_data['job_url'] = urljoin(self.config.base_url, job_data['job_url'])
                
                if job_data['title'] and job_data['company']:
                    jobs.append(job_data)
                    
            except Exception as e:
                logger.warning(f"Failed to extract job from Remote OK row: {str(e)}")
                continue
        
        return jobs
    
    def _extract_wwr_jobs(self, soup: BeautifulSoup, page_url: str) -> List[Dict[str, Any]]:
        """Extract jobs from We Work Remotely"""
        jobs = []
        
        # WWR job listings
        job_listings = soup.select('.jobs li')
        
        for listing in job_listings:
            try:
                job_data = {
                    'title': self._safe_extract_text(listing, '.title'),
                    'company': self._safe_extract_text(listing, '.company'),
                    'location': 'Remote',  # All WWR jobs are remote
                    'region': self._safe_extract_text(listing, '.region'),
                    'job_url': self._safe_extract_href(listing, 'a'),
                    'source_url': page_url,
                    'scraped_at': datetime.utcnow().isoformat()
                }
                
                # Resolve relative URLs
                if job_data['job_url']:
                    job_data['job_url'] = urljoin(self.config.base_url, job_data['job_url'])
                
                if job_data['title'] and job_data['company']:
                    jobs.append(job_data)
                    
            except Exception as e:
                logger.warning(f"Failed to extract job from WWR listing: {str(e)}")
                continue
        
        return jobs
    
    def _extract_generic_jobs(self, soup: BeautifulSoup, page_url: str) -> List[Dict[str, Any]]:
        """Extract jobs using generic parsing rules"""
        jobs = []
        
        # Use parsing rules if available
        if not self.config.parsing_rules:
            return jobs
        
        job_container_selector = self.config.parsing_rules.get('job_container', '.job')
        job_containers = soup.select(job_container_selector)
        
        for container in job_containers:
            try:
                job_data = {
                    'title': self._safe_extract_text(container, self.config.parsing_rules.get('title', '.title')),
                    'company': self._safe_extract_text(container, self.config.parsing_rules.get('company', '.company')),
                    'location': self._safe_extract_text(container, self.config.parsing_rules.get('location', '.location')),
                    'summary': self._safe_extract_text(container, self.config.parsing_rules.get('summary', '.summary')),
                    'salary': self._safe_extract_text(container, self.config.parsing_rules.get('salary', '.salary')),
                    'job_url': self._safe_extract_href(container, self.config.parsing_rules.get('job_url', 'a')),
                    'source_url': page_url,
                    'scraped_at': datetime.utcnow().isoformat()
                }
                
                # Resolve relative URLs
                if job_data['job_url']:
                    job_data['job_url'] = urljoin(self.config.base_url, job_data['job_url'])
                
                if job_data['title'] and job_data['company']:
                    jobs.append(job_data)
                    
            except Exception as e:
                logger.warning(f"Failed to extract job from generic container: {str(e)}")
                continue
        
        return jobs
    
    def _safe_extract_text(self, element, selector: str) -> Optional[str]:
        """Safely extract text from element using selector"""
        try:
            found = element.select_one(selector)
            if found:
                return ScrapingUtils.clean_text(found.get_text())
        except Exception:
            pass
        return None
    
    def _safe_extract_href(self, element, selector: str) -> Optional[str]:
        """Safely extract href attribute from element using selector"""
        try:
            found = element.select_one(selector)
            if found:
                return found.get('href')
        except Exception:
            pass
        return None
    
    def _parse_raw_jobs(self, scraping_session: ScrapingSession):
        """Parse raw job data into structured format"""
        logger.info(f"Parsing {len(scraping_session.raw_jobs)} raw jobs")
        
        for raw_job in scraping_session.raw_jobs:
            try:
                # For jobs that have detailed URLs, fetch full content
                if raw_job.get('job_url'):
                    full_job_content = self._fetch_job_details(raw_job['job_url'])
                    if full_job_content:
                        parsed_job = self.parser.parse_job(full_job_content, raw_job['job_url'])
                    else:
                        # Fallback to parsing from summary data
                        parsed_job = self._parse_job_from_summary(raw_job)
                else:
                    parsed_job = self._parse_job_from_summary(raw_job)
                
                if parsed_job and parsed_job.is_valid():
                    scraping_session.parsed_jobs.append(parsed_job)
                    scraping_session.jobs_valid += 1
                
                scraping_session.jobs_parsed += 1
                
            except Exception as e:
                logger.warning(f"Failed to parse job: {str(e)}")
                continue
        
        logger.info(f"Successfully parsed {scraping_session.jobs_valid} valid jobs out of {scraping_session.jobs_parsed}")
    
    def _fetch_job_details(self, job_url: str) -> Optional[str]:
        """Fetch detailed job content from job URL"""
        try:
            # Rate limiting
            self.rate_limiter.acquire()
            
            response = self._make_request(job_url)
            if response:
                return response.text
        except Exception as e:
            logger.warning(f"Failed to fetch job details from {job_url}: {str(e)}")
        
        return None
    
    def _parse_job_from_summary(self, raw_job: Dict[str, Any]) -> Optional[ParsedJobPost]:
        """Parse job from summary data when full content is not available"""
        try:
            job = ParsedJobPost()
            
            # Map raw job data to parsed job fields
            job.title = raw_job.get('title')
            job.company = raw_job.get('company')
            job.location = raw_job.get('location')
            job.description = raw_job.get('summary') or raw_job.get('description')
            job.source_url = raw_job.get('job_url')
            job.source_platform = self.config.source.value
            
            # Parse salary if available
            if raw_job.get('salary'):
                salary_info = ScrapingUtils.parse_salary_range(raw_job['salary'])
                job.salary_min = salary_info.get('min_salary')
                job.salary_max = salary_info.get('max_salary')
                job.salary_currency = salary_info.get('currency')
            
            # Detect job type and experience level
            combined_text = f"{job.title or ''} {job.description or ''}"
            job.job_type = ScrapingUtils.detect_job_type(combined_text)
            job.experience_level = ScrapingUtils.extract_experience_level(combined_text)
            
            # Set remote friendly based on location or description
            if job.location:
                job.remote_friendly = 'remote' in job.location.lower()
            
            # Set tags from raw data
            if raw_job.get('tags'):
                job.tags = raw_job['tags']
            
            # Set confidence score (lower for summary-only parsing)
            job.confidence_score = 0.6 if job.is_valid() else 0.3
            
            return job
            
        except Exception as e:
            logger.warning(f"Failed to parse job from summary: {str(e)}")
            return None
    
    def close(self):
        """Clean up resources"""
        if self.session:
            self.session.close()
        if self.playwright_engine:
            asyncio.run(self.playwright_engine.cleanup())