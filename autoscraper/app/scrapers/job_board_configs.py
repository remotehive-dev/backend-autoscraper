#!/usr/bin/env python3
"""
Job Board Configurations for Enhanced Scraping
Contains configurations for popular job boards with selectors, headers, and scraping parameters
"""

from typing import Dict, Any, List
from enum import Enum

class JobBoardType(Enum):
    """Job board scraping types"""
    RSS = "rss"
    HTML = "html"
    API = "api"
    HYBRID = "hybrid"

class JobBoardConfigs:
    """Enhanced job board configurations for real-world scraping"""
    
    @staticmethod
    def get_all_configs() -> List[Dict[str, Any]]:
        """Get all job board configurations"""
        return [
            JobBoardConfigs.indeed_config(),
            JobBoardConfigs.linkedin_config(),
            JobBoardConfigs.glassdoor_config(),
            JobBoardConfigs.angellist_config(),
            JobBoardConfigs.remoteok_config(),
            JobBoardConfigs.weworkremotely_config(),
            JobBoardConfigs.stackoverflow_config(),
            JobBoardConfigs.dice_config(),
            JobBoardConfigs.monster_config(),
            JobBoardConfigs.ziprecruiter_config(),
            JobBoardConfigs.flexjobs_config(),
            JobBoardConfigs.remote_co_config(),
            JobBoardConfigs.nofluffjobs_config(),
            JobBoardConfigs.ycombinator_config(),
            JobBoardConfigs.techcareers_config()
        ]
    
    @staticmethod
    def indeed_config() -> Dict[str, Any]:
        """Indeed job board configuration"""
        return {
            "name": "Indeed",
            "description": "Indeed - World's #1 job site",
            "type": JobBoardType.HTML.value,
            "base_url": "https://www.indeed.com",
            "search_url_template": "https://www.indeed.com/jobs?q={query}&l={location}&start={page}",
            "selectors": {
                "job_container": "[data-jk]",
                "title": "h2.jobTitle a span[title]",
                "company": ".companyName",
                "location": "[data-testid='job-location']",
                "description": ".job-snippet",
                "salary": ".salary-snippet",
                "url": "h2.jobTitle a",
                "posted_date": ".date"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            },
            "rate_limit_delay": 3.0,
            "max_pages": 20,
            "request_timeout": 30,
            "retry_attempts": 3,
            "quality_threshold": 0.8,
            "is_active": True,
            "requires_js": False,
            "pagination_type": "offset",
            "items_per_page": 15
        }
    
    @staticmethod
    def linkedin_config() -> Dict[str, Any]:
        """LinkedIn job board configuration"""
        return {
            "name": "LinkedIn",
            "description": "LinkedIn Jobs - Professional network job board",
            "type": JobBoardType.HTML.value,
            "base_url": "https://www.linkedin.com",
            "search_url_template": "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}&start={page}",
            "selectors": {
                "job_container": ".job-search-card",
                "title": ".base-search-card__title",
                "company": ".base-search-card__subtitle",
                "location": ".job-search-card__location",
                "description": ".job-search-card__snippet",
                "url": ".base-card__full-link",
                "posted_date": ".job-search-card__listdate"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            },
            "rate_limit_delay": 5.0,  # LinkedIn is strict about rate limiting
            "max_pages": 10,
            "request_timeout": 45,
            "retry_attempts": 2,
            "quality_threshold": 0.9,
            "is_active": True,
            "requires_js": True,  # LinkedIn heavily uses JavaScript
            "pagination_type": "offset",
            "items_per_page": 25
        }
    
    @staticmethod
    def glassdoor_config() -> Dict[str, Any]:
        """Glassdoor job board configuration"""
        return {
            "name": "Glassdoor",
            "description": "Glassdoor - Jobs and company reviews",
            "type": JobBoardType.HTML.value,
            "base_url": "https://www.glassdoor.com",
            "search_url_template": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}&locT=C&locId={location}&p={page}",
            "selectors": {
                "job_container": "[data-test='jobListing']",
                "title": "[data-test='job-title']",
                "company": "[data-test='employer-name']",
                "location": "[data-test='job-location']",
                "description": "[data-test='job-description']",
                "salary": "[data-test='detailSalary']",
                "url": "[data-test='job-title'] a"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"
            },
            "rate_limit_delay": 4.0,
            "max_pages": 15,
            "request_timeout": 35,
            "retry_attempts": 3,
            "quality_threshold": 0.85,
            "is_active": True,
            "requires_js": True,
            "pagination_type": "page_number",
            "items_per_page": 30
        }
    
    @staticmethod
    def angellist_config() -> Dict[str, Any]:
        """AngelList (Wellfound) job board configuration"""
        return {
            "name": "AngelList",
            "description": "AngelList (Wellfound) - Startup jobs",
            "type": JobBoardType.HTML.value,
            "base_url": "https://wellfound.com",
            "search_url_template": "https://wellfound.com/jobs?q={query}&l={location}&page={page}",
            "selectors": {
                "job_container": "[data-test='StartupResult']",
                "title": "[data-test='JobSearchResult-title']",
                "company": "[data-test='StartupResult-company']",
                "location": "[data-test='JobSearchResult-location']",
                "description": "[data-test='JobSearchResult-description']",
                "salary": "[data-test='JobSearchResult-salary']",
                "url": "[data-test='JobSearchResult-title'] a"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            },
            "rate_limit_delay": 3.0,
            "max_pages": 10,
            "request_timeout": 30,
            "retry_attempts": 3,
            "quality_threshold": 0.8,
            "is_active": True,
            "requires_js": True,
            "pagination_type": "page_number",
            "items_per_page": 20
        }
    
    @staticmethod
    def remoteok_config() -> Dict[str, Any]:
        """RemoteOK job board configuration"""
        return {
            "name": "RemoteOK",
            "description": "RemoteOK - Remote jobs board",
            "type": JobBoardType.RSS.value,
            "base_url": "https://remoteok.io",
            "rss_url": "https://remoteok.io/remote-jobs.rss",
            "search_url_template": "https://remoteok.io/remote-{query}-jobs",
            "selectors": {
                "job_container": ".job",
                "title": ".position",
                "company": ".company",
                "location": ".location",
                "description": ".description",
                "salary": ".salary",
                "url": "a"
            },
            "headers": {
                "User-Agent": "RemoteHive-AutoScraper/1.0 (+https://remotehive.com)",
                "Accept": "application/rss+xml, application/xml, text/xml"
            },
            "rate_limit_delay": 2.0,
            "max_pages": 5,
            "request_timeout": 20,
            "retry_attempts": 2,
            "quality_threshold": 0.7,
            "is_active": True,
            "requires_js": False,
            "pagination_type": "rss_feed",
            "items_per_page": 50
        }
    
    @staticmethod
    def weworkremotely_config() -> Dict[str, Any]:
        """We Work Remotely job board configuration"""
        return {
            "name": "We Work Remotely",
            "description": "We Work Remotely - Remote jobs",
            "type": JobBoardType.HTML.value,
            "base_url": "https://weworkremotely.com",
            "search_url_template": "https://weworkremotely.com/remote-jobs/search?term={query}&page={page}",
            "selectors": {
                "job_container": ".jobs li",
                "title": ".title",
                "company": ".company",
                "location": ".region",
                "description": ".description",
                "url": "a"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "rate_limit_delay": 2.0,
            "max_pages": 10,
            "request_timeout": 25,
            "retry_attempts": 3,
            "quality_threshold": 0.8,
            "is_active": True,
            "requires_js": False,
            "pagination_type": "page_number",
            "items_per_page": 20
        }
    
    @staticmethod
    def stackoverflow_config() -> Dict[str, Any]:
        """Stack Overflow Jobs configuration"""
        return {
            "name": "Stack Overflow Jobs",
            "description": "Stack Overflow Jobs - Developer jobs",
            "type": JobBoardType.HTML.value,
            "base_url": "https://stackoverflow.com",
            "search_url_template": "https://stackoverflow.com/jobs?q={query}&l={location}&pg={page}",
            "selectors": {
                "job_container": ".listResults .job",
                "title": ".job-link",
                "company": ".employer",
                "location": ".location",
                "description": ".excerpt",
                "salary": ".salary",
                "url": ".job-link"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "rate_limit_delay": 2.5,
            "max_pages": 15,
            "request_timeout": 30,
            "retry_attempts": 3,
            "quality_threshold": 0.85,
            "is_active": True,
            "requires_js": False,
            "pagination_type": "page_number",
            "items_per_page": 25
        }
    
    @staticmethod
    def dice_config() -> Dict[str, Any]:
        """Dice job board configuration"""
        return {
            "name": "Dice",
            "description": "Dice - Tech jobs",
            "type": JobBoardType.HTML.value,
            "base_url": "https://www.dice.com",
            "search_url_template": "https://www.dice.com/jobs?q={query}&location={location}&page={page}",
            "selectors": {
                "job_container": "[data-cy='search-result-title']",
                "title": "[data-cy='search-result-title'] a",
                "company": "[data-cy='search-result-company']",
                "location": "[data-cy='search-result-location']",
                "description": "[data-cy='search-result-summary']",
                "url": "[data-cy='search-result-title'] a"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "rate_limit_delay": 2.0,
            "max_pages": 20,
            "request_timeout": 30,
            "retry_attempts": 3,
            "quality_threshold": 0.8,
            "is_active": True,
            "requires_js": True,
            "pagination_type": "page_number",
            "items_per_page": 20
        }
    
    @staticmethod
    def monster_config() -> Dict[str, Any]:
        """Monster job board configuration"""
        return {
            "name": "Monster",
            "description": "Monster - Job search",
            "type": JobBoardType.HTML.value,
            "base_url": "https://www.monster.com",
            "search_url_template": "https://www.monster.com/jobs/search?q={query}&where={location}&page={page}",
            "selectors": {
                "job_container": "[data-testid='job-card']",
                "title": "[data-testid='job-title']",
                "company": "[data-testid='job-company']",
                "location": "[data-testid='job-location']",
                "description": "[data-testid='job-description']",
                "url": "[data-testid='job-title'] a"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "rate_limit_delay": 2.5,
            "max_pages": 15,
            "request_timeout": 30,
            "retry_attempts": 3,
            "quality_threshold": 0.75,
            "is_active": True,
            "requires_js": True,
            "pagination_type": "page_number",
            "items_per_page": 25
        }
    
    @staticmethod
    def ziprecruiter_config() -> Dict[str, Any]:
        """ZipRecruiter job board configuration"""
        return {
            "name": "ZipRecruiter",
            "description": "ZipRecruiter - Job search",
            "type": JobBoardType.HTML.value,
            "base_url": "https://www.ziprecruiter.com",
            "search_url_template": "https://www.ziprecruiter.com/jobs-search?search={query}&location={location}&page={page}",
            "selectors": {
                "job_container": "[data-testid='job_result']",
                "title": "[data-testid='job-title']",
                "company": "[data-testid='company-name']",
                "location": "[data-testid='job-location']",
                "description": "[data-testid='job-snippet']",
                "salary": "[data-testid='job-salary']",
                "url": "[data-testid='job-title'] a"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "rate_limit_delay": 2.0,
            "max_pages": 20,
            "request_timeout": 30,
            "retry_attempts": 3,
            "quality_threshold": 0.8,
            "is_active": True,
            "requires_js": True,
            "pagination_type": "page_number",
            "items_per_page": 20
        }
    
    @staticmethod
    def flexjobs_config() -> Dict[str, Any]:
        """FlexJobs configuration"""
        return {
            "name": "FlexJobs",
            "description": "FlexJobs - Flexible and remote jobs",
            "type": JobBoardType.HTML.value,
            "base_url": "https://www.flexjobs.com",
            "search_url_template": "https://www.flexjobs.com/search?search={query}&location={location}&page={page}",
            "selectors": {
                "job_container": ".job",
                "title": ".job-title",
                "company": ".job-company",
                "location": ".job-location",
                "description": ".job-description",
                "url": ".job-title a"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "rate_limit_delay": 3.0,
            "max_pages": 10,
            "request_timeout": 30,
            "retry_attempts": 3,
            "quality_threshold": 0.85,
            "is_active": True,
            "requires_js": True,
            "pagination_type": "page_number",
            "items_per_page": 15
        }
    
    @staticmethod
    def remote_co_config() -> Dict[str, Any]:
        """Remote.co configuration"""
        return {
            "name": "Remote.co",
            "description": "Remote.co - Remote jobs",
            "type": JobBoardType.HTML.value,
            "base_url": "https://remote.co",
            "search_url_template": "https://remote.co/remote-jobs/{query}/?page={page}",
            "selectors": {
                "job_container": ".job_board_job",
                "title": ".job_title",
                "company": ".job_company",
                "location": ".job_location",
                "description": ".job_description",
                "url": ".job_title a"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "rate_limit_delay": 2.0,
            "max_pages": 10,
            "request_timeout": 25,
            "retry_attempts": 3,
            "quality_threshold": 0.8,
            "is_active": True,
            "requires_js": False,
            "pagination_type": "page_number",
            "items_per_page": 20
        }
    
    @staticmethod
    def nofluffjobs_config() -> Dict[str, Any]:
        """NoFluffJobs configuration"""
        return {
            "name": "NoFluffJobs",
            "description": "NoFluffJobs - IT jobs",
            "type": JobBoardType.HTML.value,
            "base_url": "https://nofluffjobs.com",
            "search_url_template": "https://nofluffjobs.com/jobs?criteria={query}&page={page}",
            "selectors": {
                "job_container": "[data-cy='job-item']",
                "title": "[data-cy='job-title']",
                "company": "[data-cy='company-name']",
                "location": "[data-cy='job-location']",
                "description": "[data-cy='job-description']",
                "salary": "[data-cy='salary']",
                "url": "[data-cy='job-title'] a"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "rate_limit_delay": 2.0,
            "max_pages": 15,
            "request_timeout": 30,
            "retry_attempts": 3,
            "quality_threshold": 0.85,
            "is_active": True,
            "requires_js": True,
            "pagination_type": "page_number",
            "items_per_page": 20
        }
    
    @staticmethod
    def ycombinator_config() -> Dict[str, Any]:
        """Y Combinator Work List configuration"""
        return {
            "name": "Y Combinator",
            "description": "Y Combinator Work List - Startup jobs",
            "type": JobBoardType.HTML.value,
            "base_url": "https://www.worklist.fyi",
            "search_url_template": "https://www.worklist.fyi/companies?search={query}&page={page}",
            "selectors": {
                "job_container": ".job-listing",
                "title": ".job-title",
                "company": ".company-name",
                "location": ".job-location",
                "description": ".job-description",
                "url": ".job-title a"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "rate_limit_delay": 2.0,
            "max_pages": 10,
            "request_timeout": 30,
            "retry_attempts": 3,
            "quality_threshold": 0.8,
            "is_active": True,
            "requires_js": True,
            "pagination_type": "page_number",
            "items_per_page": 25
        }
    
    @staticmethod
    def techcareers_config() -> Dict[str, Any]:
        """TechCareers configuration"""
        return {
            "name": "TechCareers",
            "description": "TechCareers - Technology jobs",
            "type": JobBoardType.HTML.value,
            "base_url": "https://www.techcareers.com",
            "search_url_template": "https://www.techcareers.com/jobs/search?q={query}&l={location}&p={page}",
            "selectors": {
                "job_container": ".job-result",
                "title": ".job-title",
                "company": ".company-name",
                "location": ".job-location",
                "description": ".job-summary",
                "salary": ".salary-info",
                "url": ".job-title a"
            },
            "headers": {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
            "rate_limit_delay": 2.0,
            "max_pages": 15,
            "request_timeout": 30,
            "retry_attempts": 3,
            "quality_threshold": 0.8,
            "is_active": True,
            "requires_js": False,
            "pagination_type": "page_number",
            "items_per_page": 20
        }