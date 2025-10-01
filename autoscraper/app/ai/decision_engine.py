import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from loguru import logger

from .openrouter_client import get_openrouter_client
from ..models.mongodb_models import JobBoard
from ..scrapers.types import ScrapingEngine

@dataclass
class AIAnalysisResult:
    """Result of AI analysis for a job board"""
    job_board_id: str
    recommended_engine: ScrapingEngine
    complexity_score: float
    selectors: Dict[str, str]
    anti_bot_measures: List[str]
    rate_limit_recommendation: int
    requires_javascript: bool
    confidence_score: float
    analyzed_at: datetime
    is_valid: bool = True

@dataclass
class ContentValidationResult:
    """Result of AI content validation"""
    quality_score: float
    completeness_score: float
    relevance_score: float
    issues: List[str]
    suggestions: List[str]
    is_duplicate_likely: bool
    validated_at: datetime

@dataclass
class OptimizationRecommendation:
    """AI-powered optimization recommendations"""
    recommended_delay: float
    recommended_concurrent_requests: int
    recommended_timeout: int
    user_agent_strategy: str
    proxy_recommendation: bool
    other_optimizations: List[str]
    created_at: datetime

@dataclass
class JobBoardAnalysis:
    """Job board analysis result"""
    is_scrapable: bool
    requires_js: bool
    has_anti_bot_measures: bool
    recommended_engine: ScrapingEngine
    confidence_score: float
    selectors: Dict[str, str]
    rate_limit_recommendation: float
    notes: str = ""

