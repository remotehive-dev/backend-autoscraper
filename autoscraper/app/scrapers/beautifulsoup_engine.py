import asyncio
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import logging
import re
import random
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

from .multi_engine_framework import BaseJobScraper
from .types import ScrapingEngine, JobData
from ..models.mongodb_models import JobBoard
from ..ai.decision_engine import get_ai_decision_engine

class BeautifulSoupJobScraper(BaseJobScraper):
    """BeautifulSoup-based job scraper for simple HTML parsing"""
    
    def __init__(self):
        super().__init__(ScrapingEngine.BEAUTIFULSOUP)
        self.session = None
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        self.ai_decision_engine = get_ai_decision_engine()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': random.choice(self.user_agents),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
        
        return self.session
    
    async def test_connection(self, url: str) -> bool:
        """Test if we can connect to the URL"""
        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"BeautifulSoup connection test failed for {url}: {e}")
            return False
    
    async def scrape_jobs(self, job_board: JobBoard, selectors: Dict[str, str], **kwargs) -> List[JobData]:
        """Scrape jobs using BeautifulSoup"""
        max_jobs = kwargs.get('max_jobs', 100)
        jobs = []
        
        try:
            # Get job listing pages
            job_urls = await self._get_job_urls(job_board, max_jobs)
            
            if not job_urls:
                logger.warning(f"No job URLs found for {job_board.name}")
                return jobs
            
            # Scrape individual job pages
            semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
            tasks = []
            
            for job_url in job_urls[:max_jobs]:
                task = self._scrape_single_job(semaphore, job_url, job_board, selectors)
                tasks.append(task)
            
            # Execute all tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, JobData):
                    jobs.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Job scraping failed: {result}")
            
            logger.info(f"BeautifulSoup scraped {len(jobs)} jobs from {job_board.name}")
            return jobs
            
        except Exception as e:
            logger.error(f"BeautifulSoup scraping failed for {job_board.name}: {e}")
            return jobs
    
    async def _get_job_urls(self, job_board: JobBoard, max_jobs: int) -> List[str]:
        """Get job URLs from job board listing pages"""
        job_urls = []
        session = await self._get_session()
        
        try:
            # Start with the base URL
            current_url = job_board.base_url
            page = 1
            max_pages = min(10, (max_jobs // 20) + 1)  # Assume ~20 jobs per page
            
            while len(job_urls) < max_jobs and page <= max_pages:
                logger.info(f"Scraping job URLs from page {page}: {current_url}")
                
                # Add delay between requests
                if page > 1:
                    await asyncio.sleep(random.uniform(1.0, 3.0))
                
                async with session.get(current_url) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch page {page}: HTTP {response.status}")
                        break
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Find job links using common patterns
                    page_job_urls = await self._extract_job_urls(soup, job_board.base_url)
                    
                    if not page_job_urls:
                        logger.warning(f"No job URLs found on page {page}")
                        break
                    
                    job_urls.extend(page_job_urls)
                    
                    # Try to find next page URL
                    next_url = await self._find_next_page_url(soup, current_url)
                    if not next_url:
                        break
                    
                    current_url = next_url
                    page += 1
            
            return list(set(job_urls))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Failed to get job URLs: {e}")
            return job_urls
    
    async def _extract_job_urls(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract job URLs from a page using AI-powered analysis"""
        job_urls = []
        
        try:
            # Common job link patterns
            job_link_selectors = [
                'a[href*="/job/"]',
                'a[href*="/jobs/"]',
                'a[href*="/career/"]',
                'a[href*="/careers/"]',
                'a[href*="/position/"]',
                'a[href*="/vacancy/"]',
                '.job-title a',
                '.job-link',
                '.position-title a',
                '[data-testid*="job"] a',
                '[data-cy*="job"] a'
            ]
            
            # Try each selector
            for selector in job_link_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href')
                    if href:
                        full_url = urljoin(base_url, href)
                        if self._is_valid_job_url(full_url):
                            job_urls.append(full_url)
            
            # If no URLs found with common patterns, use AI to analyze
            if not job_urls:
                html_sample = str(soup)[:5000]  # First 5KB
                ai_selectors = await self.ai_decision_engine.generate_selectors(
                    None, html_sample  # We'll need to modify this method
                )
                
                if 'job_links' in ai_selectors:
                    links = soup.select(ai_selectors['job_links'])
                    for link in links:
                        href = link.get('href')
                        if href:
                            full_url = urljoin(base_url, href)
                            if self._is_valid_job_url(full_url):
                                job_urls.append(full_url)
            
            return list(set(job_urls))  # Remove duplicates
            
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
    
    async def _find_next_page_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Find next page URL"""
        try:
            # Common next page selectors
            next_selectors = [
                'a[rel="next"]',
                '.next a',
                '.pagination-next',
                'a:contains("Next")',
                'a:contains("→")',
                '.pager-next a',
                '[data-testid="next-page"]'
            ]
            
            for selector in next_selectors:
                next_link = soup.select_one(selector)
                if next_link and next_link.get('href'):
                    return urljoin(current_url, next_link['href'])
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to find next page URL: {e}")
            return None
    
    async def _scrape_single_job(self, semaphore: asyncio.Semaphore, job_url: str, job_board: JobBoard, selectors: Dict[str, str]) -> Optional[JobData]:
        """Scrape a single job posting"""
        async with semaphore:
            try:
                # Add delay between requests
                await asyncio.sleep(random.uniform(0.5, 2.0))
                
                session = await self._get_session()
                async with session.get(job_url) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch job: {job_url} (HTTP {response.status})")
                        return None
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract job data using selectors
                    job_data = await self._extract_job_data(soup, selectors, job_url, job_board)
                    
                    if job_data:
                        logger.debug(f"Scraped job: {job_data.title} at {job_data.company}")
                        return job_data
                    
                    return None
                    
            except Exception as e:
                logger.error(f"Failed to scrape job {job_url}: {e}")
                return None
    
    async def _extract_job_data(self, soup: BeautifulSoup, selectors: Dict[str, str], job_url: str, job_board: JobBoard) -> Optional[JobData]:
        """Extract job data from HTML using selectors"""
        try:
            # Extract basic fields
            title = self._extract_text(soup, selectors.get('job_title', ''), 'title')
            company = self._extract_text(soup, selectors.get('company', ''), 'company')
            location = self._extract_text(soup, selectors.get('location', ''), 'location')
            description = self._extract_text(soup, selectors.get('description', ''), 'description')
            salary = self._extract_text(soup, selectors.get('salary', ''), 'salary')
            date_posted_str = self._extract_text(soup, selectors.get('date_posted', ''), 'date')
            
            # Validate required fields
            if not title or not company:
                logger.warning(f"Missing required fields for job at {job_url}")
                return None
            
            # Parse date
            date_posted = self._parse_date(date_posted_str)
            
            # Create job data
            job_data = JobData(
                title=title.strip(),
                company=company.strip(),
                location=location.strip() if location else "Not specified",
                description=description.strip() if description else "",
                salary=salary.strip() if salary else None,
                date_posted=date_posted,
                url=job_url,
                job_board_id=str(job_board.id),
                job_board_name=job_board.name,
                scraped_at=datetime.now(),
                scraping_engine=ScrapingEngine.BEAUTIFULSOUP.value
            )
            
            return job_data
            
        except Exception as e:
            logger.error(f"Failed to extract job data: {e}")
            return None
    
    def _extract_text(self, soup: BeautifulSoup, selector: str, field_type: str) -> str:
        """Extract text using CSS selector with fallbacks"""
        if not selector:
            return ""
        
        try:
            # Try the provided selector first
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text:
                    return text
            
            # Fallback selectors based on field type
            fallback_selectors = self._get_fallback_selectors(field_type)
            
            for fallback_selector in fallback_selectors:
                element = soup.select_one(fallback_selector)
                if element:
                    text = element.get_text(strip=True)
                    if text:
                        return text
            
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
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("BeautifulSoup session closed")