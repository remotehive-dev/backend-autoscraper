"""Parsers for extracting structured data from web content"""

import re
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin, urlparse

from backend.scraper.utils import ScrapingUtils
from backend.scraper.exceptions import ParsingError, ValidationError
from backend.core.enums import ScraperSource

logger = logging.getLogger(__name__)

@dataclass
class ParsedJobPost:
    """Container for parsed job post data"""
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    posted_date: Optional[datetime] = None
    application_url: Optional[str] = None
    company_url: Optional[str] = None
    remote_friendly: bool = False
    benefits: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    source_url: Optional[str] = None
    source_platform: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    
    def is_valid(self) -> bool:
        """Check if the parsed job post has minimum required fields"""
        return bool(
            self.title and 
            self.company and 
            self.confidence_score >= 0.5
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert parsed job post to dictionary format"""
        return {
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'description': self.description,
            'requirements': self.requirements,
            'benefits': self.benefits,
            'salary_min': self.salary_min,
            'salary_max': self.salary_max,
            'salary_currency': self.salary_currency,
            'job_type': self.job_type,
            'experience_level': self.experience_level,
            'remote_friendly': self.remote_friendly,
            'source_url': self.source_url,
            'source_platform': self.source_platform,
            'posted_date': self.posted_date.isoformat() if self.posted_date else None,
            'application_deadline': self.application_deadline.isoformat() if self.application_deadline else None,
            'tags': self.tags,
            'confidence_score': self.confidence_score,
            'parsed_at': self.parsed_at.isoformat() if self.parsed_at else None
        }

class HTMLParser:
    """Base HTML parser with common functionality"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url
    
    def parse_html(self, html_content: str) -> BeautifulSoup:
        """Parse HTML content with BeautifulSoup"""
        if not html_content:
            raise ParsingError("HTML content is empty")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup
        except Exception as e:
            raise ParsingError(f"Failed to parse HTML: {str(e)}")
    
    def extract_text_by_selector(self, soup: BeautifulSoup, selector: str, 
                                multiple: bool = False) -> Union[str, List[str], None]:
        """Extract text using CSS selector"""
        try:
            if multiple:
                elements = soup.select(selector)
                return [ScrapingUtils.clean_text(el.get_text()) for el in elements if el.get_text().strip()]
            else:
                element = soup.select_one(selector)
                if element:
                    return ScrapingUtils.clean_text(element.get_text())
                return None
        except Exception as e:
            logger.warning(f"Failed to extract text with selector '{selector}': {str(e)}")
            return [] if multiple else None
    
    def extract_attribute_by_selector(self, soup: BeautifulSoup, selector: str, 
                                    attribute: str, multiple: bool = False) -> Union[str, List[str], None]:
        """Extract attribute using CSS selector"""
        try:
            if multiple:
                elements = soup.select(selector)
                return [el.get(attribute) for el in elements if el.get(attribute)]
            else:
                element = soup.select_one(selector)
                if element:
                    return element.get(attribute)
                return None
        except Exception as e:
            logger.warning(f"Failed to extract attribute '{attribute}' with selector '{selector}': {str(e)}")
            return [] if multiple else None
    
    def resolve_url(self, url: str) -> str:
        """Resolve relative URLs to absolute URLs"""
        if not url:
            return url
        
        if self.base_url and not url.startswith(('http://', 'https://')):
            return urljoin(self.base_url, url)
        
        return url

class JobPostParser(HTMLParser):
    """Parser for extracting job post information from HTML"""
    
    def __init__(self, parsing_rules: Dict[str, Any] = None, base_url: str = None, 
                 source: ScraperSource = None):
        super().__init__(base_url)
        self.parsing_rules = parsing_rules or {}
        self.source = source
        self.confidence_weights = {
            'title': 0.3,
            'company': 0.25,
            'location': 0.15,
            'description': 0.15,
            'salary': 0.1,
            'application_url': 0.05
        }
    
    def parse_job(self, html_content: str, url: str = None) -> ParsedJobPost:
        """Parse a single job post from HTML content"""
        soup = self.parse_html(html_content)
        job = ParsedJobPost()
        
        # Set metadata
        job.source_url = url
        job.source_platform = self.source.value if self.source else 'unknown'
        job.raw_data = {'html_length': len(html_content)}
        
        # Extract job information using parsing rules
        job.title = self._extract_title(soup)
        job.company = self._extract_company(soup)
        job.location = self._extract_location(soup)
        job.description = self._extract_description(soup)
        job.requirements = self._extract_requirements(soup)
        
        # Extract salary information
        salary_info = self._extract_salary(soup)
        job.salary_min = salary_info.get('min_salary')
        job.salary_max = salary_info.get('max_salary')
        job.salary_currency = salary_info.get('currency')
        
        # Extract additional fields
        job.job_type = self._extract_job_type(soup)
        job.experience_level = self._extract_experience_level(soup)
        job.posted_date = self._extract_posted_date(soup)
        job.application_url = self._extract_application_url(soup)
        job.company_url = self._extract_company_url(soup)
        job.remote_friendly = self._detect_remote_friendly(soup)
        job.benefits = self._extract_benefits(soup)
        job.skills = self._extract_skills(soup)
        job.tags = self._extract_tags(soup)
        
        # Calculate confidence score
        job.confidence_score = self._calculate_confidence_score(job)
        
        return job
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract job title"""
        selectors = self.parsing_rules.get('title_selectors', [
            'h1.job-title',
            '.job-title',
            'h1[data-testid="job-title"]',
            '.jobsearch-JobInfoHeader-title',
            '.job-header h1',
            'h1',
            '.title'
        ])
        
        for selector in selectors:
            title = self.extract_text_by_selector(soup, selector)
            if title and len(title.strip()) > 3:
                return title
        
        return None
    
    def _extract_company(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company name"""
        selectors = self.parsing_rules.get('company_selectors', [
            '.company-name',
            '[data-testid="company-name"]',
            '.jobsearch-InlineCompanyRating a',
            '.job-company',
            '.company',
            'a[data-tn-element="companyName"]'
        ])
        
        for selector in selectors:
            company = self.extract_text_by_selector(soup, selector)
            if company and len(company.strip()) > 1:
                return company
        
        return None
    
    def _extract_location(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract job location"""
        selectors = self.parsing_rules.get('location_selectors', [
            '.job-location',
            '[data-testid="job-location"]',
            '.jobsearch-JobInfoHeader-subtitle',
            '.location',
            '.job-info .location'
        ])
        
        for selector in selectors:
            location = self.extract_text_by_selector(soup, selector)
            if location and len(location.strip()) > 1:
                return location
        
        return None
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract job description"""
        selectors = self.parsing_rules.get('description_selectors', [
            '.job-description',
            '[data-testid="job-description"]',
            '.jobsearch-jobDescriptionText',
            '.description',
            '.job-content',
            '.job-details'
        ])
        
        for selector in selectors:
            description = self.extract_text_by_selector(soup, selector)
            if description and len(description.strip()) > 50:
                return description
        
        return None
    
    def _extract_requirements(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract job requirements"""
        selectors = self.parsing_rules.get('requirements_selectors', [
            '.requirements',
            '.job-requirements',
            '.qualifications',
            '.skills-required'
        ])
        
        for selector in selectors:
            requirements = self.extract_text_by_selector(soup, selector)
            if requirements and len(requirements.strip()) > 20:
                return requirements
        
        return None
    
    def _extract_salary(self, soup: BeautifulSoup) -> Dict[str, Optional[float]]:
        """Extract salary information"""
        selectors = self.parsing_rules.get('salary_selectors', [
            '.salary',
            '.job-salary',
            '[data-testid="salary"]',
            '.salary-range',
            '.compensation'
        ])
        
        for selector in selectors:
            salary_text = self.extract_text_by_selector(soup, selector)
            if salary_text:
                return ScrapingUtils.parse_salary_range(salary_text)
        
        return {'min_salary': None, 'max_salary': None, 'currency': None}
    
    def _extract_job_type(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract job type (full-time, part-time, etc.)"""
        selectors = self.parsing_rules.get('job_type_selectors', [
            '.job-type',
            '.employment-type',
            '[data-testid="job-type"]'
        ])
        
        # First try specific selectors
        for selector in selectors:
            job_type_text = self.extract_text_by_selector(soup, selector)
            if job_type_text:
                return ScrapingUtils.detect_job_type(job_type_text)
        
        # Fallback: analyze description for job type keywords
        description = self._extract_description(soup)
        if description:
            return ScrapingUtils.detect_job_type(description)
        
        return None
    
    def _extract_experience_level(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract experience level"""
        selectors = self.parsing_rules.get('experience_selectors', [
            '.experience-level',
            '.seniority-level',
            '.job-level'
        ])
        
        # First try specific selectors
        for selector in selectors:
            exp_text = self.extract_text_by_selector(soup, selector)
            if exp_text:
                return ScrapingUtils.extract_experience_level(exp_text)
        
        # Fallback: analyze title and description
        title = self._extract_title(soup)
        description = self._extract_description(soup)
        
        combined_text = f"{title or ''} {description or ''}"
        if combined_text.strip():
            return ScrapingUtils.extract_experience_level(combined_text)
        
        return None
    
    def _extract_posted_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract job posting date"""
        selectors = self.parsing_rules.get('date_selectors', [
            '.posted-date',
            '.job-date',
            '[data-testid="posted-date"]',
            '.date-posted'
        ])
        
        for selector in selectors:
            date_text = self.extract_text_by_selector(soup, selector)
            if date_text:
                return self._parse_date(date_text)
        
        return None
    
    def _extract_application_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract application URL"""
        selectors = self.parsing_rules.get('apply_url_selectors', [
            'a.apply-button',
            '.apply-link',
            '[data-testid="apply-button"]',
            'a[href*="apply"]'
        ])
        
        for selector in selectors:
            url = self.extract_attribute_by_selector(soup, selector, 'href')
            if url:
                return self.resolve_url(url)
        
        return None
    
    def _extract_company_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company URL"""
        selectors = self.parsing_rules.get('company_url_selectors', [
            '.company-name a',
            '.company-link',
            'a[data-tn-element="companyName"]'
        ])
        
        for selector in selectors:
            url = self.extract_attribute_by_selector(soup, selector, 'href')
            if url:
                return self.resolve_url(url)
        
        return None
    
    def _detect_remote_friendly(self, soup: BeautifulSoup) -> bool:
        """Detect if job is remote-friendly"""
        # Check location field
        location = self._extract_location(soup)
        if location:
            location_lower = location.lower()
            remote_keywords = ['remote', 'work from home', 'wfh', 'anywhere', 'distributed']
            if any(keyword in location_lower for keyword in remote_keywords):
                return True
        
        # Check description
        description = self._extract_description(soup)
        if description:
            desc_lower = description.lower()
            remote_keywords = ['remote work', 'work from home', 'remote position', 'distributed team']
            if any(keyword in desc_lower for keyword in remote_keywords):
                return True
        
        return False
    
    def _extract_benefits(self, soup: BeautifulSoup) -> List[str]:
        """Extract job benefits"""
        selectors = self.parsing_rules.get('benefits_selectors', [
            '.benefits',
            '.job-benefits',
            '.perks'
        ])
        
        benefits = []
        for selector in selectors:
            benefit_elements = self.extract_text_by_selector(soup, selector, multiple=True)
            if benefit_elements:
                benefits.extend(benefit_elements)
        
        return list(set(benefits))  # Remove duplicates
    
    def _extract_skills(self, soup: BeautifulSoup) -> List[str]:
        """Extract required skills"""
        selectors = self.parsing_rules.get('skills_selectors', [
            '.skills',
            '.required-skills',
            '.technologies',
            '.tech-stack'
        ])
        
        skills = []
        for selector in selectors:
            skill_elements = self.extract_text_by_selector(soup, selector, multiple=True)
            if skill_elements:
                skills.extend(skill_elements)
        
        return list(set(skills))  # Remove duplicates
    
    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Extract job tags"""
        selectors = self.parsing_rules.get('tags_selectors', [
            '.tags',
            '.job-tags',
            '.categories'
        ])
        
        tags = []
        for selector in selectors:
            tag_elements = self.extract_text_by_selector(soup, selector, multiple=True)
            if tag_elements:
                tags.extend(tag_elements)
        
        return list(set(tags))  # Remove duplicates
    
    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse date from text"""
        if not date_text:
            return None
        
        date_text = date_text.lower().strip()
        now = datetime.utcnow()
        
        # Handle relative dates
        if 'today' in date_text or 'just posted' in date_text:
            return now
        elif 'yesterday' in date_text:
            return now - timedelta(days=1)
        elif 'days ago' in date_text:
            days_match = re.search(r'(\d+)\s*days?\s*ago', date_text)
            if days_match:
                days = int(days_match.group(1))
                return now - timedelta(days=days)
        elif 'weeks ago' in date_text:
            weeks_match = re.search(r'(\d+)\s*weeks?\s*ago', date_text)
            if weeks_match:
                weeks = int(weeks_match.group(1))
                return now - timedelta(weeks=weeks)
        elif 'months ago' in date_text:
            months_match = re.search(r'(\d+)\s*months?\s*ago', date_text)
            if months_match:
                months = int(months_match.group(1))
                return now - timedelta(days=months * 30)  # Approximate
        
        # Try to parse absolute dates
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{2}/\d{2}/\d{4})',  # MM/DD/YYYY
            r'(\d{2}-\d{2}-\d{4})',  # MM-DD-YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    date_str = match.group(1)
                    if '-' in date_str and len(date_str.split('-')[0]) == 4:
                        return datetime.strptime(date_str, '%Y-%m-%d')
                    elif '/' in date_str:
                        return datetime.strptime(date_str, '%m/%d/%Y')
                    elif '-' in date_str:
                        return datetime.strptime(date_str, '%m-%d-%Y')
                except ValueError:
                    continue
        
        return None
    
    def _calculate_confidence_score(self, job: ParsedJobPost) -> float:
        """Calculate confidence score for parsed job"""
        score = 0.0
        
        # Check each field and add to score based on weights
        if job.title:
            score += self.confidence_weights['title']
        if job.company:
            score += self.confidence_weights['company']
        if job.location:
            score += self.confidence_weights['location']
        if job.description and len(job.description) > 100:
            score += self.confidence_weights['description']
        if job.salary_min or job.salary_max:
            score += self.confidence_weights['salary']
        if job.application_url:
            score += self.confidence_weights['application_url']
        
        return min(score, 1.0)  # Cap at 1.0

class GenericParser(HTMLParser):
    """Generic parser for extracting data from any HTML page"""
    
    def __init__(self, selectors: Dict[str, str], base_url: str = None):
        super().__init__(base_url)
        self.selectors = selectors
    
    def parse(self, html_content: str) -> Dict[str, Any]:
        """Parse HTML content using provided selectors"""
        soup = self.parse_html(html_content)
        data = {}
        
        for field_name, selector in self.selectors.items():
            try:
                if selector.endswith('[]'):  # Multiple elements
                    selector = selector[:-2]
                    data[field_name] = self.extract_text_by_selector(soup, selector, multiple=True)
                else:
                    data[field_name] = self.extract_text_by_selector(soup, selector)
            except Exception as e:
                logger.warning(f"Failed to extract '{field_name}' with selector '{selector}': {str(e)}")
                data[field_name] = None
        
        return data