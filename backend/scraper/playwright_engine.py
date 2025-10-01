"""Enhanced Playwright-based web scraping engine with anti-bot detection bypass"""

import asyncio
import random
import time
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
import hashlib
import json

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Error as PlaywrightError

from backend.scraper.utils import RateLimiter, ScrapingUtils, ScrapingResult
from backend.scraper.parsers import JobPostParser, ParsedJobPost
from backend.scraper.exceptions import (
    ScrapingError, RateLimitError, NetworkError, TimeoutError,
    CaptchaError, AuthenticationError, ConfigurationError
)
from backend.core.enums import ScraperSource
from backend.performance.tracker import PerformanceTracker, MetricType

logger = logging.getLogger(__name__)

@dataclass
class PlaywrightConfig:
    """Configuration for Playwright scraping operations"""
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    timeout: int = 30000
    navigation_timeout: int = 30000
    user_agent: Optional[str] = None
    proxy: Optional[Dict[str, str]] = None
    extra_http_headers: Dict[str, str] = field(default_factory=dict)
    ignore_https_errors: bool = False
    slow_mo: int = 0  # Delay between actions in ms
    
    # Anti-bot detection settings
    stealth_mode: bool = True
    rotate_user_agents: bool = True
    random_viewport: bool = True
    simulate_human_behavior: bool = True
    bypass_cloudflare: bool = True
    
    # Performance settings
    disable_images: bool = False
    disable_css: bool = False
    disable_fonts: bool = False
    disable_javascript: bool = False

@dataclass
class ContentDeduplication:
    """Content deduplication configuration and state"""
    enabled: bool = True
    similarity_threshold: float = 0.85
    hash_algorithm: str = 'sha256'
    content_hashes: Dict[str, datetime] = field(default_factory=dict)
    url_hashes: Dict[str, datetime] = field(default_factory=dict)
    cleanup_interval: timedelta = field(default_factory=lambda: timedelta(hours=24))
    
    def is_duplicate_content(self, content: str) -> bool:
        """Check if content is duplicate based on hash"""
        if not self.enabled:
            return False
            
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Clean old hashes
        self._cleanup_old_hashes()
        
        if content_hash in self.content_hashes:
            return True
            
        self.content_hashes[content_hash] = datetime.utcnow()
        return False
    
    def is_duplicate_url(self, url: str) -> bool:
        """Check if URL was already processed"""
        if not self.enabled:
            return False
            
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        
        # Clean old hashes
        self._cleanup_old_hashes()
        
        if url_hash in self.url_hashes:
            return True
            
        self.url_hashes[url_hash] = datetime.utcnow()
        return False
    
    def _cleanup_old_hashes(self):
        """Remove old hashes to prevent memory bloat"""
        cutoff_time = datetime.utcnow() - self.cleanup_interval
        
        # Clean content hashes
        self.content_hashes = {
            h: t for h, t in self.content_hashes.items() 
            if t > cutoff_time
        }
        
        # Clean URL hashes
        self.url_hashes = {
            h: t for h, t in self.url_hashes.items() 
            if t > cutoff_time
        }

class IntelligentRateLimiter(RateLimiter):
    """Enhanced rate limiter with adaptive behavior"""
    
    def __init__(self, base_delay: float = 1.0, max_delay: float = 10.0, 
                 adaptive: bool = True, backoff_factor: float = 1.5):
        super().__init__(1.0 / base_delay)  # Convert delay to requests per second
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.current_delay = base_delay
        self.adaptive = adaptive
        self.backoff_factor = backoff_factor
        self.consecutive_errors = 0
        self.last_success_time = time.time()
    
    async def wait_with_jitter(self):
        """Wait with random jitter to appear more human-like"""
        if self.adaptive:
            self._adjust_delay()
        
        # Add random jitter (±20%)
        jitter = random.uniform(0.8, 1.2)
        delay = self.current_delay * jitter
        
        # Add small random micro-delays to simulate human behavior
        micro_delays = random.randint(1, 3)
        for _ in range(micro_delays):
            await asyncio.sleep(random.uniform(0.1, 0.3))
        
        await asyncio.sleep(delay)
    
    def _adjust_delay(self):
        """Adjust delay based on recent success/failure patterns"""
        current_time = time.time()
        
        # If we've had recent errors, increase delay
        if self.consecutive_errors > 0:
            self.current_delay = min(
                self.max_delay,
                self.current_delay * (self.backoff_factor ** self.consecutive_errors)
            )
        # If we've been successful for a while, decrease delay
        elif current_time - self.last_success_time > 60:  # 1 minute of success
            self.current_delay = max(
                self.base_delay,
                self.current_delay / self.backoff_factor
            )
    
    def record_success(self):
        """Record successful request"""
        self.consecutive_errors = 0
        self.last_success_time = time.time()
    
    def record_error(self):
        """Record failed request"""
        self.consecutive_errors += 1

