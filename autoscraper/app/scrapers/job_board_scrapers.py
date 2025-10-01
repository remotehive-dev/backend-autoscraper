#!/usr/bin/env python3
"""
Job Board Specific Scrapers
Specialized scrapers for popular job boards with custom parsing logic
"""

import asyncio
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse, parse_qs
import json

from bs4 import BeautifulSoup
import feedparser

logger = logging.getLogger(__name__)

from .enhanced_scraper import EnhancedScraper, ScrapingResult, ScrapingStatus
from .job_board_configs import JobBoardConfigs
from .scraping_monitor import get_monitor, monitored_scraping

class IndeedScraper(EnhancedScraper):
    """Specialized scraper for Indeed.com"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.indeed.com"
        self.search_url = "https://www.indeed.com/jobs"
    
    async def scrape_jobs(self, query: str = "remote", location: str = "Remote", 
                         max_pages: int = 5) -> ScrapingResult:
        """Scrape Indeed jobs with custom logic"""
        async with monitored_scraping("Indeed", query, location) as monitor:
            start_time = datetime.now()
            jobs = []
            errors = []
            pages_scraped = 0
            
            try:
                for page in range(max_pages):
                    page_jobs, page_errors = await self._scrape_indeed_page(
                        query, location, page * 10
                    )
                    
                    if not page_jobs and page > 0:
                        break
                    
                    jobs.extend(page_jobs)
                    errors.extend(page_errors)
                    pages_scraped += 1
                    
                    # Rate limiting
                    await asyncio.sleep(2)
                
                execution_time = (datetime.now() - start_time).total_seconds()
                status = ScrapingStatus.SUCCESS if jobs else ScrapingStatus.FAILED
                
                result = ScrapingResult(
                    status=status,
                    jobs=jobs,
                    total_found=len(jobs),
                    pages_scraped=pages_scraped,
                    errors=errors,
                    execution_time=execution_time,
                    job_board_name="Indeed",
                    timestamp=datetime.now()
                )
                
                monitor.record_scraping_result(result)
                return result
                
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                result = ScrapingResult(
                    status=ScrapingStatus.FAILED,
                    jobs=jobs,
                    total_found=len(jobs),
                    pages_scraped=pages_scraped,
                    errors=errors + [str(e)],
                    execution_time=execution_time,
                    job_board_name="Indeed",
                    timestamp=datetime.now()
                )
                
                monitor.record_scraping_result(result)
                return result
    
    async def _scrape_indeed_page(self, query: str, location: str, 
                                 start: int) -> tuple[List[Dict], List[str]]:
        """Scrape a single Indeed page"""
        jobs = []
        errors = []
        
        params = {
            'q': query,
            'l': location,
            'start': start,
            'sort': 'date'
        }
        
        url = f"{self.search_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    errors.append(f"HTTP {response.status} for {url}")
                    return jobs, errors
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Indeed job containers
                job_containers = soup.find_all('div', {'data-jk': True})
                
                for container in job_containers:
                    try:
                        job_data = self._parse_indeed_job(container)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        errors.append(f"Error parsing job: {e}")
                        continue
        
        except Exception as e:
            errors.append(f"Error scraping page: {e}")
        
        return jobs, errors
    
    def _parse_indeed_job(self, container) -> Optional[Dict[str, Any]]:
        """Parse individual Indeed job posting"""
        try:
            # Job title and URL
            title_elem = container.find('h2', class_='jobTitle')
            if not title_elem:
                title_elem = container.find('a', {'data-jk': True})
            
            if not title_elem:
                return None
            
            title_link = title_elem.find('a') if title_elem.name != 'a' else title_elem
            title = title_link.get_text(strip=True) if title_link else ''
            job_url = urljoin(self.base_url, title_link.get('href', '')) if title_link else ''
            
            # Company name
            company_elem = container.find('span', class_='companyName')
            company = company_elem.get_text(strip=True) if company_elem else ''
            
            # Location
            location_elem = container.find('div', class_='companyLocation')
            location = location_elem.get_text(strip=True) if location_elem else ''
            
            # Salary (if available)
            salary_elem = container.find('span', class_='salaryText')
            salary = salary_elem.get_text(strip=True) if salary_elem else ''
            
            # Job snippet/description
            snippet_elem = container.find('div', class_='job-snippet')
            description = snippet_elem.get_text(strip=True) if snippet_elem else ''
            
            # Posted date
            date_elem = container.find('span', class_='date')
            posted_date = date_elem.get_text(strip=True) if date_elem else ''
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'salary': salary,
                'description': description,
                'url': job_url,
                'posted_date': posted_date,
                'source': 'Indeed',
                'scraped_at': datetime.now().isoformat()
            }
        
        except Exception as e:
            raise Exception(f"Error parsing Indeed job: {e}")

class LinkedInScraper(EnhancedScraper):
    """Specialized scraper for LinkedIn Jobs"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.linkedin.com"
        self.search_url = "https://www.linkedin.com/jobs/search"
    
    async def scrape_jobs(self, query: str = "remote", location: str = "Worldwide", 
                         max_pages: int = 3) -> ScrapingResult:
        """Scrape LinkedIn jobs (Note: LinkedIn has strict anti-scraping measures)"""
        async with monitored_scraping("LinkedIn", query, location) as monitor:
            start_time = datetime.now()
            
            # LinkedIn requires authentication and has strict rate limiting
            # This is a basic implementation that may be blocked
            
            result = ScrapingResult(
                status=ScrapingStatus.FAILED,
                jobs=[],
                total_found=0,
                pages_scraped=0,
                errors=["LinkedIn scraping requires authentication and may be blocked"],
                execution_time=0.0,
                job_board_name="LinkedIn",
                timestamp=datetime.now()
            )
            
            monitor.record_scraping_result(result)
            return result