class AIDecisionEngine:
    """Central AI decision engine for intelligent scraping"""
    
    def __init__(self):
        self.analysis_cache: Dict[str, AIAnalysisResult] = {}
        self.validation_cache: Dict[str, ContentValidationResult] = {}
        self.optimization_cache: Dict[str, OptimizationRecommendation] = {}
        self.cache_ttl = timedelta(hours=24)  # Cache results for 24 hours
        
    async def analyze_job_board(self, job_board: JobBoard, html_sample: str = None) -> AIAnalysisResult:
        """Analyze job board and determine optimal scraping strategy"""
        # Check cache first
        cache_key = f"{job_board.id}_{hash(html_sample) if html_sample else 'default'}"
        if cache_key in self.analysis_cache:
            cached_result = self.analysis_cache[cache_key]
            if datetime.now() - cached_result.analyzed_at < self.cache_ttl:
                logger.info(f"Using cached analysis for job board: {job_board.name}")
                return cached_result
        
        try:
            client = await get_openrouter_client()
            
            # If no HTML sample provided, use a basic analysis
            if not html_sample:
                html_sample = await self._fetch_sample_html(job_board.base_url)
            
            # Get AI analysis
            ai_result = await client.analyze_job_board_structure(job_board.base_url, html_sample)
            
            # Convert to our result format
            result = AIAnalysisResult(
                job_board_id=str(job_board.id),
                recommended_engine=ScrapingEngine(ai_result.get("recommended_engine", "scrapy")),
                complexity_score=ai_result.get("complexity_score", 0.5),
                selectors=ai_result.get("selectors", {}),
                anti_bot_measures=ai_result.get("anti_bot_measures", []),
                rate_limit_recommendation=ai_result.get("rate_limit_recommendation", 30),
                requires_javascript=ai_result.get("requires_javascript", False),
                confidence_score=self._calculate_confidence_score(ai_result),
                analyzed_at=datetime.now()
            )
            
            # Cache the result
            self.analysis_cache[cache_key] = result
            
            logger.info(f"AI analysis completed for {job_board.name}: {result.recommended_engine.value} engine recommended")
            return result
            
        except Exception as e:
            logger.error(f"AI analysis failed for {job_board.name}: {e}")
            # Return fallback analysis
            return self._get_fallback_analysis(job_board)
    
    async def select_optimal_engine(self, job_board: JobBoard, html_sample: str = None) -> ScrapingEngine:
        """Select the optimal scraping engine for a job board"""
        analysis = await self.analyze_job_board(job_board, html_sample)
        
        # Apply business logic on top of AI recommendation
        if analysis.complexity_score > 0.8 or analysis.requires_javascript:
            return ScrapingEngine.SELENIUM
        elif analysis.complexity_score < 0.3 and not analysis.anti_bot_measures:
            return ScrapingEngine.BEAUTIFULSOUP
        else:
            return ScrapingEngine.SCRAPY
    
    async def generate_selectors(self, job_board: JobBoard, html_content: str) -> Dict[str, str]:
        """Generate CSS selectors for job posting elements"""
        try:
            client = await get_openrouter_client()
            selectors = await client.generate_css_selectors(html_content, job_board.name)
            
            # Validate selectors
            validated_selectors = self._validate_selectors(selectors)
            
            logger.info(f"Generated {len(validated_selectors)} selectors for {job_board.name}")
            return validated_selectors
            
        except Exception as e:
            logger.error(f"Selector generation failed for {job_board.name}: {e}")
            return self._get_fallback_selectors()
    
    async def validate_job_content(self, job_data: Dict[str, Any], job_board_name: str) -> ContentValidationResult:
        """Validate scraped job content using AI"""
        cache_key = f"{job_board_name}_{hash(str(job_data))}"
        if cache_key in self.validation_cache:
            cached_result = self.validation_cache[cache_key]
            if datetime.now() - cached_result.validated_at < timedelta(hours=1):
                return cached_result
        
        try:
            client = await get_openrouter_client()
            validation_result = await client.validate_job_content(job_data)
            
            result = ContentValidationResult(
                quality_score=validation_result.get("quality_score", 0.7),
                completeness_score=validation_result.get("completeness_score", 0.8),
                relevance_score=validation_result.get("relevance_score", 0.7),
                issues=validation_result.get("issues", []),
                suggestions=validation_result.get("suggestions", []),
                is_duplicate_likely=validation_result.get("is_duplicate_likely", False),
                validated_at=datetime.now()
            )
            
            # Cache the result
            self.validation_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Content validation failed: {e}")
            return self._get_fallback_validation()
    
    async def detect_anti_bot_measures(self, html_content: str, response_headers: Dict[str, str]) -> List[str]:
        """Detect anti-bot measures using AI"""
        try:
            client = await get_openrouter_client()
            measures = await client.detect_anti_bot_measures(html_content, response_headers)
            
            logger.info(f"Detected {len(measures)} anti-bot measures")
            return measures
            
        except Exception as e:
            logger.error(f"Anti-bot detection failed: {e}")
            return []
    
    async def optimize_scraping_parameters(self, job_board: JobBoard, performance_data: Dict[str, Any]) -> OptimizationRecommendation:
        """Get AI-powered optimization recommendations"""
        cache_key = f"{job_board.id}_optimization"
        if cache_key in self.optimization_cache:
            cached_result = self.optimization_cache[cache_key]
            if datetime.now() - cached_result.created_at < timedelta(hours=6):
                return cached_result
        
        try:
            client = await get_openrouter_client()
            optimization_result = await client.optimize_scraping_parameters(performance_data)
            
            result = OptimizationRecommendation(
                recommended_delay=optimization_result.get("recommended_delay", 2.0),
                recommended_concurrent_requests=optimization_result.get("recommended_concurrent_requests", 5),
                recommended_timeout=optimization_result.get("recommended_timeout", 30),
                user_agent_strategy=optimization_result.get("user_agent_strategy", "rotate"),
                proxy_recommendation=optimization_result.get("proxy_recommendation", False),
                other_optimizations=optimization_result.get("other_optimizations", []),
                created_at=datetime.now()
            )
            
            # Cache the result
            self.optimization_cache[cache_key] = result
            
            logger.info(f"Generated optimization recommendations for {job_board.name}")
            return result
            
        except Exception as e:
            logger.error(f"Optimization recommendation failed: {e}")
            return self._get_fallback_optimization()
    
    async def should_use_proxy(self, job_board: JobBoard, failure_rate: float) -> bool:
        """Determine if proxy should be used based on AI analysis"""
        analysis = await self.analyze_job_board(job_board)
        
        # Use proxy if:
        # 1. Anti-bot measures detected
        # 2. High failure rate
        # 3. High complexity score
        return (
            len(analysis.anti_bot_measures) > 0 or
            failure_rate > 0.3 or
            analysis.complexity_score > 0.7
        )
    
    async def calculate_optimal_delay(self, job_board: JobBoard, current_success_rate: float) -> float:
        """Calculate optimal delay between requests"""
        analysis = await self.analyze_job_board(job_board)
        base_delay = 60.0 / analysis.rate_limit_recommendation  # Convert rate limit to delay
        
        # Adjust based on success rate
        if current_success_rate < 0.5:
            base_delay *= 2.0  # Slow down if failing
        elif current_success_rate > 0.9:
            base_delay *= 0.8  # Speed up if succeeding
        
        return max(0.5, min(10.0, base_delay))  # Clamp between 0.5 and 10 seconds
    
    def _calculate_confidence_score(self, ai_result: Dict[str, Any]) -> float:
        """Calculate confidence score based on AI result completeness"""
        required_fields = ["recommended_engine", "complexity_score", "selectors"]
        present_fields = sum(1 for field in required_fields if field in ai_result and ai_result[field])
        return present_fields / len(required_fields)
    
    def _validate_selectors(self, selectors: Dict[str, str]) -> Dict[str, str]:
        """Validate and clean CSS selectors"""
        validated = {}
        for key, selector in selectors.items():
            if selector and isinstance(selector, str) and len(selector.strip()) > 0:
                validated[key] = selector.strip()
        return validated
    
    async def _fetch_sample_html(self, url: str) -> str:
        """Fetch a sample of HTML from the job board"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url)
                return response.text[:5000]  # Return first 5KB
        except Exception as e:
            logger.error(f"Failed to fetch sample HTML from {url}: {e}")
            return ""
    
    def _get_fallback_analysis(self, job_board: JobBoard) -> AIAnalysisResult:
        """Fallback analysis when AI is unavailable"""
        return AIAnalysisResult(
            job_board_id=str(job_board.id),
            recommended_engine=ScrapingEngine.SCRAPY,
            complexity_score=0.5,
            selectors=self._get_fallback_selectors(),
            anti_bot_measures=[],
            rate_limit_recommendation=30,
            requires_javascript=False,
            confidence_score=0.3,
            analyzed_at=datetime.now(),
            is_valid=False
        )
    
    def _get_fallback_selectors(self) -> Dict[str, str]:
        """Fallback CSS selectors"""
        return {
            "job_title": ".job-title, h1, h2, .title, [data-testid*='title']",
            "company": ".company, .company-name, .employer, [data-testid*='company']",
            "location": ".location, .job-location, .city, [data-testid*='location']",
            "description": ".description, .job-description, .content, [data-testid*='description']",
            "salary": ".salary, .pay, .compensation, [data-testid*='salary']",
            "date_posted": ".date, .posted-date, .job-date, [data-testid*='date']"
        }
    
    def _get_fallback_validation(self) -> ContentValidationResult:
        """Fallback validation when AI is unavailable"""
        return ContentValidationResult(
            quality_score=0.7,
            completeness_score=0.8,
            relevance_score=0.7,
            issues=[],
            suggestions=[],
            is_duplicate_likely=False,
            validated_at=datetime.now()
        )
    
    def _get_fallback_optimization(self) -> OptimizationRecommendation:
        """Fallback optimization when AI is unavailable"""
        return OptimizationRecommendation(
            recommended_delay=2.0,
            recommended_concurrent_requests=5,
            recommended_timeout=30,
            user_agent_strategy="rotate",
            proxy_recommendation=False,
            other_optimizations=["Use session persistence", "Implement retry logic"],
            created_at=datetime.now()
        )
    
    def clear_cache(self):
        """Clear all caches"""
        self.analysis_cache.clear()
        self.validation_cache.clear()
        self.optimization_cache.clear()
        logger.info("AI decision engine cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "analysis_cache_size": len(self.analysis_cache),
            "validation_cache_size": len(self.validation_cache),
            "optimization_cache_size": len(self.optimization_cache)
        }

# Global decision engine instance
_decision_engine_instance = None

def get_ai_decision_engine() -> AIDecisionEngine:
    """Get or create AI decision engine instance"""
    global _decision_engine_instance
    if _decision_engine_instance is None:
        _decision_engine_instance = AIDecisionEngine()
    return _decision_engine_instance