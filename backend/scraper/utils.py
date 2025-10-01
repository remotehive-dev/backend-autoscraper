"""Utility functions and classes for web scraping"""

import time
import random
import hashlib
import re
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin, urlparse, parse_qs
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from backend.scraper.exceptions import RateLimitError, ValidationError

logger = logging.getLogger(__name__)

@dataclass
class ScrapingResult:
    """Container for scraping results"""
    success: bool
    url: str
    status_code: Optional[int] = None
    content: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    response_time: Optional[float] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class RateLimiter:
    """Rate limiter for web scraping requests"""
    
    def __init__(self, requests_per_second: float = 1.0, burst_size: int = 5):
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_update = time.time()
        self.request_times = []
    
    def acquire(self, timeout: float = 30.0) -> bool:
        """Acquire permission to make a request"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_time = time.time()
            
            # Refill tokens based on time elapsed
            time_passed = current_time - self.last_update
            self.tokens = min(
                self.burst_size,
                self.tokens + time_passed * self.requests_per_second
            )
            self.last_update = current_time
            
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                self.request_times.append(current_time)
                
                # Clean old request times (keep last minute)
                cutoff = current_time - 60
                self.request_times = [t for t in self.request_times if t > cutoff]
                
                return True
            
            # Calculate sleep time
            sleep_time = (1.0 - self.tokens) / self.requests_per_second
            time.sleep(min(sleep_time, 0.1))
        
        raise RateLimitError(f"Rate limit timeout after {timeout} seconds")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics"""
        current_time = time.time()
        recent_requests = len([t for t in self.request_times if t > current_time - 60])
        
        return {
            'tokens_available': self.tokens,
            'requests_per_second': self.requests_per_second,
            'burst_size': self.burst_size,
            'recent_requests_per_minute': recent_requests,
            'last_request': self.request_times[-1] if self.request_times else None
        }

class ScrapingUtils:
    """Utility functions for web scraping operations"""
    
    @staticmethod
    def normalize_url(url: str, base_url: str = None) -> str:
        """Normalize and validate URL"""
        if not url:
            raise ValidationError("URL cannot be empty")
        
        # Handle relative URLs
        if base_url and not url.startswith(('http://', 'https://')):
            url = urljoin(base_url, url)
        
        # Basic URL validation
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValidationError(f"Invalid URL format: {url}")
        
        return url
    
    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        return parsed.netloc.lower()
    
    @staticmethod
    def generate_request_id(url: str, timestamp: datetime = None) -> str:
        """Generate unique request ID"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        content = f"{url}_{timestamp.isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common HTML entities
        html_entities = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&hellip;': '...',
        }
        
        for entity, replacement in html_entities.items():
            text = text.replace(entity, replacement)
        
        return text.strip()
    
    @staticmethod
    def extract_numbers(text: str) -> List[float]:
        """Extract numbers from text"""
        if not text:
            return []
        
        # Pattern to match numbers (including decimals and currency)
        pattern = r'[\d,]+(?:\.\d+)?'
        matches = re.findall(pattern, text.replace(',', ''))
        
        numbers = []
        for match in matches:
            try:
                numbers.append(float(match))
            except ValueError:
                continue
        
        return numbers
    
    @staticmethod
    def parse_salary_range(text: str) -> Dict[str, Optional[float]]:
        """Parse salary information from text"""
        if not text:
            return {'min_salary': None, 'max_salary': None, 'currency': None}
        
        # Common currency symbols
        currency_pattern = r'[$£€¥₹]'
        currency_match = re.search(currency_pattern, text)
        currency = currency_match.group() if currency_match else None
        
        # Extract numbers
        numbers = ScrapingUtils.extract_numbers(text)
        
        if len(numbers) >= 2:
            return {
                'min_salary': min(numbers),
                'max_salary': max(numbers),
                'currency': currency
            }
        elif len(numbers) == 1:
            return {
                'min_salary': numbers[0],
                'max_salary': numbers[0],
                'currency': currency
            }
        else:
            return {'min_salary': None, 'max_salary': None, 'currency': currency}
    
    @staticmethod
    def detect_job_type(text: str) -> str:
        """Detect job type from text"""
        if not text:
            return 'unknown'
        
        text_lower = text.lower()
        
        # Job type patterns
        patterns = {
            'full-time': ['full-time', 'full time', 'permanent', 'ft'],
            'part-time': ['part-time', 'part time', 'pt'],
            'contract': ['contract', 'contractor', 'freelance', 'temporary', 'temp'],
            'internship': ['intern', 'internship', 'trainee'],
            'remote': ['remote', 'work from home', 'wfh', '100% remote'],
        }
        
        for job_type, keywords in patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                return job_type
        
        return 'unknown'
    
    @staticmethod
    def extract_experience_level(text: str) -> str:
        """Extract experience level from text"""
        if not text:
            return 'unknown'
        
        text_lower = text.lower()
        
        # Experience level patterns
        patterns = {
            'entry': ['entry', 'junior', 'graduate', 'new grad', '0-1 year', '0-2 year'],
            'mid': ['mid', 'intermediate', '2-5 year', '3-5 year', '2+ year'],
            'senior': ['senior', 'lead', '5+ year', '5-10 year', 'experienced'],
            'executive': ['director', 'vp', 'vice president', 'cto', 'ceo', 'head of']
        }
        
        for level, keywords in patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                return level
        
        return 'unknown'
    
    @staticmethod
    def generate_user_agent() -> str:
        """Generate a random user agent string"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        return random.choice(user_agents)
    
    @staticmethod
    def calculate_content_hash(content: str) -> str:
        """Calculate hash of content for duplicate detection"""
        if not content:
            return ""
        
        # Normalize content before hashing
        normalized = ScrapingUtils.clean_text(content).lower()
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Validate email address"""
        if not email:
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """Extract URLs from text"""
        if not text:
            return []
        
        url_pattern = r'https?://[^\s<>"]+'
        urls = re.findall(url_pattern, text)
        
        # Clean and validate URLs
        valid_urls = []
        for url in urls:
            try:
                # Remove trailing punctuation
                url = url.rstrip('.,;:!?')
                parsed = urlparse(url)
                if parsed.scheme and parsed.netloc:
                    valid_urls.append(url)
            except Exception:
                continue
        
        return valid_urls
    
    @staticmethod
    def get_random_delay(min_delay: float = 1.0, max_delay: float = 3.0) -> float:
        """Get random delay for rate limiting"""
        return random.uniform(min_delay, max_delay)
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"