class RemoteOKScraper(EnhancedScraper):
    """Specialized scraper for RemoteOK.io"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://remoteok.io"
        self.api_url = "https://remoteok.io/api"
    
    async def scrape_jobs(self, query: str = "", location: str = "", 
                         max_pages: int = 1) -> ScrapingResult:
        """Scrape RemoteOK jobs using their API"""
        async with monitored_scraping("RemoteOK", query, location) as monitor:
            start_time = datetime.now()
            jobs = []
            errors = []
            
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
                
                async with self.session.get(self.api_url, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"API returned status {response.status}")
                    
                    data = await response.json()
                    
                    # RemoteOK API returns array of jobs
                    for job_data in data:
                        if isinstance(job_data, dict) and 'id' in job_data:
                            try:
                                parsed_job = self._parse_remoteok_job(job_data)
                                if parsed_job and self._matches_query(parsed_job, query):
                                    jobs.append(parsed_job)
                            except Exception as e:
                                errors.append(f"Error parsing job {job_data.get('id', 'unknown')}: {e}")
                
                execution_time = (datetime.now() - start_time).total_seconds()
                status = ScrapingStatus.SUCCESS if jobs else ScrapingStatus.FAILED
                
                result = ScrapingResult(
                    status=status,
                    jobs=jobs,
                    total_found=len(jobs),
                    pages_scraped=1,
                    errors=errors,
                    execution_time=execution_time,
                    job_board_name="RemoteOK",
                    timestamp=datetime.now()
                )
                
                monitor.record_scraping_result(result)
                return result
                
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                result = ScrapingResult(
                    status=ScrapingStatus.FAILED,
                    jobs=jobs,
                    total_found=len(jobs),
                    pages_scraped=0,
                    errors=errors + [str(e)],
                    execution_time=execution_time,
                    job_board_name="RemoteOK",
                    timestamp=datetime.now()
                )
                
                monitor.record_scraping_result(result)
                return result
    
    def _parse_remoteok_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse RemoteOK job data"""
        return {
            'title': job_data.get('position', ''),
            'company': job_data.get('company', ''),
            'location': 'Remote',
            'salary': self._format_salary(job_data),
            'description': job_data.get('description', ''),
            'url': f"https://remoteok.io/remote-jobs/{job_data.get('id', '')}",
            'posted_date': self._format_date(job_data.get('date')),
            'tags': job_data.get('tags', []),
            'source': 'RemoteOK',
            'scraped_at': datetime.now().isoformat()
        }
    
    def _format_salary(self, job_data: Dict[str, Any]) -> str:
        """Format salary information"""
        salary_min = job_data.get('salary_min')
        salary_max = job_data.get('salary_max')
        
        if salary_min and salary_max:
            return f"${salary_min:,} - ${salary_max:,}"
        elif salary_min:
            return f"${salary_min:,}+"
        else:
            return ""
    
    def _format_date(self, timestamp) -> str:
        """Format date from timestamp"""
        if timestamp:
            try:
                return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d')
            except:
                pass
        return ""
    
    def _matches_query(self, job_data: Dict[str, Any], query: str) -> bool:
        """Check if job matches search query"""
        if not query:
            return True
        
        query_lower = query.lower()
        searchable_text = (
            job_data.get('title', '') + ' ' +
            job_data.get('company', '') + ' ' +
            job_data.get('description', '') + ' ' +
            ' '.join(job_data.get('tags', []))
        ).lower()
        
        return query_lower in searchable_text

