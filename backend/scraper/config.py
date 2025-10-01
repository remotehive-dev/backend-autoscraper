"""Configuration management for the enhanced web scraping engine"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class ScrapingMode(Enum):
    """Scraping mode enumeration"""
    REQUESTS = "requests"
    PLAYWRIGHT = "playwright"
    HYBRID = "hybrid"  # Use Playwright for complex sites, requests for simple ones

class AntiDetectionLevel(Enum):
    """Anti-detection level enumeration"""
    BASIC = "basic"      # Basic user agent rotation
    MODERATE = "moderate" # + Random delays, headers
    ADVANCED = "advanced" # + Stealth mode, proxy rotation
    MAXIMUM = "maximum"   # + CAPTCHA solving, behavioral mimicking

@dataclass
class PlaywrightSettings:
    """Playwright-specific configuration settings"""
    headless: bool = True
    timeout: int = 30000  # milliseconds
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: Optional[str] = None
    proxy: Optional[str] = None
    enable_stealth: bool = True
    enable_images: bool = False
    enable_javascript: bool = True
    browser_type: str = "chromium"  # chromium, firefox, webkit
    
    # Anti-detection settings
    random_viewport: bool = True
    random_user_agent: bool = True
    simulate_human_behavior: bool = True
    bypass_cloudflare: bool = True
    
@dataclass
class RateLimitingSettings:
    """Rate limiting configuration"""
    enabled: bool = True
    base_delay: float = 1.0  # seconds
    max_delay: float = 10.0  # seconds
    adaptive: bool = True
    burst_protection: bool = True
    requests_per_minute: int = 60
    concurrent_requests: int = 5
    
    # Intelligent rate limiting
    detect_rate_limits: bool = True
    backoff_multiplier: float = 2.0
    recovery_time: int = 300  # seconds
    
@dataclass
class DeduplicationSettings:
    """Content deduplication configuration"""
    enabled: bool = True
    url_deduplication: bool = True
    content_deduplication: bool = True
    similarity_threshold: float = 0.85
    cache_size: int = 10000
    cache_ttl: int = 3600  # seconds
    
    # Advanced deduplication
    fuzzy_matching: bool = True
    semantic_deduplication: bool = False  # Requires ML models
    
@dataclass
class ProxySettings:
    """Proxy configuration"""
    enabled: bool = False
    proxy_list: list = field(default_factory=list)
    rotation_enabled: bool = True
    health_check_enabled: bool = True
    health_check_interval: int = 300  # seconds
    max_failures: int = 3
    
    # Proxy types
    http_proxies: list = field(default_factory=list)
    socks_proxies: list = field(default_factory=list)
    residential_proxies: list = field(default_factory=list)
    
@dataclass
class MonitoringSettings:
    """Monitoring and metrics configuration"""
    enabled: bool = True
    performance_tracking: bool = True
    error_tracking: bool = True
    success_rate_tracking: bool = True
    response_time_tracking: bool = True
    
    # Alerting
    alert_on_failures: bool = True
    failure_threshold: float = 0.1  # 10% failure rate
    alert_email: Optional[str] = None
    
@dataclass
class EnhancedScrapingConfig:
    """Enhanced scraping engine configuration"""
    # Basic settings
    scraping_mode: ScrapingMode = ScrapingMode.REQUESTS
    anti_detection_level: AntiDetectionLevel = AntiDetectionLevel.MODERATE
    
    # Component settings
    playwright: PlaywrightSettings = field(default_factory=PlaywrightSettings)
    rate_limiting: RateLimitingSettings = field(default_factory=RateLimitingSettings)
    deduplication: DeduplicationSettings = field(default_factory=DeduplicationSettings)
    proxy: ProxySettings = field(default_factory=ProxySettings)
    monitoring: MonitoringSettings = field(default_factory=MonitoringSettings)
    
    # Site-specific overrides
    site_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    @classmethod
    def from_env(cls) -> 'EnhancedScrapingConfig':
        """Create configuration from environment variables"""
        config = cls()
        
        # Basic settings
        config.scraping_mode = ScrapingMode(os.getenv('SCRAPING_MODE', 'requests'))
        config.anti_detection_level = AntiDetectionLevel(os.getenv('ANTI_DETECTION_LEVEL', 'moderate'))
        
        # Playwright settings
        config.playwright.headless = os.getenv('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
        config.playwright.timeout = int(os.getenv('PLAYWRIGHT_TIMEOUT', '30000'))
        config.playwright.enable_stealth = os.getenv('PLAYWRIGHT_STEALTH', 'true').lower() == 'true'
        config.playwright.browser_type = os.getenv('PLAYWRIGHT_BROWSER', 'chromium')
        
        # Rate limiting settings
        config.rate_limiting.enabled = os.getenv('RATE_LIMITING_ENABLED', 'true').lower() == 'true'
        config.rate_limiting.base_delay = float(os.getenv('RATE_LIMIT_DELAY', '1.0'))
        config.rate_limiting.adaptive = os.getenv('ADAPTIVE_RATE_LIMITING', 'true').lower() == 'true'
        config.rate_limiting.requests_per_minute = int(os.getenv('REQUESTS_PER_MINUTE', '60'))
        
        # Deduplication settings
        config.deduplication.enabled = os.getenv('DEDUPLICATION_ENABLED', 'true').lower() == 'true'
        config.deduplication.similarity_threshold = float(os.getenv('SIMILARITY_THRESHOLD', '0.85'))
        
        # Proxy settings
        config.proxy.enabled = os.getenv('PROXY_ENABLED', 'false').lower() == 'true'
        proxy_list = os.getenv('PROXY_LIST', '')
        if proxy_list:
            config.proxy.proxy_list = [p.strip() for p in proxy_list.split(',')]
        
        # Monitoring settings
        config.monitoring.enabled = os.getenv('MONITORING_ENABLED', 'true').lower() == 'true'
        config.monitoring.alert_email = os.getenv('ALERT_EMAIL')
        
        return config
    
    def get_site_config(self, domain: str) -> Dict[str, Any]:
        """Get site-specific configuration overrides"""
        return self.site_configs.get(domain, {})
    
    def should_use_playwright(self, url: str) -> bool:
        """Determine if Playwright should be used for a specific URL"""
        if self.scraping_mode == ScrapingMode.PLAYWRIGHT:
            return True
        elif self.scraping_mode == ScrapingMode.REQUESTS:
            return False
        else:  # HYBRID mode
            # Use Playwright for complex sites that typically require JS
            complex_sites = [
                'linkedin.com', 'glassdoor.com', 'indeed.com',
                'angel.co', 'stackoverflow.com', 'github.com'
            ]
            return any(site in url.lower() for site in complex_sites)
    
    def get_effective_config(self, url: str) -> Dict[str, Any]:
        """Get effective configuration for a specific URL"""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.lower()
        
        # Start with base config
        effective_config = {
            'use_playwright': self.should_use_playwright(url),
            'anti_detection_level': self.anti_detection_level.value,
            'rate_limiting': self.rate_limiting,
            'deduplication': self.deduplication,
            'proxy': self.proxy,
            'playwright': self.playwright
        }
        
        # Apply site-specific overrides
        site_config = self.get_site_config(domain)
        effective_config.update(site_config)
        
        return effective_config

# Global configuration instance
_global_config: Optional[EnhancedScrapingConfig] = None

def get_scraping_config() -> EnhancedScrapingConfig:
    """Get the global scraping configuration"""
    global _global_config
    if _global_config is None:
        _global_config = EnhancedScrapingConfig.from_env()
    return _global_config

def set_scraping_config(config: EnhancedScrapingConfig):
    """Set the global scraping configuration"""
    global _global_config
    _global_config = config

def reset_scraping_config():
    """Reset the global scraping configuration"""
    global _global_config
    _global_config = None