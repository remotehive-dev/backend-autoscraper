"""Custom exceptions for the web scraping engine"""

class ScrapingError(Exception):
    """Base exception for scraping operations"""
    def __init__(self, message: str, url: str = None, status_code: int = None):
        self.message = message
        self.url = url
        self.status_code = status_code
        super().__init__(self.message)

class RateLimitError(ScrapingError):
    """Raised when rate limit is exceeded"""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, **kwargs)

class ParsingError(ScrapingError):
    """Raised when parsing fails"""
    def __init__(self, message: str, selector: str = None, **kwargs):
        self.selector = selector
        super().__init__(message, **kwargs)

class NetworkError(ScrapingError):
    """Raised when network operations fail"""
    pass

class ValidationError(ScrapingError):
    """Raised when data validation fails"""
    def __init__(self, message: str, field: str = None, **kwargs):
        self.field = field
        super().__init__(message, **kwargs)

class ConfigurationError(ScrapingError):
    """Raised when scraper configuration is invalid"""
    pass

class TimeoutError(ScrapingError):
    """Raised when operations timeout"""
    def __init__(self, message: str = "Operation timed out", timeout_duration: float = None, **kwargs):
        self.timeout_duration = timeout_duration
        super().__init__(message, **kwargs)

class AuthenticationError(ScrapingError):
    """Raised when authentication fails"""
    pass

class CaptchaError(ScrapingError):
    """Raised when CAPTCHA is encountered"""
    def __init__(self, message: str = "CAPTCHA detected", captcha_type: str = None, **kwargs):
        self.captcha_type = captcha_type
        super().__init__(message, **kwargs)

class ProxyError(ScrapingError):
    """Raised when proxy-related errors occur"""
    def __init__(self, message: str = "Proxy error", proxy_url: str = None, **kwargs):
        self.proxy_url = proxy_url
        super().__init__(message, **kwargs)

class BrowserError(ScrapingError):
    """Raised when browser-related errors occur"""
    def __init__(self, message: str = "Browser error", browser_type: str = None, **kwargs):
        self.browser_type = browser_type
        super().__init__(message, **kwargs)

class SessionError(ScrapingError):
    """Raised when session-related errors occur"""
    def __init__(self, message: str = "Session error", session_id: str = None, **kwargs):
        self.session_id = session_id
        super().__init__(message, **kwargs)

class ContentError(ScrapingError):
    """Raised when content-related errors occur"""
    def __init__(self, message: str = "Content error", content_type: str = None, **kwargs):
        self.content_type = content_type
        super().__init__(message, **kwargs)

class ResourceError(ScrapingError):
    """Raised when resource-related errors occur"""
    def __init__(self, message: str = "Resource error", resource_type: str = None, **kwargs):
        self.resource_type = resource_type
        super().__init__(message, **kwargs)
        super().__init__(message, **kwargs)