class AngelListScraper(EnhancedScraper):
    """Specialized scraper for AngelList (Wellfound)"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://wellfound.com"
        self.search_url = "https://wellfound.com/jobs"
    
    async def scrape_jobs(self, query: str = "remote", location: str = "Remote", 
                         max_pages: int = 3) -> ScrapingResult:
        """Scrape AngelList/Wellfound jobs"""
        async with monitored_scraping("AngelList", query, location) as monitor:
            start_time = datetime.now()
            
            # AngelList has moved to Wellfound and requires authentication
            # This is a placeholder implementation
            
            result = ScrapingResult(
                status=ScrapingStatus.FAILED,
                jobs=[],
                total_found=0,
                pages_scraped=0,
                errors=["AngelList/Wellfound scraping requires authentication"],
                execution_time=0.0,
                job_board_name="AngelList",
                timestamp=datetime.now()
            )
            
            monitor.record_scraping_result(result)
            return result

class StackOverflowJobsScraper(EnhancedScraper):
    """Specialized scraper for Stack Overflow Jobs (now discontinued)"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://stackoverflow.com"
    
    async def scrape_jobs(self, query: str = "remote", location: str = "Remote", 
                         max_pages: int = 3) -> ScrapingResult:
        """Stack Overflow Jobs has been discontinued"""
        async with monitored_scraping("StackOverflow", query, location) as monitor:
            result = ScrapingResult(
                status=ScrapingStatus.FAILED,
                jobs=[],
                total_found=0,
                pages_scraped=0,
                errors=["Stack Overflow Jobs has been discontinued"],
                execution_time=0.0,
                job_board_name="StackOverflow",
                timestamp=datetime.now()
            )
            
            monitor.record_scraping_result(result)
            return result

