import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import logging
import random
import re
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

from .multi_engine_framework import BaseJobScraper
from .types import ScrapingEngine, JobData
from ..models.mongodb_models import JobBoard
from ..ai.decision_engine import get_ai_decision_engine

class SeleniumJobScraper(BaseJobScraper):
    """Selenium-based job scraper for JavaScript-heavy sites"""
    
    def __init__(self):
        super().__init__(ScrapingEngine.SELENIUM)
        self.driver = None
        self.wait = None
        self.ai_decision_engine = get_ai_decision_engine()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
    
    async def _get_driver(self) -> webdriver.Chrome:
        """Get or create Selenium WebDriver"""
        if self.driver is None:
            try:
                # Chrome options
                chrome_options = ChromeOptions()
                chrome_options.add_argument('--headless')  # Run in background
                chrome_options.add_argument('--no-sandbox')
                chrome_options.add_argument('--disable-dev-shm-usage')
                chrome_options.add_argument('--disable-gpu')
                chrome_options.add_argument('--disable-extensions')
                chrome_options.add_argument('--disable-plugins')
                chrome_options.add_argument('--disable-images')
                chrome_options.add_argument('--disable-javascript-harmony-shipping')
                chrome_options.add_argument('--disable-background-timer-throttling')
                chrome_options.add_argument('--disable-renderer-backgrounding')
                chrome_options.add_argument('--disable-backgrounding-occluded-windows')
                chrome_options.add_argument('--window-size=1920,1080')
                chrome_options.add_argument(f'--user-agent={random.choice(self.user_agents)}')
                
                # Performance optimizations
                chrome_options.add_experimental_option('useAutomationExtension', False)
                chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
                chrome_options.add_argument('--disable-blink-features=AutomationControlled')
                
                # Create driver
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                # Set timeouts
                self.driver.implicitly_wait(10)
                self.driver.set_page_load_timeout(30)
                
                # Create WebDriverWait
                self.wait = WebDriverWait(self.driver, 10)
                
                logger.info("Selenium Chrome driver initialized")
                
            except Exception as e:
                logger.error(f"Failed to initialize Chrome driver: {e}")
                # Try Firefox as fallback
                try:
                    firefox_options = FirefoxOptions()
                    firefox_options.add_argument('--headless')
                    self.driver = webdriver.Firefox(options=firefox_options)
                    self.driver.implicitly_wait(10)
                    self.driver.set_page_load_timeout(30)
                    self.wait = WebDriverWait(self.driver, 10)
                    logger.info("Selenium Firefox driver initialized as fallback")
                except Exception as e2:
                    logger.error(f"Failed to initialize Firefox driver: {e2}")
                    raise Exception(f"Failed to initialize any WebDriver: Chrome: {e}, Firefox: {e2}")
        
        return self.driver
    
    async def test_connection(self, url: str) -> bool:
        """Test if we can connect to the URL"""
        try:
            driver = await self._get_driver()
            driver.get(url)
            
            # Wait for page to load
            await asyncio.sleep(2)
            
            # Check if page loaded successfully
            return "error" not in driver.title.lower() and len(driver.page_source) > 1000
            
        except Exception as e:
            logger.error(f"Selenium connection test failed for {url}: {e}")
            return False
    
    async def scrape_jobs(self, job_board: JobBoard, selectors: Dict[str, str], **kwargs) -> List[JobData]:
        """Scrape jobs using Selenium"""
        max_jobs = kwargs.get('max_jobs', 100)
        jobs = []
        
        try:
            driver = await self._get_driver()
            
            # Get job listing pages
            job_urls = await self._get_job_urls(driver, job_board, max_jobs)
            
            if not job_urls:
                logger.warning(f"No job URLs found for {job_board.name}")
                return jobs
            
            # Scrape individual job pages
            for i, job_url in enumerate(job_urls[:max_jobs]):
                try:
                    logger.info(f"Scraping job {i+1}/{min(len(job_urls), max_jobs)}: {job_url}")
                    
                    job_data = await self._scrape_single_job(driver, job_url, job_board, selectors)
                    
                    if job_data:
                        jobs.append(job_data)
                        logger.debug(f"Scraped job: {job_data.title} at {job_data.company}")
                    
                    # Add delay between jobs
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    
                except Exception as e:
                    logger.error(f"Failed to scrape job {job_url}: {e}")
                    continue
            
            logger.info(f"Selenium scraped {len(jobs)} jobs from {job_board.name}")
            return jobs
            
        except Exception as e:
            logger.error(f"Selenium scraping failed for {job_board.name}: {e}")
            return jobs
    
    async def _get_job_urls(self, driver: webdriver.Chrome, job_board: JobBoard, max_jobs: int) -> List[str]:
        """Get job URLs from job board listing pages"""
        job_urls = []
        
        try:
            # Navigate to job board
            driver.get(job_board.base_url)
            await asyncio.sleep(3)  # Wait for page to load
            
            # Handle cookie banners, popups, etc.
            await self._handle_popups(driver)
            
            page = 1
            max_pages = min(10, (max_jobs // 20) + 1)  # Assume ~20 jobs per page
            
            while len(job_urls) < max_jobs and page <= max_pages:
                logger.info(f"Scraping job URLs from page {page}")
                
                # Wait for job listings to load
                await self._wait_for_job_listings(driver)
                
                # Extract job URLs from current page
                page_job_urls = await self._extract_job_urls_from_page(driver, job_board.base_url)
                
                if not page_job_urls:
                    logger.warning(f"No job URLs found on page {page}")
                    break
                
                job_urls.extend(page_job_urls)
                logger.info(f"Found {len(page_job_urls)} job URLs on page {page}")
                
                # Try to go to next page
                if not await self._go_to_next_page(driver):
                    logger.info("No more pages available")
                    break
                
                page += 1
                await asyncio.sleep(random.uniform(3.0, 6.0))  # Wait between pages
            
            return list(set(job_urls))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Failed to get job URLs: {e}")
            return job_urls
    
    async def _handle_popups(self, driver: webdriver.Chrome):
        """Handle cookie banners and popups"""
        try:
            # Common popup selectors
            popup_selectors = [
                '[data-testid="cookie-banner"] button',
                '.cookie-banner button',
                '#cookie-banner button',
                '.gdpr-banner button',
                '[aria-label*="Accept"]',
                '[aria-label*="Close"]',
                '.modal-close',
                '.popup-close',
                'button:contains("Accept")',
                'button:contains("Close")',
                'button:contains("Dismiss")'
            ]
            
            for selector in popup_selectors:
                try:
                    # Convert CSS selector to XPath for contains() function
                    if ':contains(' in selector:
                        text = selector.split(':contains("')[1].split('")')[0]
                        xpath = f"//button[contains(text(), '{text}')]"
                        element = driver.find_element(By.XPATH, xpath)
                    else:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if element.is_displayed():
                        element.click()
                        await asyncio.sleep(1)
                        logger.info(f"Closed popup using selector: {selector}")
                        break
                        
                except (NoSuchElementException, WebDriverException):
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to handle popups: {e}")
    
    async def _wait_for_job_listings(self, driver: webdriver.Chrome):
        """Wait for job listings to load"""
        try:
            # Common job listing selectors
            job_listing_selectors = [
                '.job-listing',
                '.job-item',
                '.job-card',
                '.position',
                '.vacancy',
                '[data-testid*="job"]',
                '[data-cy*="job"]'
            ]
            
            for selector in job_listing_selectors:
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    logger.debug(f"Job listings loaded with selector: {selector}")
                    return
                except TimeoutException:
                    continue
            
            # If no specific selectors work, just wait for page to stabilize
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Failed to wait for job listings: {e}")
    
    async def _extract_job_urls_from_page(self, driver: webdriver.Chrome, base_url: str) -> List[str]:
        """Extract job URLs from current page"""
        job_urls = []
        
        try:
            # Common job link selectors
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
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        href = element.get_attribute('href')
                        if href and self._is_valid_job_url(href):
                            job_urls.append(href)
                except Exception:
                    continue
            
            # If no URLs found with common patterns, use AI to analyze
            if not job_urls:
                try:
                    html_sample = driver.page_source[:5000]  # First 5KB
                    ai_selectors = await self.ai_decision_engine.generate_selectors(
                        None, html_sample  # We'll need to modify this method
                    )
                    
                    if 'job_links' in ai_selectors:
                        elements = driver.find_elements(By.CSS_SELECTOR, ai_selectors['job_links'])
                        for element in elements:
                            href = element.get_attribute('href')
                            if href and self._is_valid_job_url(href):
                                job_urls.append(href)
                except Exception as e:
                    logger.error(f"AI selector generation failed: {e}")
            
            return list(set(job_urls))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Failed to extract job URLs from page: {e}")
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
    
    async def _go_to_next_page(self, driver: webdriver.Chrome) -> bool:
        """Navigate to next page"""
        try:
            # Common next page selectors
            next_selectors = [
                'a[rel="next"]',
                '.next a',
                '.pagination-next',
                '.pager-next a',
                '[data-testid="next-page"]',
                '[aria-label*="Next"]'
            ]
            
            # Also try XPath for text-based selectors
            next_xpaths = [
                "//a[contains(text(), 'Next')]",
                "//button[contains(text(), 'Next')]",
                "//a[contains(text(), '→')]",
                "//button[contains(text(), '→')]"
            ]
            
            # Try CSS selectors first
            for selector in next_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element.is_displayed() and element.is_enabled():
                        driver.execute_script("arguments[0].click();", element)
                        await asyncio.sleep(3)  # Wait for page to load
                        return True
                except (NoSuchElementException, WebDriverException):
                    continue
            
            # Try XPath selectors
            for xpath in next_xpaths:
                try:
                    element = driver.find_element(By.XPATH, xpath)
                    if element.is_displayed() and element.is_enabled():
                        driver.execute_script("arguments[0].click();", element)
                        await asyncio.sleep(3)  # Wait for page to load
                        return True
                except (NoSuchElementException, WebDriverException):
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to go to next page: {e}")
            return False
    
    async def _scrape_single_job(self, driver: webdriver.Chrome, job_url: str, job_board: JobBoard, selectors: Dict[str, str]) -> Optional[JobData]:
        """Scrape a single job posting"""
        try:
            # Navigate to job page
            driver.get(job_url)
            await asyncio.sleep(3)  # Wait for page to load
            
            # Handle any popups on job page
            await self._handle_popups(driver)
            
            # Wait for job content to load
            await self._wait_for_job_content(driver)
            
            # Extract job data using selectors
            job_data = await self._extract_job_data_from_page(driver, selectors, job_url, job_board)
            
            return job_data
            
        except Exception as e:
            logger.error(f"Failed to scrape job {job_url}: {e}")
            return None
    
    async def _wait_for_job_content(self, driver: webdriver.Chrome):
        """Wait for job content to load"""
        try:
            # Common job content selectors
            content_selectors = [
                '.job-description',
                '.job-content',
                '.position-details',
                '.job-details',
                '[data-testid*="description"]',
                '[data-cy*="description"]'
            ]
            
            for selector in content_selectors:
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    logger.debug(f"Job content loaded with selector: {selector}")
                    return
                except TimeoutException:
                    continue
            
            # If no specific selectors work, just wait
            await asyncio.sleep(3)
            
        except Exception as e:
            logger.error(f"Failed to wait for job content: {e}")
    
    async def _extract_job_data_from_page(self, driver: webdriver.Chrome, selectors: Dict[str, str], job_url: str, job_board: JobBoard) -> Optional[JobData]:
        """Extract job data from current page"""
        try:
            # Extract basic fields
            title = self._extract_text_selenium(driver, selectors.get('job_title', ''), 'title')
            company = self._extract_text_selenium(driver, selectors.get('company', ''), 'company')
            location = self._extract_text_selenium(driver, selectors.get('location', ''), 'location')
            description = self._extract_text_selenium(driver, selectors.get('description', ''), 'description')
            salary = self._extract_text_selenium(driver, selectors.get('salary', ''), 'salary')
            date_posted_str = self._extract_text_selenium(driver, selectors.get('date_posted', ''), 'date')
            
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
                scraping_engine=ScrapingEngine.SELENIUM.value
            )
            
            return job_data
            
        except Exception as e:
            logger.error(f"Failed to extract job data: {e}")
            return None
    
    def _extract_text_selenium(self, driver: webdriver.Chrome, selector: str, field_type: str) -> str:
        """Extract text using CSS selector with Selenium"""
        if not selector:
            return ""
        
        try:
            # Try the provided selector first
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text:
                    return text
            except (NoSuchElementException, WebDriverException):
                pass
            
            # Fallback selectors based on field type
            fallback_selectors = self._get_fallback_selectors(field_type)
            
            for fallback_selector in fallback_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, fallback_selector)
                    text = element.text.strip()
                    if text:
                        return text
                except (NoSuchElementException, WebDriverException):
                    continue
            
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
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Selenium driver closed")
            except Exception as e:
                logger.error(f"Failed to close Selenium driver: {e}")
            finally:
                self.driver = None
                self.wait = None