class PlaywrightScrapingEngine:
    """Enhanced Playwright-based web scraping engine"""
    
    def __init__(self, config: PlaywrightConfig, performance_session_id: str = None):
        self.config = config
        self.performance_tracker = PerformanceTracker()
        self.performance_session_id = performance_session_id
        self.rate_limiter = IntelligentRateLimiter()
        self.deduplication = ContentDeduplication()
        self.job_parser = JobPostParser()
        
        # Browser management
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Anti-bot detection
        self.user_agents = self._get_user_agent_pool()
        self.viewports = self._get_viewport_pool()
        
        # Statistics
        self.stats = {
            'pages_scraped': 0,
            'jobs_found': 0,
            'duplicates_filtered': 0,
            'errors': 0,
            'captchas_detected': 0,
            'rate_limits_hit': 0
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()
    
    async def initialize(self):
        """Initialize Playwright browser and context"""
        try:
            self.playwright = await async_playwright().start()
            
            # Launch browser with anti-detection settings
            launch_options = {
                'headless': self.config.headless,
                'slow_mo': self.config.slow_mo,
                'args': self._get_browser_args()
            }
            
            if self.config.proxy:
                launch_options['proxy'] = self.config.proxy
            
            self.browser = await self.playwright.chromium.launch(**launch_options)
            
            # Create context with stealth settings
            context_options = {
                'viewport': {
                    'width': self.config.viewport_width,
                    'height': self.config.viewport_height
                },
                'user_agent': self._get_random_user_agent(),
                'extra_http_headers': self.config.extra_http_headers,
                'ignore_https_errors': self.config.ignore_https_errors
            }
            
            self.context = await self.browser.new_context(**context_options)
            
            # Apply stealth techniques
            if self.config.stealth_mode:
                await self._apply_stealth_techniques()
            
            # Create page
            self.page = await self.context.new_page()
            
            # Set timeouts
            self.page.set_default_timeout(self.config.timeout)
            self.page.set_default_navigation_timeout(self.config.navigation_timeout)
            
            # Block unnecessary resources for performance
            await self._setup_resource_blocking()
            
            logger.info("Playwright engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Playwright engine: {str(e)}")
            await self.cleanup()
            raise ConfigurationError(f"Playwright initialization failed: {str(e)}")
    
    async def scrape_job_listings(self, urls: List[str], 
                                 source: ScraperSource) -> List[ParsedJobPost]:
        """Scrape job listings from multiple URLs"""
        all_jobs = []
        
        for url in urls:
            try:
                # Check for duplicate URL
                if self.deduplication.is_duplicate_url(url):
                    logger.info(f"Skipping duplicate URL: {url}")
                    self.stats['duplicates_filtered'] += 1
                    continue
                
                # Rate limiting with jitter
                await self.rate_limiter.wait_with_jitter()
                
                # Scrape single page
                jobs = await self._scrape_single_page(url, source)
                all_jobs.extend(jobs)
                
                self.rate_limiter.record_success()
                self.stats['pages_scraped'] += 1
                
            except Exception as e:
                logger.error(f"Error scraping {url}: {str(e)}")
                self.rate_limiter.record_error()
                self.stats['errors'] += 1
                
                # Handle specific error types
                if "captcha" in str(e).lower():
                    self.stats['captchas_detected'] += 1
                    await self._handle_captcha_detection()
                elif "rate limit" in str(e).lower():
                    self.stats['rate_limits_hit'] += 1
                    await self._handle_rate_limit()
        
        return all_jobs
    
    async def _scrape_single_page(self, url: str, source: ScraperSource) -> List[ParsedJobPost]:
        """Scrape a single page for job listings"""
        try:
            # Navigate with retry logic
            await self._navigate_with_retry(url)
            
            # Wait for content to load
            await self._wait_for_content_load(source)
            
            # Extract job data
            job_elements = await self._extract_job_elements(source)
            
            # Parse jobs
            jobs = []
            for element in job_elements:
                try:
                    job_data = await self._extract_job_data(element, source, url)
                    
                    # Check for duplicate content
                    if self.deduplication.is_duplicate_content(job_data.get('description', '')):
                        self.stats['duplicates_filtered'] += 1
                        continue
                    
                    # Parse job post
                    parsed_job = self.job_parser.parse_job_post(job_data)
                    if parsed_job:
                        jobs.append(parsed_job)
                        self.stats['jobs_found'] += 1
                        
                except Exception as e:
                    logger.warning(f"Error parsing job element: {str(e)}")
                    continue
            
            return jobs
            
        except PlaywrightTimeoutError:
            raise TimeoutError(f"Timeout while loading {url}")
        except PlaywrightError as e:
            if "net::ERR_BLOCKED_BY_CLIENT" in str(e):
                raise CaptchaError(f"Request blocked (possible CAPTCHA): {url}")
            raise NetworkError(f"Network error: {str(e)}")
    
    async def _navigate_with_retry(self, url: str, max_retries: int = 3):
        """Navigate to URL with retry logic and human-like behavior"""
        for attempt in range(max_retries):
            try:
                # Randomize viewport if enabled
                if self.config.random_viewport:
                    await self._randomize_viewport()
                
                # Simulate human-like navigation
                if self.config.simulate_human_behavior and attempt > 0:
                    await self._simulate_human_behavior()
                
                # Navigate to page
                response = await self.page.goto(url, wait_until='domcontentloaded')
                
                if response and response.status >= 400:
                    raise NetworkError(f"HTTP {response.status} for {url}")
                
                return response
                
            except PlaywrightTimeoutError:
                if attempt == max_retries - 1:
                    raise TimeoutError(f"Failed to load {url} after {max_retries} attempts")
                
                # Wait before retry with exponential backoff
                wait_time = (2 ** attempt) + random.uniform(1, 3)
                await asyncio.sleep(wait_time)
    
    async def _wait_for_content_load(self, source: ScraperSource):
        """Wait for page content to fully load based on source"""
        # Source-specific selectors for content readiness
        selectors = {
            ScraperSource.INDEED: '[data-jk]',
            ScraperSource.LINKEDIN: '.job-search-card',
            ScraperSource.GLASSDOOR: '[data-test="job-link"]',
            ScraperSource.REMOTE_OK: '.job',
            ScraperSource.WE_WORK_REMOTELY: '.feature'
        }
        
        selector = selectors.get(source, '.job, [class*="job"], [data-job]')
        
        try:
            # Wait for at least one job element to appear
            await self.page.wait_for_selector(selector, timeout=10000)
            
            # Additional wait for dynamic content
            await asyncio.sleep(random.uniform(1, 3))
            
            # Check for infinite scroll or pagination
            await self._handle_dynamic_content()
            
        except PlaywrightTimeoutError:
            logger.warning(f"Content selector '{selector}' not found, proceeding anyway")
    
    async def _extract_job_elements(self, source: ScraperSource) -> List[Any]:
        """Extract job elements from the page"""
        selectors = {
            ScraperSource.INDEED: '[data-jk]',
            ScraperSource.LINKEDIN: '.job-search-card',
            ScraperSource.GLASSDOOR: '[data-test="job-link"]',
            ScraperSource.REMOTE_OK: '.job',
            ScraperSource.WE_WORK_REMOTELY: '.feature'
        }
        
        selector = selectors.get(source, '.job, [class*="job"], [data-job]')
        
        try:
            elements = await self.page.query_selector_all(selector)
            logger.info(f"Found {len(elements)} job elements with selector '{selector}'")
            return elements
        except Exception as e:
            logger.error(f"Error extracting job elements: {str(e)}")
            return []
    
    async def _extract_job_data(self, element: Any, source: ScraperSource, 
                               page_url: str) -> Dict[str, Any]:
        """Extract job data from a single element"""
        try:
            # Source-specific extraction logic
            if source == ScraperSource.INDEED:
                return await self._extract_indeed_job(element, page_url)
            elif source == ScraperSource.LINKEDIN:
                return await self._extract_linkedin_job(element, page_url)
            elif source == ScraperSource.GLASSDOOR:
                return await self._extract_glassdoor_job(element, page_url)
            elif source == ScraperSource.REMOTE_OK:
                return await self._extract_remote_ok_job(element, page_url)
            elif source == ScraperSource.WE_WORK_REMOTELY:
                return await self._extract_wwr_job(element, page_url)
            else:
                return await self._extract_generic_job(element, page_url)
                
        except Exception as e:
            logger.error(f"Error extracting job data: {str(e)}")
            return {}
    
    async def _extract_indeed_job(self, element: Any, page_url: str) -> Dict[str, Any]:
        """Extract job data from Indeed job element"""
        try:
            title_elem = await element.query_selector('h2 a span[title]')
            title = await title_elem.get_attribute('title') if title_elem else None
            
            company_elem = await element.query_selector('[data-testid="company-name"]')
            company = await company_elem.inner_text() if company_elem else None
            
            location_elem = await element.query_selector('[data-testid="job-location"]')
            location = await location_elem.inner_text() if location_elem else None
            
            salary_elem = await element.query_selector('[data-testid="attribute_snippet_testid"]')
            salary = await salary_elem.inner_text() if salary_elem else None
            
            link_elem = await element.query_selector('h2 a')
            job_url = await link_elem.get_attribute('href') if link_elem else None
            if job_url:
                job_url = urljoin(page_url, job_url)
            
            description_elem = await element.query_selector('.slider_container .slider_item')
            description = await description_elem.inner_text() if description_elem else None
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'salary': salary,
                'url': job_url,
                'description': description,
                'source': 'indeed',
                'scraped_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error extracting Indeed job: {str(e)}")
            return {}
    
    async def _extract_linkedin_job(self, element: Any, page_url: str) -> Dict[str, Any]:
        """Extract job data from LinkedIn job element"""
        # Similar implementation for LinkedIn
        # ... (implementation details)
        return {}
    
    async def _extract_glassdoor_job(self, element: Any, page_url: str) -> Dict[str, Any]:
        """Extract job data from Glassdoor job element"""
        # Similar implementation for Glassdoor
        # ... (implementation details)
        return {}
    
    async def _extract_remote_ok_job(self, element: Any, page_url: str) -> Dict[str, Any]:
        """Extract job data from Remote OK job element"""
        # Similar implementation for Remote OK
        # ... (implementation details)
        return {}
    
    async def _extract_wwr_job(self, element: Any, page_url: str) -> Dict[str, Any]:
        """Extract job data from We Work Remotely job element"""
        # Similar implementation for WWR
        # ... (implementation details)
        return {}
    
    async def _extract_generic_job(self, element: Any, page_url: str) -> Dict[str, Any]:
        """Generic job data extraction for unknown sources"""
        try:
            # Try common selectors
            title = await self._safe_extract_text(element, 'h1, h2, h3, .title, [class*="title"]')
            company = await self._safe_extract_text(element, '.company, [class*="company"]')
            location = await self._safe_extract_text(element, '.location, [class*="location"]')
            description = await self._safe_extract_text(element, '.description, [class*="description"]')
            
            # Try to find job URL
            link_elem = await element.query_selector('a')
            job_url = await link_elem.get_attribute('href') if link_elem else None
            if job_url:
                job_url = urljoin(page_url, job_url)
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'description': description,
                'url': job_url,
                'source': 'generic',
                'scraped_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error extracting generic job: {str(e)}")
            return {}
    
    async def _safe_extract_text(self, element: Any, selector: str) -> Optional[str]:
        """Safely extract text from element using selector"""
        try:
            elem = await element.query_selector(selector)
            if elem:
                text = await elem.inner_text()
                return text.strip() if text else None
        except Exception:
            pass
        return None
    
    async def _handle_dynamic_content(self):
        """Handle infinite scroll and dynamic content loading"""
        try:
            # Check for "Load More" buttons
            load_more_selectors = [
                'button[class*="load"]',
                'button[class*="more"]',
                '.load-more',
                '[data-test*="load"]'
            ]
            
            for selector in load_more_selectors:
                button = await self.page.query_selector(selector)
                if button:
                    await button.click()
                    await asyncio.sleep(random.uniform(2, 4))
                    break
            
            # Try infinite scroll
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(random.uniform(1, 2))
            
        except Exception as e:
            logger.debug(f"Dynamic content handling failed: {str(e)}")
    
    async def _apply_stealth_techniques(self):
        """Apply various stealth techniques to avoid detection"""
        try:
            # Remove webdriver property
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            # Mock plugins
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """)
            
            # Mock languages
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            """)
            
            # Mock permissions
            await self.context.add_init_script("""
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            
        except Exception as e:
            logger.warning(f"Failed to apply stealth techniques: {str(e)}")
    
    async def _setup_resource_blocking(self):
        """Block unnecessary resources to improve performance"""
        try:
            blocked_resources = []
            
            if self.config.disable_images:
                blocked_resources.extend(['image', 'imageset'])
            if self.config.disable_css:
                blocked_resources.append('stylesheet')
            if self.config.disable_fonts:
                blocked_resources.append('font')
            
            if blocked_resources:
                await self.page.route('**/*', lambda route: (
                    route.abort() if route.request.resource_type in blocked_resources 
                    else route.continue_()
                ))
                
        except Exception as e:
            logger.warning(f"Failed to setup resource blocking: {str(e)}")
    
    async def _randomize_viewport(self):
        """Randomize viewport size to appear more human-like"""
        try:
            viewport = random.choice(self.viewports)
            await self.page.set_viewport_size(viewport)
        except Exception as e:
            logger.debug(f"Failed to randomize viewport: {str(e)}")
    
    async def _simulate_human_behavior(self):
        """Simulate human-like behavior patterns"""
        try:
            # Random mouse movements
            for _ in range(random.randint(1, 3)):
                x = random.randint(100, 800)
                y = random.randint(100, 600)
                await self.page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.5))
            
            # Random scrolling
            scroll_distance = random.randint(100, 500)
            await self.page.evaluate(f'window.scrollBy(0, {scroll_distance})')
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
        except Exception as e:
            logger.debug(f"Failed to simulate human behavior: {str(e)}")
    
    async def _handle_captcha_detection(self):
        """Handle CAPTCHA detection"""
        logger.warning("CAPTCHA detected, implementing countermeasures")
        
        # Rotate user agent
        if self.config.rotate_user_agents:
            new_ua = self._get_random_user_agent()
            await self.page.set_extra_http_headers({'User-Agent': new_ua})
        
        # Increase delays
        self.rate_limiter.current_delay *= 2
        
        # Wait longer before next request
        await asyncio.sleep(random.uniform(30, 60))
    
    async def _handle_rate_limit(self):
        """Handle rate limiting"""
        logger.warning("Rate limit detected, backing off")
        
        # Exponential backoff
        backoff_time = min(300, 30 * (2 ** self.stats['rate_limits_hit']))
        await asyncio.sleep(backoff_time + random.uniform(0, 30))
    
    def _get_browser_args(self) -> List[str]:
        """Get browser launch arguments for anti-detection"""
        args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
        ]
        
        if self.config.stealth_mode:
            args.extend([
                '--disable-blink-features=AutomationControlled',
                '--exclude-switches=enable-automation',
                '--disable-extensions-except=',
                '--disable-plugins-discovery',
                '--disable-default-apps'
            ])
        
        return args
    
    def _get_user_agent_pool(self) -> List[str]:
        """Get pool of realistic user agents"""
        return [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]
    
    def _get_viewport_pool(self) -> List[Dict[str, int]]:
        """Get pool of realistic viewport sizes"""
        return [
            {'width': 1920, 'height': 1080},
            {'width': 1366, 'height': 768},
            {'width': 1536, 'height': 864},
            {'width': 1440, 'height': 900},
            {'width': 1280, 'height': 720},
        ]
    
    def _get_random_user_agent(self) -> str:
        """Get random user agent from pool"""
        if self.config.user_agent:
            return self.config.user_agent
        return random.choice(self.user_agents)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scraping statistics"""
        return {
            **self.stats,
            'rate_limiter_stats': self.rate_limiter.get_stats(),
            'deduplication_stats': {
                'content_hashes': len(self.deduplication.content_hashes),
                'url_hashes': len(self.deduplication.url_hashes)
            }
        }
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
                
            logger.info("Playwright engine cleaned up successfully")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")