class WeWorkRemotelyScraper(EnhancedScraper):
    """Specialized scraper for WeWorkRemotely.com"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://weworkremotely.com"
        self.rss_url = "https://weworkremotely.com/remote-jobs.rss"
    
    async def scrape_jobs(self, query: str = "", location: str = "", 
                         max_pages: int = 1) -> ScrapingResult:
        """Scrape WeWorkRemotely jobs using RSS feed"""
        async with monitored_scraping("WeWorkRemotely", query, location) as monitor:
            start_time = datetime.now()
            jobs = []
            errors = []
            
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
                
                async with self.session.get(self.rss_url, headers=headers) as response:
                    if response.status != 200:
                        raise Exception(f"RSS feed returned status {response.status}")
                    
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    for entry in feed.entries:
                        try:
                            job_data = self._parse_wwr_job(entry)
                            if job_data and self._matches_query(job_data, query):
                                jobs.append(job_data)
                        except Exception as e:
                            errors.append(f"Error parsing RSS entry: {e}")
                
                execution_time = (datetime.now() - start_time).total_seconds()
                status = ScrapingStatus.SUCCESS if jobs else ScrapingStatus.FAILED
                
                result = ScrapingResult(
                    status=status,
                    jobs=jobs,
                    total_found=len(jobs),
                    pages_scraped=1,
                    errors=errors,
                    execution_time=execution_time,
                    job_board_name="WeWorkRemotely",
                    timestamp=datetime.now()
                )
                
                monitor.record_scraping_result(result)
                return result
                
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                result = ScrapingResult(
                    status=ScrapingStatus.FAILED,
                    jobs=jobs,
                    total_found=len(jobs),
                    pages_scraped=0,
                    errors=errors + [str(e)],
                    execution_time=execution_time,
                    job_board_name="WeWorkRemotely",
                    timestamp=datetime.now()
                )
                
                monitor.record_scraping_result(result)
                return result
    
    def _parse_wwr_job(self, entry) -> Dict[str, Any]:
        """Parse WeWorkRemotely RSS entry"""
        title = getattr(entry, 'title', '')
        
        # Extract company and position from title (format: "Company: Position")
        if ':' in title:
            company, position = title.split(':', 1)
            company = company.strip()
            position = position.strip()
        else:
            company = ''
            position = title
        
        return {
            'title': position,
            'company': company,
            'location': 'Remote',
            'salary': '',
            'description': getattr(entry, 'summary', ''),
            'url': getattr(entry, 'link', ''),
            'posted_date': getattr(entry, 'published', ''),
            'source': 'WeWorkRemotely',
            'scraped_at': datetime.now().isoformat()
        }
    
    def _matches_query(self, job_data: Dict[str, Any], query: str) -> bool:
        """Check if job matches search query"""
        if not query:
            return True
        
        query_lower = query.lower()
        searchable_text = (
            job_data.get('title', '') + ' ' +
            job_data.get('company', '') + ' ' +
            job_data.get('description', '')
        ).lower()
        
        return query_lower in searchable_text

class JobBoardScraperFactory:
    """Factory for creating specialized job board scrapers with generic fallback"""
    
    _scrapers = {
        'indeed': IndeedScraper,
        'linkedin': LinkedInScraper,
        'remoteok': RemoteOKScraper,
        'angellist': AngelListScraper,
        'stackoverflow': StackOverflowJobsScraper,
        'weworkremotely': WeWorkRemotelyScraper
    }
    
    @classmethod
    def create_scraper(cls, job_board_name: str) -> Optional[EnhancedScraper]:
        """Create a specialized scraper for the given job board, with generic fallback"""
        # Normalize job board name to match scraper keys
        normalized_name = cls._normalize_job_board_name(job_board_name)
        scraper_class = cls._scrapers.get(normalized_name)
        if scraper_class:
            return scraper_class()
        
        # For unknown job boards, create a generic scraper using MultiEngineScrapingFramework
        logger.info(f"No specialized scraper found for '{job_board_name}', using generic multi-engine scraper")
        return cls._create_generic_scraper(job_board_name)
    
    @classmethod
    def _create_generic_scraper(cls, job_board_name: str) -> Optional[EnhancedScraper]:
        """Create a generic scraper for unknown job boards"""
        try:
            from .multi_engine_framework import MultiEngineScrapingFramework
            
            # Create a wrapper that adapts MultiEngineScrapingFramework to EnhancedScraper interface
            class GenericJobBoardScraper(EnhancedScraper):
                def __init__(self, board_name: str):
                    super().__init__()
                    self.board_name = board_name
                    self.multi_engine = MultiEngineScrapingFramework()
                
                async def scrape_jobs(self, query: str = "", location: str = "Remote", 
                                    max_pages: int = 3) -> ScrapingResult:
                    """Scrape jobs using multi-engine framework"""
                    try:
                        # Create a mock JobBoard object for the multi-engine framework
                        from ..models.mongodb_models import JobBoard, JobBoardType
                        
                        # Create a temporary job board configuration
                        job_board = JobBoard(
                            name=self.board_name,
                            type=JobBoardType.HTML,  # Default to HTML type
                            base_url=f"https://{self.board_name.lower().replace(' ', '')}.com",
                            search_url_template=f"https://{self.board_name.lower().replace(' ', '')}.com/jobs",
                            is_active=True,
                            selectors={},  # Let AI determine selectors
                            rate_limit_delay=2.0,
                            max_pages_per_search=max_pages
                        )
                        
                        # Use multi-engine framework to scrape
                        result = await self.multi_engine.scrape_job_board(job_board, max_jobs=100)
                        
                        # Convert MultiEngineScrapingFramework result to EnhancedScraper format
                        return ScrapingResult(
                            status=ScrapingStatus.SUCCESS if result.success else ScrapingStatus.FAILED,
                            jobs=[job.__dict__ for job in result.jobs] if result.jobs else [],
                            total_found=len(result.jobs) if result.jobs else 0,
                            pages_scraped=1,
                            errors=[result.error_message] if result.error_message else [],
                            execution_time=result.execution_time,
                            job_board_name=self.board_name,
                            timestamp=datetime.now()
                        )
                        
                    except Exception as e:
                        logger.error(f"Generic scraper failed for {self.board_name}: {e}")
                        return ScrapingResult(
                            status=ScrapingStatus.FAILED,
                            jobs=[],
                            total_found=0,
                            pages_scraped=0,
                            errors=[str(e)],
                            execution_time=0.0,
                            job_board_name=self.board_name,
                            timestamp=datetime.now()
                        )
            
            return GenericJobBoardScraper(job_board_name)
            
        except Exception as e:
            logger.error(f"Failed to create generic scraper for {job_board_name}: {e}")
            return None
    
    @classmethod
    def _normalize_job_board_name(cls, job_board_name: str) -> str:
        """Normalize job board name to match scraper factory keys"""
        name_lower = job_board_name.lower().strip()
        
        # Map common job board name variations to scraper keys
        name_mappings = {
            'indeed jobs': 'indeed',
            'indeed': 'indeed',
            'linkedin jobs': 'linkedin', 
            'linkedin': 'linkedin',
            'glassdoor': 'glassdoor',  # Not implemented yet
            'monster': 'monster',      # Not implemented yet
            'ziprecruiter': 'ziprecruiter',  # Not implemented yet
            'remote ok': 'remoteok',
            'remoteok': 'remoteok',
            'angel list': 'angellist',
            'angellist': 'angellist',
            'stackoverflow jobs': 'stackoverflow',
            'stackoverflow': 'stackoverflow',
            'stack overflow jobs': 'stackoverflow',
            'weworkremotely': 'weworkremotely',
            'we work remotely': 'weworkremotely'
        }
        
        return name_mappings.get(name_lower, name_lower)
    
    @classmethod
    def get_available_scrapers(cls) -> List[str]:
        """Get list of available specialized scrapers"""
        return list(cls._scrapers.keys())
    
    @classmethod
    async def scrape_all_available(cls, query: str = "remote", 
                                  location: str = "Remote",
                                  max_pages: int = 3) -> List[ScrapingResult]:
        """Scrape all available job boards concurrently"""
        results = []
        
        # Create tasks for all scrapers
        tasks = []
        for scraper_name in cls._scrapers.keys():
            scraper = cls.create_scraper(scraper_name)
            if scraper:
                async with scraper:
                    task = scraper.scrape_jobs(query, location, max_pages)
                    tasks.append(task)
        
        # Execute all tasks concurrently
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            valid_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Create failed result for exceptions
                    scraper_name = list(cls._scrapers.keys())[i]
                    valid_results.append(ScrapingResult(
                        status=ScrapingStatus.FAILED,
                        jobs=[],
                        total_found=0,
                        pages_scraped=0,
                        errors=[str(result)],
                        execution_time=0.0,
                        job_board_name=scraper_name,
                        timestamp=datetime.now()
                    ))
                else:
                    valid_results.append(result)
            
            results = valid_results
        
        return results

# Convenience functions
async def scrape_indeed(query: str = "remote", location: str = "Remote", 
                       max_pages: int = 5) -> ScrapingResult:
    """Convenience function to scrape Indeed"""
    async with IndeedScraper() as scraper:
        return await scraper.scrape_jobs(query, location, max_pages)

async def scrape_remoteok(query: str = "") -> ScrapingResult:
    """Convenience function to scrape RemoteOK"""
    async with RemoteOKScraper() as scraper:
        return await scraper.scrape_jobs(query)

async def scrape_weworkremotely(query: str = "") -> ScrapingResult:
    """Convenience function to scrape WeWorkRemotely"""
    async with WeWorkRemotelyScraper() as scraper:
        return await scraper.scrape_jobs(query)