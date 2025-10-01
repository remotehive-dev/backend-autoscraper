import os
import json
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import httpx
from loguru import logger

@dataclass
class OpenRouterConfig:
    """OpenRouter API configuration"""
    api_key: str
    model: str
    base_url: str
    max_tokens: int
    temperature: float
    timeout: int

class OpenRouterClient:
    """OpenRouter API client for AI-powered scraping decisions"""
    
    def __init__(self, config: Optional[OpenRouterConfig] = None):
        self.config = config or self._load_config()
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://remotehive.com",
                "X-Title": "RemoteHive AI Autoscraper"
            }
        )
        
    def _load_config(self) -> OpenRouterConfig:
        """Load configuration from environment variables"""
        return OpenRouterConfig(
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            model=os.getenv("OPENROUTER_MODEL", "mistralai/mistral-nemo:free"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("OPENROUTER_TEMPERATURE", "0.3")),
            timeout=int(os.getenv("OPENROUTER_TIMEOUT", "30"))
        )
    
    async def _make_request(self, messages: List[Dict[str, str]], system_prompt: str = "") -> Optional[str]:
        """Make a request to OpenRouter API"""
        try:
            # Prepare messages with system prompt if provided
            request_messages = []
            if system_prompt:
                request_messages.append({"role": "system", "content": system_prompt})
            request_messages.extend(messages)
            
            payload = {
                "model": self.config.model,
                "messages": request_messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except Exception as e:
            logger.error(f"OpenRouter API request failed: {e}")
            return None
    
    async def analyze_job_board_structure(self, url: str, html_sample: str) -> Dict[str, Any]:
        """Analyze job board structure and recommend scraping strategy"""
        system_prompt = """
You are an expert web scraping analyst. Analyze the provided HTML structure and recommend the optimal scraping approach.
Respond with a JSON object containing:
- recommended_engine: "scrapy", "bs4", or "selenium"
- complexity_score: float between 0-1 (0=simple, 1=complex)
- selectors: object with CSS selectors for job_title, company, location, description, salary, date_posted
- anti_bot_measures: array of detected anti-bot measures
- rate_limit_recommendation: integer (requests per minute)
- requires_javascript: boolean
"""
        
        messages = [{
            "role": "user",
            "content": f"Analyze this job board structure:\nURL: {url}\nHTML Sample:\n{html_sample[:2000]}..."
        }]
        
        response = await self._make_request(messages, system_prompt)
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.error("Failed to parse AI response as JSON")
                return self._get_fallback_analysis()
        
        return self._get_fallback_analysis()
    
    async def generate_css_selectors(self, html_content: str, job_board_name: str) -> Dict[str, str]:
        """Generate CSS selectors for job posting elements"""
        system_prompt = """
You are a CSS selector expert. Analyze the HTML and generate precise CSS selectors for job posting elements.
Respond with a JSON object containing selectors for:
- job_title
- company
- location
- description
- salary (if available)
- date_posted (if available)
- apply_url (if available)

Ensure selectors are specific and robust.
"""
        
        messages = [{
            "role": "user",
            "content": f"Generate CSS selectors for {job_board_name}:\n{html_content[:1500]}..."
        }]
        
        response = await self._make_request(messages, system_prompt)
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return self._get_fallback_selectors()
        
        return self._get_fallback_selectors()
    
    async def validate_job_content(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and score job posting content quality"""
        system_prompt = """
You are a job posting quality analyst. Evaluate the provided job data and respond with a JSON object:
- quality_score: float between 0-1 (0=poor, 1=excellent)
- completeness_score: float between 0-1
- relevance_score: float between 0-1
- issues: array of identified issues
- suggestions: array of improvement suggestions
- is_duplicate_likely: boolean
"""
        
        messages = [{
            "role": "user",
            "content": f"Evaluate this job posting:\n{json.dumps(job_data, indent=2)}"
        }]
        
        response = await self._make_request(messages, system_prompt)
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return self._get_fallback_validation()
        
        return self._get_fallback_validation()
    
    async def detect_anti_bot_measures(self, html_content: str, response_headers: Dict[str, str]) -> List[str]:
        """Detect anti-bot measures on the website"""
        system_prompt = """
You are a web security analyst. Analyze the HTML content and response headers to detect anti-bot measures.
Respond with a JSON array of detected measures, such as:
- "cloudflare_protection"
- "captcha_present"
- "rate_limiting"
- "javascript_required"
- "user_agent_checking"
- "ip_blocking"
- "session_validation"
"""
        
        messages = [{
            "role": "user",
            "content": f"Detect anti-bot measures:\nHeaders: {json.dumps(response_headers)}\nHTML: {html_content[:1000]}..."
        }]
        
        response = await self._make_request(messages, system_prompt)
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return []
        
        return []
    
    async def optimize_scraping_parameters(self, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize scraping parameters based on performance data"""
        system_prompt = """
You are a web scraping optimization expert. Analyze performance data and recommend optimizations.
Respond with a JSON object containing:
- recommended_delay: float (seconds between requests)
- recommended_concurrent_requests: integer
- recommended_timeout: integer (seconds)
- user_agent_strategy: string
- proxy_recommendation: boolean
- other_optimizations: array of suggestions
"""
        
        messages = [{
            "role": "user",
            "content": f"Optimize scraping based on this performance data:\n{json.dumps(performance_data, indent=2)}"
        }]
        
        response = await self._make_request(messages, system_prompt)
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return self._get_fallback_optimization()
        
        return self._get_fallback_optimization()
    
    def _get_fallback_analysis(self) -> Dict[str, Any]:
        """Fallback analysis when AI is unavailable"""
        return {
            "recommended_engine": "scrapy",
            "complexity_score": 0.5,
            "selectors": self._get_fallback_selectors(),
            "anti_bot_measures": [],
            "rate_limit_recommendation": 30,
            "requires_javascript": False
        }
    
    def _get_fallback_selectors(self) -> Dict[str, str]:
        """Fallback CSS selectors"""
        return {
            "job_title": ".job-title, h1, h2, .title",
            "company": ".company, .company-name, .employer",
            "location": ".location, .job-location, .city",
            "description": ".description, .job-description, .content",
            "salary": ".salary, .pay, .compensation",
            "date_posted": ".date, .posted-date, .job-date"
        }
    
    def _get_fallback_validation(self) -> Dict[str, Any]:
        """Fallback validation when AI is unavailable"""
        return {
            "quality_score": 0.7,
            "completeness_score": 0.8,
            "relevance_score": 0.7,
            "issues": [],
            "suggestions": [],
            "is_duplicate_likely": False
        }
    
    def _get_fallback_optimization(self) -> Dict[str, Any]:
        """Fallback optimization when AI is unavailable"""
        return {
            "recommended_delay": 2.0,
            "recommended_concurrent_requests": 5,
            "recommended_timeout": 30,
            "user_agent_strategy": "rotate",
            "proxy_recommendation": False,
            "other_optimizations": ["Use session persistence", "Implement retry logic"]
        }
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# Global client instance
_client_instance = None

async def get_openrouter_client() -> OpenRouterClient:
    """Get or create OpenRouter client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = OpenRouterClient()
    return _client_instance